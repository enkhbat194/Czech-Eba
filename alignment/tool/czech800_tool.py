# -*- coding: utf-8 -*-
"""Czech800 local audio/video timestamp workbench, pilot v0.1.
All timestamps are CANDIDATES until the reviewer verifies them.
Original files are read-only. Works with CMD and existing NVIDIA GPU setup.
"""
import argparse
import contextlib
import csv
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Czech800")
RAW = ROOT / "raw"
DATA = ROOT / "data"
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
REVIEW = ROOT / "review"
MODELS = ROOT / "models"
VIDEO = RAW / "Czech800.mp4"
AUDIO = RAW / "Czech800.m4a"
TARGETS = DATA / "czech_810_alignment_targets.json"
CANDIDATES = DATA / "alignment_candidates.json"
ANCHORS = DATA / "video_anchors.json"
SYNC = DATA / "sync_report.json"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def setup():
    for d in (RAW, DATA, WORK, OUTPUT, REVIEW, MODELS):
        d.mkdir(parents=True, exist_ok=True)

def run(args, *, raw=False):
    kw = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "check": True}
    try:
        p = subprocess.run([str(v) for v in args], **kw)
    except FileNotFoundError as e:
        raise RuntimeError(f"Required program not found: {args[0]}") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError((e.stderr or b"").decode("utf-8", "replace")[-1800:]) from e
    return p.stdout if raw else p.stdout.decode("utf-8", "replace")

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

