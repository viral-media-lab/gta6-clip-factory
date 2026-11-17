import os
import re
import math
import json
import random
import asyncio
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from gtts import gTTS

ROOT = Path(__file__).parent
GAME_DIR = ROOT / "assets/game"
BODYCAM_DIR = ROOT / "assets/bodycam"
OUTPUT_DIR = ROOT / "output"
SFX_DIR = ROOT / "assets/sfx"
MUSIC_DIR = ROOT / "assets/music"
GAME_VIDEO = GAME_DIR / "gta6.mp4"
FINAL_VIDEO = OUTPUT_DIR / "gta6_short.mp4"
W, H, FPS = 1080, 1920, 30

# Punchier editorial copy. Keep factual claims framed as expectations, not confirmed mechanics.
SCRIPT = [
    "БЛЯТЬ, А ЕСЛИ В GTA 6 КОПЫ НАКОНЕЦ ПЕРЕСТАНУТ БЫТЬ ПОЛНЫМИ ИДИОТАМИ?",
    "В старой GTA ты устраивал бойню, прятался за углом — и через минуту мусора уже забыли, кто ты такой.",
    "А теперь представь: тебя заметили, запомнили тачку, лицо, маршрут. И ты такой: «Да я просто мимо проходил, нахуй!»",
    "Сменил шмотки? Охуенный план. Только вот машина та же. Гениально, Шерлок, блядь.",
    "И вместо лёгкого побега у тебя начинается персональный пиздец: свернул не туда — приехали, герой.",
    "Но спокойно: Rockstar ещё не подтвердила все эти детали. Мы пока собираем слухи и показанные нам куски.",
    "Хотя если полиция реально станет умнее, каждый угон превратится в сериал «Какой же я долбоёб».",
    "Ты хотел расслабиться в Vice City, а получил экзамен на самого тупого преступника Флориды.",
    "Короче, ты хочешь реалистичных копов — или чтобы они, как раньше, теряли тебя за ближайшим кустом?"
]
# Labels drive visual selection. Police footage is never silently substituted with random game footage.
SCENE_TYPES = ["game", "game", "game", "game", "meme", "police", "police", "game", "meme"]

def run(cmd):
    subprocess.run(cmd, check=True)

def probe_duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ])
    return float(result.decode().strip())

def download_file(url, destination):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as response, open(destination, "wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

def download_game():
    if GAME_VIDEO.exists() and GAME_VIDEO.stat().st_size > 10_000_000:
        return
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    urls = ["https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_An_Extended_Look/GTAVI_An_Extended_Look.mp4"]
    for url in urls:
        try:
            print("Downloading official GTA VI footage")
            download_file(url, GAME_VIDEO)
            if GAME_VIDEO.exists() and GAME_VIDEO.stat().st_size > 10_000_000:
                return
        except Exception as exc:
            print("Game footage download failed:", exc)
    raise RuntimeError("No GTA VI footage available")

async def make_voice():
    # Voice work is deferred; if Edge fails, regenerate EVERY line with one fallback voice.
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    paths = [audio_dir / f"{i:02}.mp3" for i in range(len(SCRIPT))]
    provider = "edge"

    async def generate_edge():
        for path, phrase in zip(paths, SCRIPT):
            tts = edge_tts.Communicate(phrase, "ru-RU-DmitryNeural", rate="+15%", pitch="-8Hz")
            await asyncio.wait_for(tts.save(str(path)), timeout=45)
            if not path.exists() or path.stat().st_size < 1000:
                raise RuntimeError("Empty Edge TTS result")

    try:
        await generate_edge()
    except Exception as exc:
        print("Edge TTS unavailable; regenerating the FULL narration with one fallback voice:", exc)
        provider = "google-fallback"
        for path in paths:
            path.unlink(missing_ok=True)
        for path, phrase in zip(paths, SCRIPT):
            gTTS(text=phrase, lang="ru", slow=False).save(str(path))

    durations = [probe_duration(p) for p in paths]
    concat = OUTPUT_DIR / "audio_list.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in paths), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c:a", "libmp3lame", str(OUTPUT_DIR / "voice.mp3")])
    print("Narration provider:", provider)
    return durations

