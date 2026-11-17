
import asyncio
import random
import subprocess
import textwrap
from pathlib import Path

import edge_tts

ROOT = Path(__file__).parent
GAME = ROOT / "assets" / "game"
BODYCAM = ROOT / "assets" / "bodycam"
OUT = ROOT / "output"
WORK = OUT / "work"

VIDEO_URL = "https://www.youtube.com/watch?v=tJbzMqJGH4k"
SOURCE = GAME / "extended_look.mp4"

VOICE = "ru-RU-DmitryNeural"
RATE = "+12%"
PITCH = "-8Hz"

# Текст разбит на отдельные эмоциональные реплики.
# Тайминг субтитров рассчитывается по фактической длине озвучки.

SCENES = [
    (750, "game"),
    (770, "game"),
    (690, "game"),
    (710, "game"),
    (1150, "game"),
    (750, "game"),
    (760, "game"),
    (500, "game"),
    (270, "game"),
    (780, "game"),
]

SCRIPT = [
    "БЛЯТЬ, В GTA 6 КОПЫ НЕ ПРОСТО ПОТЕРЯЮТ ТЕБЯ. ОНИ ЗАПОМНЯТ, КТО ТЫ ТАКОЙ!",
    "В старых частях можно было нарезать круги по району, переждать звёзды — и будто ничего не было.",
    "А здесь у полиции будет целое досье: лицо, одежда, машина, оружие, камеры и даже твой напарник.",
    "И да, если ты просто нацепил кепку и очки — одежда всё ещё палит тебя. Это прямо объяснял разработчик Rockstar.",
    "Придётся реально переодеться, сменить тачку или разделиться с Люсией. Это уже не побег, а работа над ошибками.",
    "А если преступление никто не увидел и сигнализация не сработала, копы могут вообще не получить вызов.",
    "То есть сначала найди свидетеля, потом устрой погоню, а потом ещё докажи полиции, что это был не ты. Красота!",
    "А пока ты пытаешься всё это провернуть, американские копы в реальности иногда выглядят так, будто сами застряли в GTA.",
    "Rockstar, вы делаете криминальную песочницу или курс повышения квалификации для беглых?",
    "Короче, мало просто оторваться. Надо стереть за собой улики. Ты бы вывез?"
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
        print("Game video already downloaded.")
        return

    print("Downloading official Rockstar footage...")

    GAME.mkdir(parents=True, exist_ok=True)

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
        raise RuntimeError("Game video was not downloaded.")


async def make_voice(index, phrase):
    path = WORK / f"voice_{index:02d}.mp3"
    temp = WORK / f"voice_{index:02d}_padded.mp3"

    print(f"Creating voice {index + 1}/{len(SCRIPT)}")

    communicate = edge_tts.Communicate(
        phrase,
        VOICE,
        rate=RATE,
        pitch=PITCH
    )

    await communicate.save(str(path))

    # Небольшая пауза после каждой реплики.
    run([
        "ffmpeg", "-y",
        "-i", str(path),
        "-af", "apad=pad_dur=0.22",
        "-c:a", "libmp3lame",
        "-q:a", "3",
        str(temp)
    ])

    return temp


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
Style: Default,DejaVu Sans,66,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,1,6,2,2,70,70,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def stamp(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    content = header
    current = 0.0

    for phrase, duration in zip(SCRIPT, durations):
        start = current + 0.02
        end = current + duration - 0.03

        wrapped = textwrap.wrap(phrase, width=29)
        caption = r"\N".join(wrapped)
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


def make_video_segment(index, duration, scene_start, bodycam_files):
    output = WORK / f"scene_{index:02d}.mp4"

    # Каждая четвёртая сцена может быть реальной bodycam-вставкой.
    use_bodycam = (
        index in (3, 7)
        and len(bodycam_files) > 0
    )

    if use_bodycam:
        source = bodycam_files[(index // 4) % len(bodycam_files)]
        print("Using bodycam:", source.name)

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
        print("Using GTA scene:", scene_start)

        run([
            "ffmpeg", "-y",
            "-ss", str(scene_start),
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

    voice_files = []

    for i, phrase in enumerate(SCRIPT):
        voice_files.append(await make_voice(i, phrase))

    durations = [probe_duration(p) for p in voice_files]

    # Собираем озвучку в один файл.
    concat_audio = WORK / "audio_list.txt"
    concat_audio.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in voice_files),
        encoding="utf-8"
    )

    narration = OUT / "narration.mp3"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_audio),
        "-c:a", "libmp3lame",
        "-q:a", "2",
        str(narration)
    ])

    bodycam_files = find_bodycam()

    if not bodycam_files:
        print(
            "\nBODYCAM: no files found. "
            "Using GTA footage for all scenes."
        )

    # Создаём отдельные игровые сцены под каждую реплику.
    video_files = []

    for i, (scene_start, scene_type) in enumerate(SCENES):
        video_files.append(
            make_video_segment(
                i,
                durations[i],
                scene_start,
                bodycam_files
            )
        )

    concat_video = WORK / "video_list.txt"
    concat_video.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in video_files),
        encoding="utf-8"
    )

    raw_video = WORK / "raw_video.mp4"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_video),
        "-c", "copy",
        str(raw_video)
    ])

    captions = make_ass(durations)

    final_video = OUT / "gta6_short.mp4"

    print("\nRendering final vertical video...")

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