def read_json(path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return default

def rows():
    data = read_json(TARGETS)
    if not data:
        raise RuntimeError(f"Missing targets: {TARGETS}. Run INSTALL.cmd.")
    found = data["rows"] if isinstance(data, dict) else data
    return found

def probe(path):
    info = json.loads(run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", path]))
    return {
        "duration_sec": float(info["format"]["duration"]),
        "size_bytes": int(info["format"].get("size", 0)),
        "streams": [{"type": s.get("codec_type"), "codec": s.get("codec_name")} for s in info["streams"]]
    }

def check(args):
    setup()
    print("Czech800 / diagnostic")
    for path in (VIDEO, AUDIO, TARGETS):
        print(("OK      " if path.exists() else "MISSING ") + str(path))
        if path.exists() and path.suffix.lower() in (".mp4", ".m4a"):
            print(json.dumps(probe(path), indent=2))
    import ctranslate2
    print("CTranslate2", ctranslate2.__version__, "CUDA devices", ctranslate2.get_cuda_device_count())
    print("Targets", len(rows()))
    print("Candidate records", len(read_json(CANDIDATES, {})))
    print("TIP: RUN.cmd sync, RUN.cmd scan --limit 20, RUN.cmd transcribe --limit 20")

def read_audio(path, start, duration, rate=8000):
    if start < 0:
        start = 0
    b = run([FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error",
             "-ss", f"{start:.3f}", "-i", path, "-t", f"{duration:.3f}",
             "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"], raw=True)
    import numpy as np
    return np.frombuffer(b, dtype="<f4").copy()

def sync(args):
    import numpy as np
    from scipy.signal import correlate, correlation_lags
    a = probe(AUDIO)
    v = probe(VIDEO)
    length = min(a["duration_sec"], v["duration_sec"])
    points = [70.0, max(80.0, length / 2), max(90.0, length - 110)]
    res = []
    for t in points:
        t = min(t, length - 24)
        left = read_audio(VIDEO, t, 14, rate=8000)
        right = read_audio(AUDIO, t, 14, rate=8000)
        n = min(len(left), len(right))
        left, right = left[:n], right[:n]
        # Normalize amplitudes; 14s samples, bounded search +/-2 seconds.
        left -= np.mean(left)
        right -= np.mean(right)
        corr = correlate(left, right, method="fft", mode="full")
        lags = correlation_lags(len(left), len(right), mode="full")
        mask = np.abs(lags) <= 16000
        selected = np.flatnonzero(mask)
        k = selected[int(np.argmax(corr[mask]))]
        lag = int(lags[k])
        # Peak normalized against the total signal energy: correlation score.
        confidence = float(corr[k] / (math.sqrt(float(np.dot(left, left) * np.dot(right, right))) + 1e-12))
        val = {"time_sec": round(t, 3), "sample_lag_sec": round(lag/8000, 4),
               "correlation": round(confidence, 5)}
        res.append(val)
        print("CHECK", val)
    valid = all(x["correlation"] >= 0.9 and abs(x["sample_lag_sec"]) < 0.15 for x in res)
    report = {"mp4": str(VIDEO), "m4a": str(AUDIO), "points": res,
              "same_audio_close_sync": valid,
              "note": "Correlation only at three test positions; not a full-file proof."}
    atomic_json(SYNC, report)
    print("SYNC", "PASS" if valid else "REVIEW OFFSET/ENCODING", "=>", SYNC)

def frame_green_score(frame):
    import numpy as np
    small = frame[::4, ::4]
    b = small[:,:,0].astype(np.float32)
    g = small[:,:,1].astype(np.float32)
    r = small[:,:,2].astype(np.float32)
    return float(np.mean((g > 65) & (g > b*1.18) & (g > r*1.18)))

def scan(args):
    import cv2
    setup()
    if not VIDEO.exists():
        raise RuntimeError("Video missing")
    data = rows()
    if args.limit:
        data = data[:args.limit]
    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        raise RuntimeError("Could not open video via OpenCV")
    out = read_json(ANCHORS, {})
    for idx, row in enumerate(data, 1):
        uid = row["id"]
        approx = float(row.get("approximate_ocr_start_sec") or 0)
        vals = []
        # OCR windows are rough: look +/-10sec for green word-card rise.
        t = max(0, approx - 10)
        while t <= approx + 10.001:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if ok:
                vals.append((round(t, 2), frame_green_score(frame)))
            t += 0.5
        rises = [(a[0], a[1]) for prev, a in zip(vals, vals[1:])
                 if prev[1] < 0.22 and a[1] >= 0.22]
        if rises:
            closest = min(rises, key=lambda v: abs(v[0]-approx))
            anchor = closest[0]
            status = "VISUAL_GREEN_TRANSITION_CANDIDATE"
        else:
            anchor = None
            status = "NOT_FOUND"
        out[uid] = {"id": uid, "czech": row.get("czech_original"), "ocr_approx_sec": approx,
                    "frame_green_transition_sec": anchor, "status": status,
                    "samples": vals}
        if idx % 5 == 0:
            atomic_json(ANCHORS, out)
        print(f"{idx:03d}/{len(data):03d} {uid} approx={approx:.2f} green={anchor} [{status}]")
    cap.release()
    atomic_json(ANCHORS, out)
    print("Saved", ANCHORS)
    print("WARNING: green scene change != exact spoken onset.")

def normalize(txt):
    text = unicodedata.normalize("NFKD", str(txt).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def flat_word(txt):
    return re.sub(r"[^a-z0-9]", "", normalize(txt))

def classify(utterance, row):
    from rapidfuzz import fuzz
    text = normalize(utterance)
    original = normalize(row.get("czech_sentence_original", ""))
    corrected = normalize(row.get("czech_sentence_corrected", ""))
    target = normalize(row.get("czech_original", ""))
    corrected_word = normalize(row.get("czech_corrected", ""))
    sentence_score = max((fuzz.ratio(text, t) for t in (original, corrected) if t), default=0)
    w_score = max((fuzz.ratio(flat_word(utterance), flat_word(t)) for t in (target, corrected_word) if t), default=0)
    if sentence_score >= 81 and len(text.split()) >= 2:
        return "czech_sentence", round(sentence_score, 1)
    if w_score >= 79 and len(text.split()) <= 4:
        return "czech_word", round(w_score, 1)
    return "unclassified", round(max(sentence_score, w_score), 1)

def transcribe(args):
    from faster_whisper import WhisperModel
    setup()
    data = rows()
    if args.limit:
        data = data[:args.limit]
    if args.start:
        data = [r for r in data if int(r["id"].split("_")[-1]) >= args.start]
    results = read_json(CANDIDATES, {})
    anchors = read_json(ANCHORS, {})
    print(f"Loading {args.model}, {args.device}, {args.compute} ...", flush=True)
    whisper = WhisperModel(args.model, device=args.device, compute_type=args.compute,
                           download_root=str(MODELS), cpu_threads=6)
    for idx, row in enumerate(data, 1):
        uid = row["id"]
        if uid in results and not args.force:
            print("SKIP cached", uid)
            continue
        a = float(row.get("approximate_ocr_start_sec") or 0)
        b = float(row.get("approximate_ocr_end_sec") or (a + 36))
        anchor = (anchors.get(uid) or {}).get("frame_green_transition_sec")
        # Expand around uncertain OCR windows to catch shifted speech boundaries.
        center = float(anchor) if anchor is not None and abs(float(anchor) - a) <= 10 else a
        start = max(0, min(a, center) - 9)
        end = max(b, center + 23) + 7
        clip = WORK / f"{uid}_asr.wav"
        run([FFMPEG, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{start:.3f}", "-i", AUDIO,
             "-t", f"{end-start:.3f}", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", clip])
        segments, info = whisper.transcribe(str(clip), language=args.language,
                         beam_size=args.beam, word_timestamps=True,
                         vad_filter=False, condition_on_previous_text=False)
        utterances = []
        for s in segments:
            t = s.text.strip()
            if not t:
                continue
            role, score = classify(t, row)
            utterances.append({
                "role_candidate": role, "text_heard_asr": t, "match_score": score,
                "start_sec": round(start + s.start, 3),
                "end_sec": round(start + s.end, 3),
                "words": [{"text": w.word, "start_sec":round(start+w.start, 3),
                           "end_sec":round(start+w.end, 3),
                           "probability":round(w.probability, 4)}
                          for w in (s.words or []) if w.start is not None and w.end is not None],
                "status": "ASR_ESTIMATE_NOT_VERIFIED"
            })
        # Separate repeated sentences, but do not infer eight recordings from 5 visual states.
        normal = 0
        for u in utterances:
            if u["role_candidate"] == "czech_sentence":
                normal += 1
                u["occurrence"] = normal
        results[uid] = {
            "id":uid, "czech":row.get("czech_original"), "mongolian":row.get("mongolian_word"),
            "czech_sentence":row.get("czech_sentence_original"),
            "mongolian_sentence":row.get("mongolian_sentence"),
            "rough_ocr_start_sec":a, "rough_ocr_end_sec":b,
            "frame_green_transition_sec":anchor,
            "segment_start_sec":round(start,3), "segment_end_sec":round(end,3),
            "model":args.model, "device":args.device,
            "verified":False, "utterances":utterances
        }
        atomic_json(CANDIDATES, results)
        if not args.keep_wav:
            clip.unlink(missing_ok=True)
        matched = sum(u["role_candidate"]!="unclassified" for u in utterances)
        print(f"{idx:03d}/{len(data):03d} {uid}: {len(utterances)} utterances, {matched} Czech matches",flush=True)
    print("Candidate file:", CANDIDATES)
    print("These timings are NOT verified. Use RUN.cmd review.")

def video_segment_cut(start, end, fmt="wav"):
    # For waveform-exact output, use lossless WAV; MP3 adds encoder padding.
    start=max(0.0,float(start));end=float(end)
    if end <= start or end-start>90:
        raise ValueError("Invalid segment times")
    cmd=[FFMPEG, "-nostdin", "-hide_banner","-loglevel","error",
         "-ss",f"{start:.3f}","-i",AUDIO,"-t",f"{end-start:.3f}"]
    if fmt=="wav":
        cmd+=["-ac","1","-ar","44100","-c:a","pcm_s16le","-f","wav","-"]
    else:
        cmd+=["-ac","1","-codec:a","libmp3lame","-q:a","3","-f","mp3","-"]
    return run(cmd,raw=True)

def review(args):
    from flask import Flask, request, jsonify, Response, send_file, render_template_string
    app=Flask(__name__)
    lock=threading.Lock()
    template=r'''<!doctype html><html lang="mn"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Czech800 Alignment QA</title><style>
body{font:15px system-ui;background:#101827;color:#e6edf8;margin:0}
header{position:sticky;top:0;background:#182438;padding:14px 20px;z-index:5;border-bottom:1px solid #32415d}
h1{font-size:20px;margin:0 0 7px}small{color:#b1c3db}input,select,button{font:inherit;padding:8px;background:#202f46;color:#eaf0ff;border:1px solid #4d6284;border-radius:6px}
button{cursor:pointer}button:hover{background:#304e7c}button.approve{background:#165f50}
main{max-width:1150px;margin:18px auto;padding:0 14px}section{padding:14px;margin:16px 0;border:1px solid #374a67;border-radius:10px;background:#1b2940}
.bad{color:#ffc483}.good{color:#9ce8b9}.row{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.row>*{flex:none}
.item{padding:10px 4px;border-top:1px solid #40506a}
.meta{font-weight:bold}.full{width:100%}.reading{color:#b8cedd}input[type=number]{width:110px}
mark{background:#304a5a;color:#eaf0ff}video{max-width:100%;width:560px;max-height:270px}
.note{font-size:12px;color:#b7c5d7}.status{font-size:12px}
</style></head><body>
<header><h1>Czech800 — дуудлагын хугацаа шалгах</h1><small>Текст: Google Drive • ASR: Faster-Whisper • Эх видео/аудио: D:\Czech800\raw • Миллисекундийн бичиглэл ≠ 1ms баталгаатай алдаа</small>
<div class="row"><label>ID <input id="search" value="" placeholder="cz_0001"/></label>
<button onclick="reload()">Шинэчлэх</button><label><input id="only" type="checkbox"/> Зөвхөн шалгаагүй</label>
<span id="counter"></span></div></header>
<main><video id="video" controls preload="metadata" src="/video"></video><div id="items"></div></main>
<script>
const el=id=>document.getElementById(id);
function esc(x){return String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
let rows={};
async function reload(){rows=await (await fetch("/api/items")).json();render();}
function render(){
const filter=el('search').value.toLowerCase().trim();
const keys=Object.keys(rows).filter(k=>(!filter||(k+" "+(rows[k].czech||"")).toLowerCase().includes(filter))&&(!el("only").checked||!rows[k].verified));
el('counter').textContent=keys.length+" бичлэгийн карт";
el('items').innerHTML=keys.map(k=>{
 const r=rows[k];
 return '<section><div class="row"><b>'+esc(k)+' — '+esc(r.czech)+'</b><span class="'+(r.verified?'good':'bad')+'">'+(r.verified?'REVIEWED':'NOT VERIFIED')+'</span><button onclick="seek('+Number(r.rough_ocr_start_sec)+')">Видеоноос харах</button></div>'
 +'<p>'+esc(r.mongolian)+'</p><p>'+esc(r.czech_sentence)+'</p><p class="reading">'+esc(r.mongolian_sentence)+'</p>'
 +(r.utterances||[]).map((u,i)=>'<div class="item"><div class="row"><span class="meta">#'+i+' • '+esc(u.role_candidate)+' ('+esc(u.match_score)+'%)</span><span class="status">'+esc(u.status||'candidate')+'</span></div>'
 +'<div class="reading">'+esc(u.text_heard_asr)+'</div>'
 +'<div class="row"><label>Start <input type="number" step=".001" id="s_'+k+'_'+i+'" value="'+u.start_sec+'"/></label><label>End <input type="number" step=".001" id="e_'+k+'_'+i+'" value="'+u.end_sec+'"/></label>'
 +'<select id="t_'+k+'_'+i+'">'+['czech_word','czech_word_syllabic','czech_sentence','czech_sentence_slow','english_word','english_sentence','skip','unclassified'].map(t=>'<option value="'+t+'" '+((u.role_reviewed||u.role_candidate)===t?'selected':'')+'>'+t+'</option>').join('')+'</select>'
 +'<button onclick="play(\''+k+'\','+i+')">Сонсох</button><button onclick="seek('+u.start_sec+')">Видео</button><button onclick="save(\''+k+'\','+i+',false)">Хадгалах</button><button class="approve" onclick="save(\''+k+'\','+i+',true)">Шалгаад батлах</button></div></div>').join('')
 +'</section>';
}).join('');
}
function seek(t){const v=el('video');v.currentTime=Number(t);v.play().catch(()=>{});}
function play(k,i){const s=+el('s_'+k+'_'+i).value,e=+el('e_'+k+'_'+i).value;
if(e<=s){alert('End > Start байх ёстой');return;}
new Audio('/audio?start='+s+'&end='+e).play().catch(e=>alert(e.message));}
async function save(k,i,approve){
 const start=+el('s_'+k+'_'+i).value,end=+el('e_'+k+'_'+i).value,role=el('t_'+k+'_'+i).value;
 if(!(start>=0&&end>start&&end-start<=90)){alert('Хугацааны утга буруу');return;}
 const resp=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:k,index:i,start,end,role,approve})});
 if(!resp.ok){alert(await resp.text());return;}
 await reload();
}
el('search').oninput=render;el('only').onchange=render;reload();
</script></body></html>'''
    @app.get("/")
    def home():
        return render_template_string(template)
    @app.get("/api/items")
    def items():
        return jsonify(read_json(CANDIDATES, {}))
    @app.get("/video")
    def video():
        return send_file(VIDEO, mimetype="video/mp4", conditional=True)
    @app.get("/audio")
    def audio():
        st=request.args.get("start",type=float)
        en=request.args.get("end",type=float)
        if st is None or en is None or st<0 or en<=st or en-st>90:
            return "Bad times",400
        return Response(video_segment_cut(st,en,"wav"),mimetype="audio/wav")
    @app.post("/api/review")
    def update():
        body=request.get_json(force=True)
        uid=str(body.get("id",""))
        idx=int(body.get("index",-1))
        st=float(body.get("start",0))
        en=float(body.get("end",0))
        role=str(body.get("role",""))
        if st<0 or en<=st or en-st>90:
            return "Invalid times",400
        if role not in {"czech_word","czech_word_syllabic","czech_sentence","czech_sentence_slow",
                        "english_word","english_sentence","skip","unclassified"}:
            return "Invalid role",400
        with lock:
            content=read_json(CANDIDATES,{})
            if uid not in content or idx<0 or idx>=len(content[uid].get("utterances",[])):
                return "Unknown item",404
            u=content[uid]["utterances"][idx]
            u.update({"reviewed_start_sec":round(st,3),"reviewed_end_sec":round(en,3),
                      "role_reviewed":role,
                      "verified":bool(body.get("approve")),
                      "status":"HUMAN_REVIEWED" if body.get("approve") else "EDITED_NOT_VERIFIED",
                      "reviewed_at":datetime.now(timezone.utc).isoformat()})
            content[uid]["verified"]=all(x.get("verified") or x.get("role_reviewed")=="skip" for x in content[uid]["utterances"])
            atomic_json(CANDIDATES,content)
        return jsonify({"ok":True})
    print("OPEN http://127.0.0.1:8765 in browser; Ctrl+C to stop")
    app.run(host="127.0.0.1",port=8765,debug=False,threaded=True)

def export(args):
    records=read_json(CANDIDATES,{})
    if not records:
        raise RuntimeError("No candidate data. Run RUN.cmd transcribe --limit 20")
    outcsv=OUTPUT/"verified_segments.csv"
    manifest=[]
    for uid, row in records.items():
        for index,u in enumerate(row.get("utterances",[])):
            if not u.get("verified"):
                continue
            role=u.get("role_reviewed",u.get("role_candidate"))
            if role in ("skip","unclassified"):
                continue
            start=u.get("reviewed_start_sec")
            end=u.get("reviewed_end_sec")
            if start is None or end is None:
                continue
            name=f"{uid}_{index:02d}_{role}.wav"
            destination=OUTPUT/name
            if not destination.exists() or args.force:
                run([FFMPEG,"-y","-nostdin","-hide_banner","-loglevel","error",
                     "-ss",f"{start:.3f}","-i",AUDIO,"-t",f"{end-start:.3f}",
                     "-ac","1","-ar","44100","-c:a","pcm_s16le",destination])
            manifest.append({"id":uid,"czech":row["czech"],"mongolian":row["mongolian"],
                             "role":role,"start_sec":start,"end_sec":end,"path":str(destination),
                             "verified":True,"source":"local_CzechClass101_recording",
                             "redistribution_rights":"NOT_CONFIRMED"})
            print("WAV",destination.name)
    with outcsv.open("w",encoding="utf-8-sig",newline="") as f:
        cols=["id","czech","mongolian","role","start_sec","end_sec","path","verified",
              "source","redistribution_rights"]
        writer=csv.DictWriter(f,fieldnames=cols)
        writer.writeheader();writer.writerows(manifest)
    atomic_json(OUTPUT/"verified_segments.json",manifest)
    print("Exported",len(manifest),"QA-approved lossless WAV clips")
    print("Copyright: private processing; do not publish CzechClass101 audio without rights.")

def main():
    parser=argparse.ArgumentParser(description="Czech800 video + speech timing workbench")
    cmds=parser.add_subparsers(dest="command",required=True)
    cmds.add_parser("check")
    cmds.add_parser("sync")
    sp=cmds.add_parser("scan")
    sp.add_argument("--limit",type=int,default=20,help="First N entries; use 0 for all")
    sp=cmds.add_parser("transcribe")
    sp.add_argument("--limit",type=int,default=20,help="First N entries; use 0 for all")
    sp.add_argument("--start",type=int,default=0)
    sp.add_argument("--model",default="medium")
    sp.add_argument("--language",default="cs")
    sp.add_argument("--device",default="cuda")
    sp.add_argument("--compute",default="float16")
    sp.add_argument("--beam",type=int,default=5)
    sp.add_argument("--force",action="store_true")
    sp.add_argument("--keep-wav",action="store_true")
    cmds.add_parser("review")
    sp=cmds.add_parser("export")
    sp.add_argument("--force",action="store_true")
    args=parser.parse_args()
    setup()
    return {"check":check,"sync":sync,"scan":scan,"transcribe":transcribe,
            "review":review,"export":export}[args.command](args)

if __name__=="__main__":
    try:
        main()
    except Exception as error:
        import traceback
        traceback.print_exc()
        sys.exit(1)