def get_bodycam():
    exts = {".mp4", ".mov", ".mkv", ".webm", ".ogv"}
    files = [p for p in BODYCAM_DIR.glob("*") if p.suffix.lower() in exts and p.stat().st_size > 300_000]
    # Avoid known fatal-incident footage: this project wants energetic, non-graphic pursuits.
    manifest_path = BODYCAM_DIR / "sources.json"
    if manifest_path.exists():
        try:
            records = json.loads(manifest_path.read_text(encoding="utf-8"))
            safe = {r.get("file") for r in records if not re.search(r"death|killed|shooting|fatal|murder", (r.get("commons_title","") + " " + r.get("file","")).lower())}
            files = [p for p in files if p.name in safe]
        except Exception:
            pass
    return files

def make_music(duration):
    # Original, generated beat: no third-party track or copyright dependency.
    sr = 44100
    n = int(duration * sr)
    t = np.arange(n) / sr
    audio = np.zeros(n, dtype=np.float32)
    bpm = 138
    beat = 60 / bpm
    for k in range(int(duration / beat) + 1):
        start = int(k * beat * sr)
        end = min(n, start + int(0.16 * sr))
        if end <= start:
            continue
        x = np.arange(end - start) / sr
        if k % 4 == 0:
            # Kick
            phase = 2 * np.pi * (85 * x - 28 * x * x)
            env = np.exp(-24 * x)
            audio[start:end] += (0.72 * np.sin(phase) * env).astype(np.float32)
        elif k % 2 == 0:
            # Snare-like noise snap
            rng = np.random.default_rng(k + 7)
            noise = rng.normal(0, 1, end - start)
            env = np.exp(-38 * x)
            audio[start:end] += (0.18 * noise * env).astype(np.float32)
        # Hi-hat tick
        h_end = min(n, start + int(0.045 * sr))
        if h_end > start:
            hx = np.arange(h_end - start) / sr
            rng = np.random.default_rng(900 + k)
            audio[start:h_end] += (0.035 * rng.normal(0, 1, h_end-start) * np.exp(-90*hx)).astype(np.float32)
    # Low synth pulse
    audio += (0.055 * np.sin(2*np.pi*55*t) * (0.5 + 0.5*np.sin(2*np.pi*0.5*t))).astype(np.float32)
    peak = max(0.01, float(np.max(np.abs(audio))))
    audio = np.clip(audio / peak * 0.22, -0.95, 0.95)
    out = OUTPUT_DIR / "original_beat.wav"
    import wave
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((audio * 32767).astype("<i2").tobytes())
    return out

def make_siren(duration):
    sr = 44100
    n = int(duration * sr)
    t = np.arange(n) / sr
    sweep = 0.5 + 0.5 * np.sin(2*np.pi*0.75*t)
    freq = 620 + 520*sweep
    phase = 2*np.pi*np.cumsum(freq)/sr
    signal = 0.12 * np.sin(phase) * (0.5 + 0.5*np.sin(2*np.pi*1.5*t))
    out = OUTPUT_DIR / "siren.wav"
    import wave
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((np.clip(signal,-1,1)*32767).astype("<i2").tobytes())
    return out

def find_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None

