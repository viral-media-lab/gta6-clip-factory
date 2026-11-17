import json
import os
import subprocess
import tempfile
import atexit
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

URLS = [
    "https://www.youtube.com/shorts/YQhAo8QyQJM",
    "https://www.youtube.com/shorts/JCVC_wCsxj8",
    "https://www.youtube.com/shorts/b8W8Obp97FE",
    "https://www.youtube.com/shorts/7OeyPYZXrMU",
]
ROOT = Path("reference_review")
VIDEO_DIR = ROOT / "videos"
FRAME_DIR = ROOT / "frames"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
FRAME_DIR.mkdir(parents=True, exist_ok=True)
results = []

# Optional authenticated YouTube session supplied as a GitHub Actions secret.
# Never print the cookie contents; remove the temporary file when the job exits.
COOKIE_FILE = None
cookie_text = os.environ.get("YT_COOKIES", "").strip()
if cookie_text:
    handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False)
    handle.write(cookie_text)
    handle.close()
    COOKIE_FILE = handle.name
    atexit.register(lambda: Path(COOKIE_FILE).unlink(missing_ok=True))
    print("YouTube cookies: configured", flush=True)
else:
    print("YouTube cookies: not configured; trying public access", flush=True)

for index, url in enumerate(URLS, 1):
    output = VIDEO_DIR / f"ref_{index}.%(ext)s"
    cmd = [
        "yt-dlp", "--no-playlist", "--no-warnings",

        "-f", "best[height<=720]/best",
        "-o", str(output),
    ]
    if COOKIE_FILE:
        cmd.extend(["--cookies", COOKIE_FILE])
    cmd.append(url)
    print(f"\n===== REFERENCE {index}: {url} =====", flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    print(proc.stdout[-5000:], flush=True)
    if proc.returncode:
        print(proc.stderr[-5000:], flush=True)
        diagnostic = ["yt-dlp", "--no-warnings", "--list-formats"]
        if COOKIE_FILE:
            diagnostic.extend(["--cookies", COOKIE_FILE])
        diagnostic.append(url)
        diag = subprocess.run(diagnostic, text=True, capture_output=True)
        print("FORMAT DIAGNOSTIC:\\n" + diag.stdout[-7000:] + diag.stderr[-3000:], flush=True)
        results.append({"index": index, "url": url, "status": "download_failed", "error": proc.stderr[-1800:], "format_diagnostic": (diag.stdout + diag.stderr)[-3000:]})
        continue

    files = list(VIDEO_DIR.glob(f"ref_{index}.*"))
    files = [p for p in files if p.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    if not files:
        results.append({"index": index, "url": url, "status": "no_video_file"})
        continue
    video = files[0]
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video)
    ], text=True, capture_output=True)
    duration = float(probe.stdout.strip() or 0)
    frame_pattern = FRAME_DIR / f"ref_{index}_%03d.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video), "-vf",
        "fps=1/1.5,scale=270:480:force_original_aspect_ratio=decrease,"
        "pad=270:480:(ow-iw)/2:(oh-ih)/2",
        "-frames:v", "40", str(frame_pattern)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    results.append({
        "index": index, "url": url, "status": "downloaded",
        "file": str(video), "duration_seconds": duration,
        "frames": len(list(FRAME_DIR.glob(f"ref_{index}_*.jpg")))
    })

(ROOT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\n===== SUMMARY =====")
print(json.dumps(results, ensure_ascii=False, indent=2))
