# -*- coding: utf-8 -*-
"""Local Czech800 trimmed-6h QA viewer. No automatic approval and no original media upload."""
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from flask import Flask, request, jsonify, send_file, Response, render_template_string

ROOT = Path(r"D:\Czech800")
DATA = ROOT / "data"
WORK = ROOT / "work" / "trimmed6h_preview"
MKV = ROOT / "raw" / "Czech800_tairsan.mkv"
INDEX = DATA / "trimmed6h_index_909.json"
TARGETS = DATA / "czech_810_alignment_targets.json"
REVIEW = DATA / "trimmed6h_reviewed.json"
AUTO = DATA / "trimmed6h_ctc_candidates.json"
WORK.mkdir(parents=True, exist_ok=True)
for path in (MKV, INDEX, TARGETS):
    if not path.exists():
        raise SystemExit("Missing required file: " + str(path))
timeline = json.loads(INDEX.read_text(encoding="utf-8-sig"))
targets_raw = json.loads(TARGETS.read_text(encoding="utf-8-sig"))
targets = {r["id"]: r for r in targets_raw["rows"]}
cues = {r["id"]: r for r in timeline["entries"]}
if not cues or not targets:
    raise SystemExit("No index targets loaded")
lock = threading.Lock()
app = Flask(__name__)

def load_review():
    if REVIEW.exists():
        return json.loads(REVIEW.read_text(encoding="utf-8-sig"))
    return {}

def load_auto():
    if AUTO.exists():
        return json.loads(AUTO.read_text(encoding="utf-8-sig")).get("candidates", {})
    return {}

def save_review(items):
    tmp = REVIEW.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, REVIEW)

def ffmpeg(args):
    p = subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error"] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", errors="replace")[-900:])
    return p.stdout