def make_karaoke_ass(durations):
    # Short caption beats; punch words get a larger yellow pop instead of flat karaoke.
    path = OUTPUT_DIR / "captions.ass"

    def stamp(sec):
        h = int(sec // 3600); m = int((sec % 3600)//60); s = sec % 60
        return f"{h}:{m:02}:{s:05.2f}"

    punch_words = {
        "БЛЯТЬ", "ИДИОТАМИ", "БОЙНЮ", "НАХУЙ", "ОХУЕННЫЙ",
        "БЛЯДЬ", "ПИЗДЕЦ", "ДОЛБОЁБА", "ФЛОРИДЫ"
    }
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,82,&H00FFFFFF,&H0000D7FF,&H00000000,&H99000000,-1,0,1,8,4,2,64,64,330,1
Style: Punch,DejaVu Sans,104,&H0000D7FF,&H0000D7FF,&H00000000,&HAA000000,-1,0,1,10,5,2,48,48,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    now = 0.0
    lines = [header]
    for phrase, dur in zip(SCRIPT, durations):
        words = phrase.split()
        # Break on punch words and punctuation; keep ordinary caption beats to 2–4 words.
        chunks, chunk = [], []
        for word in words:
            clean = re.sub(r"^[^A-Za-zА-Яа-яЁё]+|[^A-Za-zА-Яа-яЁё]+$", "", word).upper()
            if clean in punch_words and chunk:
                chunks.append(chunk)
                chunk = []
            chunk.append(word)
            if clean in punch_words or re.search(r"[.!?…,:;]$", word) or len(chunk) >= 4:
                chunks.append(chunk)
                chunk = []
        if chunk:
            chunks.append(chunk)

        weights = [max(1, len(group) + sum(
            1.0 for w in group
            if re.sub(r"^[^A-Za-zА-Яа-яЁё]+|[^A-Za-zА-Яа-яЁё]+$", "", w).upper() in punch_words
        ) * 1.2) for group in chunks]
        total_weight = sum(weights) or 1
        cursor = now
        for group, weight in zip(chunks, weights):
            beat_dur = dur * weight / total_weight
            has_punch = any(
                re.sub(r"^[^A-Za-zА-Яа-яЁё]+|[^A-Za-zА-Яа-яЁё]+$", "", w).upper() in punch_words
                for w in group
            )
            escaped = []
            for word in group:
                safe = word.replace("{", "").replace("}", "")
                clean = re.sub(r"^[^A-Za-zА-Яа-яЁё]+|[^A-Za-zА-Яа-яЁё]+$", "", word).upper()
                if clean in punch_words:
                    escaped.append(r"{\c&H0000D7FF&\fscx118\fscy118}" + safe + r"{\rDefault}")
                else:
                    escaped.append(safe)
            style = "Punch" if has_punch and len(group) == 1 else "Default"
            lines.append(
                f"Dialogue: 0,{stamp(cursor)},{stamp(min(now+dur, cursor+beat_dur+0.06))},{style},,0,0,0,,"
                + " ".join(escaped) + "\n"
            )
            cursor += beat_dur
        now += dur

    path.write_text("".join(lines), encoding="utf-8")
    return path


def detect_game_shots(video):
    """Build a deterministic shot library from actual scene changes in the trailer."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    sample_rate = 4
    previous = None
    cuts = [0.0]
    frame_no = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        sec = frame_no / fps
        if frame_no % max(1, int(fps / sample_rate)) == 0:
            small = cv2.resize(frame, (96, 54))
            hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            cv2.normalize(hist, hist)
            if previous is not None:
                delta = cv2.compareHist(previous, hist, cv2.HISTCMP_BHATTACHARYYA)
                if delta > 0.38 and sec - cuts[-1] >= 1.15:
                    cuts.append(sec)
            previous = hist
        frame_no += 1
    cap.release()
    cuts.append(total)
    shots = [(a, b-a) for a, b in zip(cuts, cuts[1:]) if b-a >= 1.0]
    if not shots:
        shots = [(0.0, max(1.0, total))]
    print(f"Detected {len(shots)} usable GTA scene segments")
    return shots

def get_meme_clips():
    folder = ROOT / "assets" / "memes"
    manifest = folder / "sources.json"
    if not manifest.exists():
        return []
    try:
        records = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return []
    clips = []
    for record in records:
        path = folder / record.get("file", "")
        if path.exists() and path.stat().st_size > 250_000:
            try:
                duration = probe_duration(path)
                if duration >= 1.0:
                    clips.append((path, duration, record.get("title", "")))
            except Exception:
                pass
    print(f"Usable absurd/reaction meme clips: {len(clips)}")
    return clips


def build_montage(durations, police_files=None):
    # Real, openly licensed video inserts; no text cards or fabricated meme templates.
    shots = detect_game_shots(GAME_VIDEO)
    meme_clips = get_meme_clips()
    # Insertions land on the punchline, not randomly between unrelated lines.
    meme_at = {3: 0.62, 4: 0.70, 6: 0.62, 7: 0.68}
    scenes = []
    shot_cursor = 0
    meme_cursor = 0

    def add_game_segments(phrase_i, total):
        nonlocal shot_cursor
        left = total
        while left > 0.025:
            src_start, src_len = shots[shot_cursor % len(shots)]
            shot_cursor += 1
            cut_dur = min(left, 4.0, max(0.35, src_len - 0.08))
            usable = max(0.0, src_len - cut_dur - 0.08)
            offset = (shot_cursor * 0.37) % max(0.1, usable) if usable > 0.1 else 0.0
            scenes.append((GAME_VIDEO, src_start + offset, cut_dur, "game", phrase_i))
            left -= cut_dur

    for phrase_i, phrase_dur in enumerate(durations):
        insert_dur = meme_at.get(phrase_i, 0.0)
        if meme_clips and insert_dur and phrase_dur > insert_dur + 0.65:
            lead = (phrase_dur - insert_dur) * 0.56
            tail = phrase_dur - insert_dur - lead
            add_game_segments(phrase_i, lead)
            path, clip_len, title = meme_clips[meme_cursor % len(meme_clips)]
            meme_cursor += 1
            # Keep the excerpt short and varied; no clip is repeated until the pool cycles.
            usable = max(0.0, clip_len - insert_dur - 0.1)
            meme_start = ((meme_cursor * 1.73) % usable) if usable > 0.15 else 0.0
            scenes.append((path, meme_start, min(insert_dur, clip_len), "meme", phrase_i))
            print(f"Meme insert on line {phrase_i+1}: {title}")
            add_game_segments(phrase_i, tail)
        else:
            add_game_segments(phrase_i, phrase_dur)

    concat_list = OUTPUT_DIR / "video_parts.txt"
    with concat_list.open("w", encoding="utf-8") as listing:
        for n, (source, start, dur, kind, phrase_i) in enumerate(scenes):
            out = OUTPUT_DIR / f"cut_{n:03}.mp4"
            if kind == "meme":
                vf = (
                    "[0:v]split=2[bg][fg];"
                    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,boxblur=24:12,eq=brightness=-0.18:saturation=1.15[back];"
                    "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[front];"
                    "[back][front]overlay=(W-w)/2:(H-h)/2,"
                    "scale=1080:1920,setsar=1,eq=contrast=1.12:saturation=1.25,"
                    "format=yuv420p"
                )
            else:
                vf = (
                    "[0:v]split=2[bg][fg];"
                    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,boxblur=24:12,eq=brightness=-0.22:saturation=0.85[back];"
                    "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[front];"
                    "[back][front]overlay=(W-w)/2:(H-h)/2,"
                    "eq=contrast=1.08:saturation=1.14,setsar=1,format=yuv420p"
                )
            run(["ffmpeg","-y","-ss",f"{start:.3f}","-i",str(source),"-t",f"{dur:.3f}",
                 "-filter_complex",vf,"-r",str(FPS),"-an","-c:v","libx264",
                 "-preset","ultrafast","-pix_fmt","yuv420p",str(out)])
            listing.write(f"file '{out.as_posix()}'\n")
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat_list),
         "-c:v","copy",str(OUTPUT_DIR/"video.mp4")])


def main():
    random.seed()
    for folder in (GAME_DIR, BODYCAM_DIR, OUTPUT_DIR, SFX_DIR, MUSIC_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    print("=== GTA6 SHORT FACTORY / EDITOR V3 ===")
    download_game()
    durations = asyncio.run(make_voice())
    police = get_bodycam()
    print(f"Optional real-life clips available: {len(police)} (not inserted unless explicitly mapped)")
    build_montage(durations, police)
    ass = make_karaoke_ass(durations)
    total = sum(durations)
    music = make_music(total)
    run(["ffmpeg","-y","-i",str(OUTPUT_DIR/"video.mp4"),"-i",str(OUTPUT_DIR/"voice.mp3"),
         "-i",str(music),
         "-filter_complex",
         f"[2:a]volume=0.20,afade=t=in:st=0:d=1,afade=t=out:st={max(0,total-2):.2f}:d=2[m];"
         "[1:a]volume=1.0[v];[m][v]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[a]",
         "-vf",f"ass={ass.as_posix()}","-map","0:v:0","-map","[a]",
         "-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","aac","-b:a","192k",
         "-shortest","-movflags","+faststart",str(FINAL_VIDEO)])
    print("DONE:", FINAL_VIDEO)

if __name__ == "__main__":
    main()
