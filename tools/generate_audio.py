import asyncio
import json
import re
from pathlib import Path
import edge_tts

VOICE = "cs-CZ-AntoninNeural"
ROOT = Path(__file__).resolve().parents[1]
PHRASES = json.loads((ROOT / "audio" / "phrases.json").read_text(encoding="utf-8"))
OUT = ROOT / "audio"
OUT.mkdir(exist_ok=True)

def slug(text: str) -> str:
    text = text.lower().strip()
    table = str.maketrans({"á":"a","č":"c","ď":"d","é":"e","ě":"e","í":"i","ň":"n","ó":"o","ř":"r","š":"s","ť":"t","ú":"u","ů":"u","ý":"y","ž":"z"})
    text = text.translate(table)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")

async def main():
    for phrase in PHRASES:
        target = OUT / f"{slug(phrase)}.mp3"
        if target.exists():
            print(f"skip {target.name}")
            continue
        print(f"create {target.name}")
        communicate = edge_tts.Communicate(phrase, VOICE, rate="-8%")
        await communicate.save(str(target))

if __name__ == "__main__":
    asyncio.run(main())
