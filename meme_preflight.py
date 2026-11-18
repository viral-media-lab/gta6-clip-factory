#!/usr/bin/env python3
"""Discover, validate and create a contact sheet for relevant meme cutaways."""
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw
import make_short

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"


def main():
    subprocess.run([sys.executable, str(ROOT / "meme_finder.py")], check=True)
    clips = make_short.get_meme_clips()
    if len(clips) < 2:
        raise RuntimeError(
            f"Meme preflight failed: only {len(clips)} relevant clips; need at least 2"
        )

    manifest_path = ROOT / "assets" / "memes" / "sources.json"
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_file = {record.get("file"): record for record in records}
    frames = []
    for index, (path, duration, title) in enumerate(clips):
        record = by_file.get(path.name, {})
        if not record.get("license") or not record.get("source_page"):
            raise RuntimeError(f"Missing license/source metadata: {path.name}")

        frame_path = OUTPUT / f"meme_frame_{index:02}.jpg"
        timestamp = min(1.0, max(0.0, duration / 2))
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{timestamp:.2f}", "-i", str(path),
            "-frames:v", "1",
            "-vf", "scale=360:640:force_original_aspect_ratio=decrease,"
                   "pad=360:640:(ow-iw)/2:(oh-ih)/2",
            str(frame_path)
        ], check=True)
        frames.append((frame_path, title))
        print(
            f"MEME_CANDIDATE: {path.name} | {duration:.2f}s | "
            f"{record.get('license')} | {record.get('source_page')}"
        )

    columns = 2
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * 360, rows * 640), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    for index, (frame_path, title) in enumerate(frames):
        image = Image.open(frame_path).convert("RGB")
        x = (index % columns) * 360
        y = (index // columns) * 640
        sheet.paste(image, (x, y))
        draw.rectangle((x, y, x + 359, y + 44), fill=(0, 0, 0))
        draw.text((x + 8, y + 12), title[:48], fill=(255, 255, 255))
    contact_sheet = OUTPUT / "meme_contact_sheet.jpg"
    sheet.save(contact_sheet, quality=90)
    print(f"MEME_PREFLIGHT_OK: {len(clips)} clips; contact sheet: {contact_sheet}")


if __name__ == "__main__":
    main()
