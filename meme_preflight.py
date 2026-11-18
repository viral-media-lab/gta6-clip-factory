#!/usr/bin/env python3
"""Discover meme candidates, verify license metadata and render a visual contact sheet."""
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw
import make_short

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
MEME_DIR = ROOT / "assets" / "memes"


def main():
    subprocess.run([sys.executable, str(ROOT / "meme_finder.py")], check=True)
    manifest_path = MEME_DIR / "sources.json"
    records = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    candidates = []

    for record in records:
        path = MEME_DIR / record.get("file", "")
        if not path.exists() or path.stat().st_size < 250_000:
            continue
        if not record.get("license") or not record.get("source_page"):
            continue
        try:
            duration = make_short.probe_duration(path)
        except Exception as exc:
            print(f"Skip unreadable meme candidate {path.name}: {exc}")
            continue
        if duration < 1.0:
            continue
        candidates.append((path, duration, record.get("title", ""), record))

    frames = []
    for index, (path, duration, title, record) in enumerate(candidates):
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
        frames.append((frame_path, title, record.get("approved_for_edit", False)))
        print(
            f"MEME_CANDIDATE: {path.name} | {duration:.2f}s | "
            f"approved={record.get('approved_for_edit', False)} | "
            f"{record.get('license')} | {record.get('source_page')}"
        )

    if frames:
        columns = 2
        rows = math.ceil(len(frames) / columns)
        sheet = Image.new("RGB", (columns * 360, rows * 640), (12, 12, 12))
        draw = ImageDraw.Draw(sheet)
        for index, (frame_path, title, approved) in enumerate(frames):
            image = Image.open(frame_path).convert("RGB")
            x = (index % columns) * 360
            y = (index // columns) * 640
            sheet.paste(image, (x, y))
            draw.rectangle((x, y, x + 359, y + 48), fill=(0, 0, 0))
            label = ("[APPROVED] " if approved else "[CANDIDATE] ") + title[:38]
            draw.text((x + 8, y + 14), label, fill=(255, 255, 255))
        contact_sheet = OUTPUT / "meme_contact_sheet.jpg"
        sheet.save(contact_sheet, quality=90)
        print(f"MEME_CONTACT_SHEET: {contact_sheet}")

    approved_count = sum(1 for _, _, _, record in candidates if record.get("approved_for_edit", False))
    print(f"MEME_CANDIDATE_GATE: downloaded={len(candidates)} approved={approved_count}")
    if approved_count < 2:
        raise RuntimeError(
            f"Only {approved_count} visually approved meme clips; need at least 2. "
            "Candidate contact sheet was still generated for review."
        )

    print(f"MEME_PREFLIGHT_OK: {approved_count} approved clips")


if __name__ == "__main__":
    main()