page = r"""<!DOCTYPE html><html lang="mn"><head><meta charset="utf-8"/>
<title>Czech800 — 6h timeline review</title><meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body{margin:0;background:#101827;color:#e9f0fc;font:15px system-ui}
header{position:sticky;top:0;z-index:3;background:#1d2c42;padding:14px;border-bottom:1px solid #3a4b68}
main{max-width:1080px;margin:18px auto;padding:0 12px}
input,button{background:#223653;color:#eef3ff;border:1px solid #55718f;border-radius:5px;padding:7px;font:inherit}
button{cursor:pointer;margin:4px}
button:hover{background:#315778}
.card{background:#1b2a41;border:1px solid #42546d;border-radius:9px;margin:14px 0;padding:14px}
.meta{font-size:12px;color:#adc2d9}.danger{color:#f6c187}
.small{font-size:13px;color:#bdd0e3}label{margin-right:8px}
video{width:100%;max-width:680px;max-height:350px;background:#000}
.number{width:115px}#status{margin:12px}span.badge{padding:4px 8px;border:1px solid #607c9c;border-radius:9px;font-size:12px}
</style></head><body><header><b>Czech800 — тайрагдсан 6:45:17 MKV, ярианы хугацаа</b>
<div class="small">909 дэлгэцийн SRT хүрээ + 810 Чех карт + Colab ASR 4046 сегмент. Хугацаа одоогоор баталгаажаагүй.</div>
<div><input id="query" placeholder="cz_0001 / nadějný"/><button onclick="loadCards()">Хайх / шинэчлэх</button><button onclick="setQuery('!review')">Зөвхөн шалгах</button><button onclick="setQuery('!high')">CTC боломжийн</button><button onclick="setQuery('')">Бүгд</button><span id="status"></span></div></header>
<main><div id="cards"></div></main>
<script>
function esc(v){return String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
let list=[];
function setQuery(v){document.getElementById("query").value=v;loadCards();}
function useCTC(id,j,st,en){document.getElementById("st_"+id+"_"+j).value=st;document.getElementById("en_"+id+"_"+j).value=en;}
async function loadCards(){
  const p=new URLSearchParams({query:document.getElementById("query").value,limit:40});
  const response=await fetch("/api/cards?"+p.toString());
  const data=await response.json();list=data.cards;
  document.getElementById("status").textContent=data.total+" олдсон, эхний "+list.length+" харагдаж байна";
  const host=document.getElementById("cards");host.innerHTML="";
  for(const r of list){
    const div=document.createElement("section");div.className="card";
    let html='<b>'+esc(r.id)+' — '+esc(r.czech)+'</b> <span class="badge">'+esc(r.match_method)+" "+esc(r.similarity)+'</span>'
      +'<p>'+esc(r.mongolian)+'</p><p>'+esc(r.sentence)+'</p><p class="small">'+esc(r.mongolian_sentence)+'</p>'
      +'<p class="meta">SRT дэлгэцийн хүрээ: '+esc(r.video_start_sec)+'–'+esc(r.video_end_sec)
      +' с (ярианы яг хил биш)</p>';
    if(r.video_start_sec!==null){
      html+='<button onclick="playVideo(\''+r.id+'\')">Видеог үзэх</button><div id="vid_'+r.id+'"></div>';
    }
    if(!r.candidates.length){
      html+='<p class="danger">Энэ өгүүлбэрийн тусдаа ASR хугацаа таараагүй. Дахин alignment шаардлагатай.</p>';
    }
    for(let j=0;j<r.candidates.length;j++){
      const s=r.candidates[j],saved=(r.reviewed||{})[String(j)]||{};
      const stAuto=(r.auto||{})[String(s.segment_id)]||null;
      const start=saved.start_sec==null?(stAuto&&stAuto.start_sec!=null?stAuto.start_sec:s.start_sec):saved.start_sec;
      const end=saved.end_sec==null?(stAuto&&stAuto.end_sec!=null?stAuto.end_sec:s.end_sec):saved.end_sec;
      html+='<div class="small">ASR segment #'+esc(s.segment_id)+' — '+(saved.verified?"сонсож баталсан":"баталгаажаагүй")
        +(stAuto?(' | Чех CTC: '+esc(stAuto.status)+' | score '+esc(stAuto.mean_ctc_score)):' | CTC хараахан тооцоогүй')+'</div>'
        +'<label>Start <input class="number" type="number" step=".001" id="st_'+r.id+'_'+j+'" value="'+start+'"/></label>'
        +'<label>End <input class="number" type="number" step=".001" id="en_'+r.id+'_'+j+'" value="'+end+'"/></label>'
        +'<button onclick="playAudio(\''+r.id+'\','+j+')">Сонсох</button>'
        +'<button onclick="save(\''+r.id+'\','+j+',false)">Хадгалах</button>'
        +'<button onclick="save(\''+r.id+'\','+j+',true)">Сонсож баталсан</button>';
    }
    div.innerHTML=html;host.appendChild(div);
  }
}
async function playVideo(id){
  const d=document.getElementById("vid_"+id);
  if(d.childElementCount){d.innerHTML="";return;}
  d.innerHTML='<p class="small">Эхний удаа MKV-ээс түр MP4 preview үүсгэнэ...</p><video controls preload="none" src="/preview/'+id+'"></video>';
}
function playAudio(id,j){
 const a=Number(document.getElementById("st_"+id+"_"+j).value),b=Number(document.getElementById("en_"+id+"_"+j).value);
 if(!(b>a)){alert("End нь Start-ээс их байх ёстой");return;}
 new Audio("/audio?start="+a+"&end="+b).play().catch(e=>alert(e.message));
}
async function save(id,j,approve){
 const a=Number(document.getElementById("st_"+id+"_"+j).value),b=Number(document.getElementById("en_"+id+"_"+j).value);
 if(!(a>=0&&b>a&&b-a<=90&&b<=24317.049)){alert("Хугацаа буруу");return;}
 if(approve&&!confirm("Дууг бүтнээр нь сонсож, эхлэл/төгсгөлийг өөрөө шалгасан уу?"))return;
 const r=await fetch("/api/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id,index:j,start_sec:a,end_sec:b,verified:approve})});
 if(!r.ok){alert(await r.text());return;}
 await loadCards();
}
document.getElementById("query").addEventListener("keydown",e=>{if(e.key==="Enter")loadCards();});
loadCards();
</script></body></html>"""

@app.get("/")
def home():
    return render_template_string(page)

