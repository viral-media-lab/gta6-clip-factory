
import os
import re
import json
import random
import asyncio
import subprocess
import urllib.request
from pathlib import Path

import edge_tts

ROOT = Path(__file__).parent
GAME_DIR = ROOT / "assets/game"
BODYCAM_DIR = ROOT / "assets/bodycam"
OUTPUT_DIR = ROOT / "output"

GAME_VIDEO = GAME_DIR / "gta6.mp4"
FINAL_VIDEO = OUTPUT_DIR / "gta6_short.mp4"

# Прямые источники видео. Если источник недоступен,
# скрипт попробует следующий.
GAME_URLS = [
    "https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_An_Extended_Look/GTAVI_An_Extended_Look.mp4",
]

SCRIPT = [
    "БЛЯТЬ, В GTA 6 КОПЫ НЕ ПРОСТО ПОТЕРЯЮТ ТЕБЯ. ОНИ ЗАПОМНЯТ, КТО ТЫ ТАКОЙ!",
    "В старых частях можно было нарезать круги по району и переждать звёзды.",
    "А здесь полиция будет учитывать твою одежду, машину, оружие и камеры.",
    "Нацепил кепку и очки? Брат, это уже не поможет.",
    "Придётся менять тачку, переодеваться и заметать следы.",
    "И самое смешное: реальные американские копы иногда выглядят так, будто сами застряли в GTA.",
    "Погоня, сирены, полный хаос. Только это уже не игра, блядь!",
    "Rockstar, вы делаете криминальную песочницу или курс побега от полиции?",
    "Короче, мало просто оторваться. Надо ещё не спалиться. Ты бы вывез?"
]

def run(cmd):
    subprocess.run(cmd, check=True)

def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        with open(destination, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)

def download_game():
    if GAME_VIDEO.exists() and GAME_VIDEO.stat().st_size > 10_000_000:
        return

    for url in GAME_URLS:
        try:
            print("Downloading GTA footage...")
            download_file(url, GAME_VIDEO)
            if GAME_VIDEO.stat().st_size > 10_000_000:
                return
        except Exception as error:
            print("Source failed:", error)

    raise RuntimeError("Could not download GTA footage.")

def find_bodycam():
    extensions = {".mp4", ".mov", ".mkv"}
    return [
        p for p in BODYCAM_DIR.iterdir()
        if p.suffix.lower() in extensions
    ]

async def make_voice():
    AUDIO_DIR = OUTPUT_DIR / "audio"
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    files = []
    for i, phrase in enumerate(SCRIPT):
        path = AUDIO_DIR / f"{i:02}.mp3"
        voice = edge_tts.Communicate(
            phrase,
            "ru-RU-DmitryNeural",
            rate="+15%",
            pitch="-8Hz"
        )
        await voice.save(str(path))
        files.append(path)

    with open(OUTPUT_DIR / "audio_list.txt", "w") as f:
        for path in files:
            f.write(f"file '{path.as_posix()}'\n")

    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(OUTPUT_DIR / "audio_list.txt"),
        "-c:a", "libmp3lame",
        str(OUTPUT_DIR / "voice.mp3")
    ])

def get_duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return float(result.decode().strip())

def make_video():
    bodycam = find_bodycam()
    source_duration = get_duration(GAME_VIDEO)
    voice_duration = get_duration(OUTPUT_DIR / "voice.mp3")

    # Чередуем игровые сцены и реальные bodycam,
    # если в папке есть подходящие видео.
    scenes = []
    scene_count = len(SCRIPT)
    segment_duration = voice_duration / scene_count

    for i in range(scene_count):
        if bodycam and i in (5, 6):
            scenes.append(random.choice(bodycam))
        else:
            scenes.append(GAME_VIDEO)

    concat_file = OUTPUT_DIR / "scenes.txt"

    with open(concat_file, "w") as f:
        for i, source in enumerate(scenes):
            if source == GAME_VIDEO:
                start = max(
                    0,
                    min(
                        source_duration - segment_duration - 1,
                        (source_duration - segment_duration) *
                        i / max(1, scene_count - 1)
                    )
                )
            else:
                duration = get_duration(source)
                start = random.uniform(
                    0, max(0, duration - segment_duration - 0.5)
                )

            scene = OUTPUT_DIR / f"scene_{i}.mp4"

            run([
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", str(source),
                "-t", str(segment_duration),
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,setsar=1",
                "-r", "30",
                "-an",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                str(scene)
            ])

            f.write(f"file '{scene.as_posix()}'\n")

    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(OUTPUT_DIR / "video.mp4")
    ])

def make_subtitles():
    duration = get_duration(OUTPUT_DIR / "voice.mp3")
    segment = duration / len(SCRIPT)

    def stamp(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours}:{minutes:02}:{seconds:05.2f}"

    with open(OUTPUT_DIR / "captions.ass", "w", encoding="utf-8") as f:
        f.write("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,66,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,1,5,2,2,65,65,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")

        for i, phrase in enumerate(SCRIPT):
            start = i * segment
            end = (i + 1) * segment
            words = phrase.split()
            lines = []
            current = ""

            for word in words:
                if len(current) + len(word) > 25:
                    lines.append(current)
                    current = word
                else:
                    current = (current + " " + word).strip()

            if current:
                lines.append(current)

            text = r"\N".join(lines)
            text = text.replace("{", r"\{").replace("}", r"\}")
            f.write(
                f"Dialogue: 0,{stamp(start)},{stamp(end)},"
                f"Default,,0,0,0,,{text}\n"
            )

def main():
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    BODYCAM_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== GTA 6 CLIP FACTORY ===")
    download_game()
    asyncio.run(make_voice())
    make_video()
    make_subtitles()

    run([
        "ffmpeg", "-y",
        "-i", str(OUTPUT_DIR / "video.mp4"),
        "-i", str(OUTPUT_DIR / "voice.mp3"),
        "-vf", f"ass={OUTPUT_DIR / 'captions.ass'}",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(FINAL_VIDEO)
    ])

    print("DONE:", FINAL_VIDEO)

if __name__ == "__main__":
    main()
