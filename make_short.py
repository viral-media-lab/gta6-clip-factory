
import asyncio
import subprocess
import textwrap
from pathlib import Path

import edge_tts

ROOT = Path(__file__).parent
GAME = ROOT / "assets" / "game"
BODYCAM = ROOT / "assets" / "bodycam"
OUT = ROOT / "output"
WORK = OUT / "work"

# Официальный Trailer 2 на канале PlayStation
VIDEO_URL = "https://www.youtube.com/watch?v=l6RRdTFuepk"
SOURCE = GAME / "extended_look.mp4"

VOICE = "ru-RU-DmitryNeural"
RATE = "+15%"
PITCH = "-8Hz"

# Таймкоды внутри ролика длительностью 2:47
SCENE_STARTS = [4, 17, 31, 45, 59, 74, 89, 105, 123, 145]

SCRIPT = [
    "БЛЯТЬ, В GTA 6 КОПЫ НЕ ПРОСТО ПОТЕРЯЮТ ТЕБЯ. ОНИ ЗАПОМНЯТ, КТО ТЫ ТАКОЙ!",
    "В старых частях можно было нарезать круги по району, переждать звёзды — и будто ничего не было.",
    "А здесь у полиции будет целое досье: твоя одежда, машина, оружие, камеры и даже твой напарник.",
    "И если ты просто нацепил кепку и очки — это ещё не значит, что тебя не узнают. Rockstar явно решила усложнить жизнь.",
    "Придётся реально переодеться, сменить тачку или разделиться с Люсией. Это уже не побег, а работа над ошибками.",
    "А теперь представь: ты вроде бы скрылся, а полиция всё ещё пытается понять, кто ты и куда делся.",
    "То есть мало устроить беспредел — надо ещё грамотно замести за собой следы. Красота, блядь!",
    "А пока ты пытаешься всё это провернуть, американские копы в реальности иногда выглядят так, будто сами застряли в GTA.",
    "Rockstar, вы делаете криминальную песочницу или курс повышения квалификации для беглых?",
    "Короче, мало просто оторваться. Надо ещё не спалиться. Ты бы вывез?"
]


def run(cmd):
    print("RUN:", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def probe_duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return float(result.decode().strip())


def download_game_video():
    if SOURCE.exists() and SOURCE.stat().st_size > 10_000_000:
        print("Using existing game video.")
        return

    GAME.mkdir(parents=True, exist_ok=True)
    print("Downloading PlayStation Trailer 2...")

    run([
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", str(SOURCE),
        VIDEO_URL
    ])

    if not SOURCE.exists():
        raise RuntimeError("Video download finished but MP4 was not found.")


async def make_voice(index, phrase):
    path = WORK / f"voice_{index:02d}.mp3"
    padded = WORK / f"voice_{index:02d}_padded.mp3"

    print(f"Creating voice {index + 1}/{len(SCRIPT)}")

    tts = edge_tts.Communicate(
        phrase,
        VOICE,
        rate=RATE,
        pitch=PITCH
    )
    await tts.save(str(path))

    run([
        "ffmpeg", "-y",
        "-i", str(path),
        "-af", "apad=pad_dur=0.25",
        "-c:a", "libmp3lame",
        "-q:a", "3",
        str(padded)
    ])

    return padded


def make_ass(durations):
    header = """[Script Info]
Title: GTA 6 Short
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,66,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,1,6,2,2,65,65,280,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def stamp(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    content = header
    current = 0.0

    for phrase, duration in zip(SCRIPT, durations):
        start = current + 0.02
        end = current + duration - 0.03

        lines = textwrap.wrap(phrase, width=27)
        caption = r"\N".join(lines)
        caption = caption.replace("{", "").replace("}", "")

        content += (
            f"Dialogue: 0,{stamp(start)},{stamp(end)},"
            f"Default,,0,0,0,,{caption}\n"
        )

        current += duration

    path = OUT / "captions.ass"
    path.write_text(content, encoding="utf-8")
    return path


def find_bodycam():
    extensions = {".mp4", ".mov", ".mkv", ".webm"}
    return sorted(
        p for p in BODYCAM.glob("*")
        if p.suffix.lower() in extensions
    )


def make_video_segment(index, duration, source_duration, bodycam_files):
    output = WORK / f"scene_{index:02d}.mp4"

    # Если в папке есть bodycam-файлы,
    # используем их в двух комедийных перебивках.
    use_bodycam = index in (3, 7) and bool(bodycam_files)

    if use_bodycam:
        source = bodycam_files[(index // 4) % len(bodycam_files)]
        print("BODYCAM INSERT:", source.name)

        run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(source),
            "-t", str(duration),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,fps=30,setsar=1",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            str(output)
        ])

    else:
        requested_start = SCENE_STARTS[index]

        # Не позволяем таймкоду выйти за границы ролика.
        max_start = max(0, source_duration - duration - 0.5)
        start = min(requested_start, max_start)

        print(f"GTA SCENE {index + 1}: {start:.1f}s")

        run([
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(SOURCE),
            "-t", str(duration),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,fps=30,setsar=1,"
            "eq=contrast=1.06:saturation=1.12",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            str(output)
        ])

    return output


async def main():
    OUT.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    GAME.mkdir(parents=True, exist_ok=True)
    BODYCAM.mkdir(parents=True, exist_ok=True)

    print("\n=== GTA 6 CLIP FACTORY ===\n")

    download_game_video()

    source_duration = probe_duration(SOURCE)
    print("SOURCE DURATION:", round(source_duration, 1), "seconds")

    voice_files = []

    for i, phrase in enumerate(SCRIPT):
        voice_files.append(await make_voice(i, phrase))

    durations = [probe_duration(p) for p in voice_files]

    # Склеиваем реплики в одну аудиодорожку.
    audio_list = WORK / "audio_list.txt"
    audio_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in voice_files),
        encoding="utf-8"
    )

    narration = OUT / "narration.mp3"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(audio_list),
        "-c:a", "libmp3lame",
        "-q:a", "2",
        str(narration)
    ])

    bodycam_files = find_bodycam()

    if not bodycam_files:
        print("No bodycam files found. Using GTA footage only.")

    video_files = []

    for i, duration in enumerate(durations):
        video_files.append(
            make_video_segment(
                i,
                duration,
                source_duration,
                bodycam_files
            )
        )

    # Склеиваем все видеосцены.
    video_list = WORK / "video_list.txt"
    video_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in video_files),
        encoding="utf-8"
    )

    raw_video = WORK / "raw_video.mp4"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(video_list),
        "-c", "copy",
        str(raw_video)
    ])

    captions = make_ass(durations)
    final_video = OUT / "gta6_short.mp4"

    print("\nRendering final video...")

    run([
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-i", str(narration),
        "-vf",
        f"subtitles={captions}:fontsdir=/usr/share/fonts/truetype/dejavu",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final_video)
    ])

    print("\n================================")
    print("VIDEO READY:", final_video)
    print("DURATION:", round(probe_duration(final_video), 1), "seconds")
    print("================================")


if __name__ == "__main__":
    asyncio.run(main())