@app.get("/api/cards")
def api_cards():
    q=request.args.get("query","").strip().lower()
    limit=min(100,max(1,request.args.get("limit",40,type=int)))
    found=[]
    reviewed=load_review()
    auto=load_auto()
    for uid,t in targets.items():
        c=cues.get(uid,{})
        candidates=c.get("asr_exact_sentence_candidates",[])
        auto_for={str(x["segment_id"]):auto.get(uid+":"+str(x["segment_id"])) for x in candidates if uid+":"+str(x["segment_id"]) in auto}
        if q == "!review":
            if c.get("match_method")=="NOT_MAPPED" or not candidates or not auto_for:
                pass
            elif all(x and x.get("status")=="HIGH_CONFIDENCE_CANDIDATE_NOT_VERIFIED" for x in auto_for.values()) and len(auto_for)==len(candidates):
                continue
        elif q == "!high":
            if not any(x and x.get("status")=="HIGH_CONFIDENCE_CANDIDATE_NOT_VERIFIED" for x in auto_for.values()):
                continue
        elif q and q not in (uid+" "+str(t.get("czech_original",""))+" "+str(t.get("mongolian_word",""))).lower():
            continue
        found.append({
            "id":uid,"czech":t.get("czech_original",""),"mongolian":t.get("mongolian_word",""),
            "sentence":t.get("czech_sentence_original",""),"mongolian_sentence":t.get("mongolian_sentence",""),
            "match_method":c.get("match_method","NOT_MAPPED"),"similarity":c.get("text_similarity"),
            "video_start_sec":c.get("video_start_sec"),"video_end_sec":c.get("video_end_sec"),
            "candidates":candidates,
            "auto":auto_for,
            "reviewed":reviewed.get(uid,{})
        })
    return jsonify({"total":len(found),"cards":found[:limit]})

@app.get("/preview/<uid>")
def preview(uid):
    if not re.fullmatch(r"cz_\d{4}",uid) or uid not in cues:
        return "Unknown ID",404
    c=cues[uid]
    st=c.get("video_start_sec");en=c.get("video_end_sec")
    if st is None or en is None:
        return "No subtitle anchor",404
    p=WORK/(uid+".mp4")
    if not p.exists() or p.stat().st_size<1024:
        begin=max(0,float(st)-16)
        length=min(60,float(en)-begin+2)
        tmp=WORK/(uid+".partial.mp4")
        cmd=["-y","-ss",f"{begin:.3f}","-i",str(MKV),"-t",f"{length:.3f}",
             "-vf","scale=720:-2","-c:v","libx264","-preset","ultrafast","-crf","30",
             "-c:a","aac","-b:a","96k","-movflags","+faststart",str(tmp)]
        ffmpeg(cmd)
        os.replace(tmp,p)
    return send_file(p,mimetype="video/mp4",conditional=True)

@app.get("/audio")
def audio():
    st=request.args.get("start",type=float);en=request.args.get("end",type=float)
    if st is None or en is None or not (0<=st<en<=24317.049) or en-st>90:
        return "Invalid audio interval",400
    try:
        wav=ffmpeg(["-ss",f"{st:.3f}","-i",str(MKV),"-t",f"{en-st:.3f}",
                    "-vn","-ar","16000","-ac","1","-c:a","pcm_s16le","-f","wav","-"])
        return Response(wav,mimetype="audio/wav")
    except Exception as e:
        return str(e),500

@app.post("/api/review")
def api_review():
    data=request.get_json(force=True) or {}
    uid=data.get("id")
    i=data.get("index")
    if uid not in cues or type(i) is not int:
        return "Bad review id",400
    cand=cues[uid].get("asr_exact_sentence_candidates",[])
    if i<0 or i>=len(cand):
        return "Candidate missing",400
    try:
        st=float(data["start_sec"]);en=float(data["end_sec"])
    except (ValueError,KeyError,TypeError):
        return "Invalid times",400
    if not (0<=st<en<=24317.049 and en-st<=90):
        return "Invalid interval",400
    with lock:
        doc=load_review()
        doc.setdefault(uid,{})[str(i)]={"start_sec":round(st,3),"end_sec":round(en,3),
                 "verified":data.get("verified") is True,"source_segment_id":cand[i]["segment_id"]}
        save_review(doc)
    return jsonify({"ok":True})

if __name__=="__main__":
    print("Czech800 trimmed video:",MKV)
    print("View: http://127.0.0.1:8766")
    app.run(host="127.0.0.1",port=8766,debug=False,threaded=True)
