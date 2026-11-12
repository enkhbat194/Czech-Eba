# Czech800 — audio/video alignment workspace (draft)

## Purpose
Use the original 7h26m56.192s CzechClass101 MP4 and M4A with pre-existing Czech text and Mongolian translations to determine **speech** onset/offset per vocabulary word and sentence. Export candidate times and finally QA-approved clips. This workspace is **not yet a completed alignment dataset**.

## Confirmed environment on user's Windows 11 laptop
- NVIDIA RTX 2070 Super 8GB; driver 621.14; CTranslate2 4.9.0 GPU inference confirmed.
- Python 3.11 virtual environment: `D:\Czech800\.venv`.
- FFmpeg 9.0.1; source files:
  - `D:\Czech800\raw\Czech800.mp4` (1,814,243,201 bytes; H.264 + AAC)
  - `D:\Czech800\raw\Czech800.m4a` (433,684,262 bytes; AAC)
  - Both formats report duration 26,816.191565 s. Equal duration is **not** proof of identical audio sync.
- CUDA library locations must be added to CMD PATH for CTranslate2, as already tested:
  `D:\Czech800\.venv\Lib\site-packages\nvidia\cublas\bin` and
  `D:\Czech800\.venv\Lib\site-packages\nvidia\cudnn\bin` and
  `D:\Czech800\.venv\Lib\site-packages\nvidia\cuda_runtime\bin`.

## Data sources
- `data/czech_810_alignment_targets.json`: 810 Drive OCR-derived ID rows with original/corrected Czech words and sentences and Mongolian translations. `approximate_ocr_start_sec` and `approximate_ocr_end_sec` are **not precise speech boundaries**; the 810 entries may include OCR-fragment duplicates.
- `pilot_first20_czech_sentences.srt`: 25 exact Czech example-sentence utterance matches from existing Whisper large-v3 word-time candidates, spanning 19 of the first 20 IDs. Repeated Czech sentences are retained as separate cues. Not all Czech speech from these IDs is present; words and English audio are excluded.
- `pilot_first20_czech_sentences.csv`: cue provenance with ID and tentative start/end.

## Existing ready-made tools
1. **Subtitle Edit v5.4.0 (Windows x64)**: official https://github.com/SubtitleEdit/subtitleedit/releases/tag/v5.4.0
   - Video → Open video… → select `Czech800.mp4`.
   - File → Open → select `pilot_first20_czech_sentences.srt`.
   - Tools → Improve time codes (forced alignment)… → choose the **Czech wav2vec2 aligner** (downloads in Crisp ASR when needed).
   - Check the list's disputed and large moves against the original and aligned waveform.
   - Note: this tool optimizes **subtitle display** timing (including reading duration), which may differ from exact audio clip boundaries. Do not directly export final word clips from unreviewed SRT time codes.
2. **Montreal Forced Aligner Czech model**: https://huggingface.co/MontrealCorpusTools/czech_mfa ; use matching Czech speech-only utterances to generate phone/word boundary candidates.
3. **PySceneDetect + OCR** for visual green-card/teacher sentence transitions; needed as additional source anchors, not as phoneme boundaries.

## Required validation before automatic processing of all 800 words
- At 3+ locations (beginning, middle, end), measure MP4 and M4A audio offset by waveform correlation (not duration equality).
- From pilot 20 cards, use video transitions and Czech/English screen text to resolve per-card membership. The intro and advertisement breaks must not become word clips.
- Align Czech sentences using matching **original spoken** transcript, not the AI-corrected sentence if different.
- Separate individual word normal/syllabic readings, normal Czech sentence, slow Czech sentence, and English speech by their actual audio roles. Five visual screen states do not imply exactly eight spoken files.
- Refine voice boundaries with waveform/VAD; remove chime, background sounds and next-card words; manually listen to flagged low-confidence cuts.
- Store `start_sec`, `end_sec` to three decimals as a timestamp **representation**, not a claim of 1ms measured accuracy.
- Keep candidates `verified:false` until audio/video QA; release exports only after verified QA.
- Confirm rights/licensing before redistributing CzechClass101 recordings in a public app.

## Current status
GPU works; rough Czech+Mongolian corpus staged in GitHub; 19/20 pilot IDs have exact-ASR-text Czech sentence candidate cues. **No final boundaries or 6,400 redistributable clips have been verified or exported.**
