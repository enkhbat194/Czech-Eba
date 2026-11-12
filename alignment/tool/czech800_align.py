# -*- coding: utf-8 -*-
"""Optional Czech CTC forced alignment, strictly candidate times.
Requires a separate Python environment with WhisperX. Does not modify audio.
"""
import argparse
import json
import subprocess
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(r"D:\Czech800")
AUDIO=ROOT/"raw"/"Czech800.m4a"
DATA=ROOT/"data"/"alignment_candidates.json"
WORK=ROOT/"work"/"ctc"
MODELS=ROOT/"models"/"align"
TARGETS=ROOT/"data"/"czech_810_alignment_targets.json"

def save(obj):
    temp=DATA.with_suffix(".tmp")
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(temp,DATA)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=20)
    parser.add_argument("--start",type=int,default=1)
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    if not DATA.exists():
        raise RuntimeError("Run START_PILOT.cmd first to seed ASR candidate times")
    doc=json.loads(DATA.read_text(encoding="utf-8"))
    targets=json.loads(TARGETS.read_text(encoding="utf-8"))
    targets={r["id"]:r for r in targets["rows"]}
    WORK.mkdir(parents=True,exist_ok=True)
    MODELS.mkdir(parents=True,exist_ok=True)
    import whisperx
    print("Loading Czech wav2vec2 CTC model on CPU...",flush=True)
    model,metadata=whisperx.load_align_model(language_code="cs",device="cpu",model_dir=str(MODELS))
    count=0
    for uid,row in sorted(doc.items()):
        number=int(uid.split("_")[-1])
        if number<args.start or number>=args.start+args.limit:
            continue
        target=targets.get(uid,{})
        for i,u in enumerate(row.get("utterances",[])):
            if u.get("role_candidate")!="czech_sentence":
                continue
            if u.get("verified"):
                continue
            if u.get("aligned_words") and not args.force:
                continue
            expected=str(target.get("czech_sentence_original") or "").strip()
            if not expected:
                continue
            # The CTC model needs a short, likely-correct transcript from VIDEO,
            # not a 7-hour audio file or an AI-invented corrected sentence.
            st=max(0.0,float(u["start_sec"])-0.55)
            en=float(u["end_sec"])+0.55
            if en<=st or en-st>90:
                continue
            wav=WORK/f"{uid}_{i}.wav"
            subprocess.run(["ffmpeg","-y","-nostdin","-hide_banner","-loglevel","error",
                            "-ss",f"{st:.3f}","-i",str(AUDIO),"-t",f"{en-st:.3f}",
                            "-ar","16000","-ac","1",str(wav)],check=True)
            try:
                transcript=[{"start":0.0,"end":en-st,"text":expected}]
                outcome=whisperx.align(transcript,model,metadata,str(wav),"cpu",
                                       return_char_alignments=False)
                aligned=outcome.get("word_segments",[])
                valid=[w for w in aligned if w.get("start") is not None and w.get("end") is not None]
                if not valid:
                    print("UNRESOLVED",uid,i,"no aligned words")
                    u["alignment_status"]="NO_VALID_WORDS"
                    continue
                start=round(st+float(valid[0]["start"]),3)
                end=round(st+float(valid[-1]["end"]),3)
                if not (0<=start<end<=en+0.5):
                    print("UNRESOLVED",uid,i,"invalid CTC interval")
                    continue
                u["aligned_start_sec"]=start
                u["aligned_end_sec"]=end
                u["aligned_words"]=[
                    {"word":w.get("word",""),"start_sec":round(st+float(w["start"]),3),
                     "end_sec":round(st+float(w["end"]),3),
                     "score":w.get("score")} for w in valid]
                u["alignment_status"]="CZECH_CTC_CANDIDATE_NOT_VERIFIED"
                u["alignment_model"]="comodoro/wav2vec2-xls-r-300m-cs-250"
                u["alignment_run_at"]=datetime.now(timezone.utc).isoformat()
                count+=1
                print("CTC CANDIDATE",uid,i,f"{start:.3f}-{end:.3f}",flush=True)
            except Exception as error:
                u["alignment_status"]="FAILED"
                u["alignment_error"]=str(error)[:350]
                print("FAILED",uid,i,error,flush=True)
            finally:
                wav.unlink(missing_ok=True)
                save(doc)
        save(doc)
    print("CTC-aligned candidates:",count)
    print("Review times and speech yourself; 0.001 display precision is not +/-1ms measurement.")

if __name__=="__main__":
    main()
