import json
import subprocess
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

for index, url in enumerate(URLS, 1):
    output = VIDEO_DIR / f"ref_{index}.%(ext)s"
    cmd = [
        "yt-dlp", "--no-playlist", "--no-warnings",
        "-f", "bv*[height<=720]+ba/b[height<=720]",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "-o", str(output), url,
    ]
    print(f"\n===== REFERENCE {index}: {url} =====", flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    print(proc.stdout[-5000:], flush=True)
    if proc.returncode:
        print(proc.stderr[-5000:], flush=True)
        results.append({"index": index, "url": url, "status": "download_failed", "error": proc.stderr[-1800:]})
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
