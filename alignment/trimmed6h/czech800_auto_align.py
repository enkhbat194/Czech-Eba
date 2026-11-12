# -*- coding: utf-8 -*-
"""Czech800 trimmed-MKV automatic Czech sentence CTC alignment.
Reads local 909-cue SRT index + prior 4046-segment exact text matches.
Does not overwrite manually reviewed intervals, auto-verify or upload media.
Results are checkpoints; rerun after interruption to resume.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Czech800")
SOURCE = ROOT / "raw" / "Czech800_tairsan.mkv"
DATA = ROOT / "data"
INDEX = DATA / "trimmed6h_index_909.json"
TARGETS = DATA / "czech_810_alignment_targets.json"
OUTPUT = DATA / "trimmed6h_ctc_candidates.json"
REPORT = DATA / "trimmed6h_ctc_report.json"
WAV_DIR = ROOT / "work" / "trimmed6h_ctc"
MODEL_DIR = ROOT / "models" / "align"
DURATION = 24317.049

def atomic_json(path, obj):
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp,path)

def wav_cut(start,end,path):
    length=end-start
    if not (0<=start<end<=DURATION and 0.3<=length<=90):
        raise ValueError("Invalid candidate range: %.3f-%.3f"%(start,end))
    subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error",
      "-ss","%.3f"%start,"-i",str(SOURCE),"-t","%.3f"%length,
      "-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(path)],check=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--start",type=int,default=1,help="First Czech target number")
    parser.add_argument("--limit",type=int,default=20,help="Number of targets (0 = all remaining)")
    parser.add_argument("--force",action="store_true",help="Recompute already checkpointed candidates")
    args=parser.parse_args()
    for p in (SOURCE,INDEX,TARGETS):
        if not p.exists(): raise SystemExit("Missing: "+str(p))
    import whisperx
    index=json.loads(INDEX.read_text(encoding="utf-8-sig"))
    targets={r["id"]:r for r in json.loads(TARGETS.read_text(encoding="utf-8-sig"))["rows"]}
    rows={r["id"]:r for r in index["entries"]}
    WAV_DIR.mkdir(parents=True,exist_ok=True)
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    data=json.loads(OUTPUT.read_text(encoding="utf-8-sig")) if OUTPUT.exists() else {
      "version":1,"source":"Czech800_tairsan.mkv","duration_sec":DURATION,
      "model":"whisperx Czech CTC","candidates":{}}
    if data.get("source")!="Czech800_tairsan.mkv":
        raise SystemExit("Output contains different source media")
    limit=args.limit if args.limit>0 else 811
    selected=[("cz_%04d"%i,rows.get("cz_%04d"%i)) for i in range(args.start,min(811,args.start+limit))]
    selected=[(uid,r) for uid,r in selected if r]
    todo=[]
    for uid,r in selected:
        for j,c in enumerate(r.get("asr_exact_sentence_candidates") or []):
            key=uid+":"+str(c["segment_id"])
            if key not in data["candidates"] or args.force:
                todo.append((uid,key,r,c))
    print("Selected",len(selected),"cards; CTC tasks:",len(todo),flush=True)
    if not todo:
        print("Already checkpointed. Use --force only if you intend to recompute.")
    if todo:
        print("Loading Czech-specific CTC aligner on CPU; first run may download model...",flush=True)
        model,metadata=whisperx.load_align_model(language_code="cs",device="cpu",model_dir=str(MODEL_DIR))
    for n,(uid,key,row,c) in enumerate(todo,1):
        expected=str(targets.get(uid,{}).get("czech_sentence_original") or
                     targets.get(uid,{}).get("czech_sentence_corrected") or "").strip()
        sr=row.get("video_start_sec");er=row.get("video_end_sec")
        a,b=float(c["start_sec"]),float(c["end_sec"])
        result={"id":uid,"segment_id":c["segment_id"],"asr_start_sec":a,"asr_end_sec":b,
           "screen_start_sec":sr,"screen_end_sec":er,"expected":expected,
           "status":"NEEDS_REVIEW","verified":False,
           "updated_at":datetime.now(timezone.utc).isoformat()}
        wav=WAV_DIR/(uid+"_"+str(c["segment_id"])+".wav")
        try:
            if not expected or sr is None or er is None:
                result["reason"]="MISSING_TEXT_OR_VIDEO_WINDOW"
            else:
                # A large ASR segment often includes a Czech word, English translation,
                # and the target Czech sentence. The on-screen SRT start is a useful
                # localizer, but is NOT the speech start.
                lo=max(0,a-0.8)
                hi=min(DURATION,b+0.8)
                if b-a>12 and float(sr)-a>4:
                    lo=max(lo,float(sr)-1.8)
                hi=min(hi,float(er)+2.0)
                if hi-lo<0.8:
                    lo=max(0,a-0.8);hi=min(DURATION,b+0.8)
                if hi-lo>35:
                    result["reason"]="ASR_WINDOW_TOO_LONG"
                else:
                    wav_cut(lo,hi,wav)
                    outcome=whisperx.align([{"start":0.0,"end":hi-lo,"text":expected}],
                        model,metadata,str(wav),"cpu",return_char_alignments=False)
                    word_segments=outcome.get("word_segments") or []
                    valid=[w for w in word_segments if w.get("start") is not None and w.get("end") is not None
                            and float(w["end"])>float(w["start"])]
                    if not valid:
                        result["reason"]="CTC_NO_WORDS"
                    else:
                        aligned_start=round(lo+float(valid[0]["start"]),3)
                        aligned_end=round(lo+float(valid[-1]["end"]),3)
                        scores=[float(w["score"]) for w in valid if w.get("score") is not None]
                        avg_score=round(statistics.mean(scores),3) if scores else None
                        expected_count=len(expected.split())
                        coverage=min(1.0,len(valid)/max(expected_count,1))
                        strong=(coverage>=0.85 and len(scores)>=max(1,expected_count-1)
                                and avg_score is not None and avg_score>=0.85
                                and aligned_start>=lo-0.01 and aligned_end<=hi+0.01
                                and aligned_start<aligned_end and aligned_end-aligned_start<25
                                and aligned_start>=a-1.6 and aligned_end<=b+1.6)
                        result.update({
                          "start_sec":aligned_start,"end_sec":aligned_end,
                          "aligned_words":[{"word":w.get("word",""),
                             "start_sec":round(lo+float(w["start"]),3),
                             "end_sec":round(lo+float(w["end"]),3),
                             "score":w.get("score")} for w in valid],
                          "mean_ctc_score":avg_score,"word_coverage":round(coverage,3),
                          "status":"HIGH_CONFIDENCE_CANDIDATE_NOT_VERIFIED" if strong else "NEEDS_REVIEW",
                          "reason":"CTC_AND_TEXT_PASS" if strong else "WEAK_CTC_OR_BOUNDARY_DISAGREEMENT"
                        })
        except Exception as exc:
            result["status"]="ERROR"
            result["reason"]=str(exc)[:400]
        finally:
            wav.unlink(missing_ok=True)
            data["candidates"][key]=result
            atomic_json(OUTPUT,data)
        print("[%d/%d] %s: %s | %s"%(n,len(todo),uid,result["status"],result.get("reason","")),flush=True)
    vals=list(data["candidates"].values())
    status={}
    for r in vals:status[r["status"]]=status.get(r["status"],0)+1
    report={"total_candidates":len(vals),"by_status":status,
       "total_cards_with_ctc":len(set(r["id"] for r in vals)),
       "note":"HIGH_CONFIDENCE = model's self consistency, not verified clean audio cuts."}
    atomic_json(REPORT,report)
    print("CTC RESULT:",json.dumps(report,ensure_ascii=False),flush=True)
    print("Saved:",OUTPUT,flush=True)

if __name__=="__main__":main()
