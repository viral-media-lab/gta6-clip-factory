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
    "БЛЯТЬ, В GTA 6 ОТ КОПОВ МОЖНО БУДЕТ НЕ УБЕЖАТЬ. ПОТОМУ ЧТО ОНИ МОГУТ ТЕБЯ ЗАПОМНИТЬ.",
    "В старой GTA сделал круг вокруг квартала — и полиция будто амнезию словила.",
    "А теперь представь: тебя палят камеры, свидетели, тачка и твоя тупая рожа.",
    "Переоделся? Красавчик. Только машину-то ты оставил ту же, гений.",
    "И вот ты уже не гангстер. Ты участник самого дорогого квеста «НЕ ПОПАДИСЬ, ИДИОТ».",
    "А теперь сравни это с реальными американскими погонями. Там иногда такой цирк, что Rockstar нервно курит.",
    "Сирены, развороты, копы на хвосте — и один тип, который явно забыл, что тормоз существует.",
    "Если Rockstar реально доведёт полицию до такого уровня, обычная поездка в магазин станет уголовным триллером.",
    "Короче, вопрос один: ты будешь играть в GTA 6 или проходить стажировку по побегу от копов?"
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

def make_meme_card(index, text):
    img = Image.new("RGB", (W, H), (15, 15, 18))
    d = ImageDraw.Draw(img)
    font_path = find_font()
    font = ImageFont.truetype(font_path, 92) if font_path else ImageFont.load_default()
    small = ImageFont.truetype(font_path, 42) if font_path else ImageFont.load_default()
    d.rectangle((54, 400, W-54, 1500), outline=(255, 214, 0), width=12)
    d.text((W//2, 530), "POV:", font=small, fill=(255, 214, 0), anchor="mm")
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if d.textbbox((0,0), test, font=font)[2] > W-180:
            lines.append(line); line = word
        else:
            line = test
    if line: lines.append(line)
    y = 760
    for ln in lines[:5]:
        d.text((W//2+4, y+4), ln, font=font, fill=(0,0,0), anchor="mm", stroke_width=5, stroke_fill=(0,0,0))
        d.text((W//2, y), ln, font=font, fill=(255,255,255), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        y += 130
    d.text((W//2, 1380), "GTA 6 POLICE UPDATE", font=small, fill=(255,255,255), anchor="mm")
    path = OUTPUT_DIR / f"meme_{index}.png"
    img.save(path)
    return path

def make_karaoke_ass(durations):
    # ASS karaoke: each word lights up in sequence, line timings follow actual phrase audio durations.
    path = OUTPUT_DIR / "captions.ass"
    def stamp(sec):
        h = int(sec // 3600); m = int((sec % 3600)//60); s = sec % 60
        return f"{h}:{m:02}:{s:05.2f}"
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,76,&H00FFFFFF,&H0000D7FF,&H00000000,&H99000000,-1,0,1,7,3,2,70,70,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    now = 0.0
    lines = [header]
    for phrase, dur in zip(SCRIPT, durations):
        words = phrase.split()
        # Split into readable chunks of max 5 words; each chunk gets its own karaoke timing.
        chunks, chunk = [], []
        for word in words:
            chunk.append(word)
            if len(chunk) >= 5:
                chunks.append(chunk); chunk=[]
        if chunk: chunks.append(chunk)
        chunk_dur = dur / max(1, len(chunks))
        for ci, group in enumerate(chunks):
            each = max(1, int(chunk_dur * 100 / len(group)))
            text = " ".join(r"{\k" + str(each) + "}" + w.replace("{","").replace("}","") for w in group)
            start = now + ci*chunk_dur
            end = min(now+dur, start+chunk_dur+0.08)
            lines.append(f"Dialogue: 0,{stamp(start)},{stamp(end)},Default,,0,0,0,,{text}\n")
        now += dur
    path.write_text("".join(lines), encoding="utf-8")
    return path

def build_montage(durations, police_files):
    game_dur = probe_duration(GAME_VIDEO)
    scenes = []
    timeline = 0.0
    police_cursor = 0
    for i, phrase in enumerate(SCRIPT):
        phrase_dur = durations[i]
        kind = SCENE_TYPES[i]
        if kind == "police" and police_files:
            source = police_files[police_cursor % len(police_files)]
            police_cursor += 1
            # Divide this sentence into short cuts, all from actual police footage.
            scene_len = 1.35
            count = max(1, math.ceil(phrase_dur / scene_len))
            for j in range(count):
                dur = min(scene_len, phrase_dur - j*scene_len)
                srcdur = probe_duration(source)
                start = (police_cursor*7 + j*3) % max(1, int(max(1, srcdur-dur)))
                scenes.append((source, start, dur, "police", i))
        elif kind == "meme":
            meme_text = "ТВОЙ ПЛАН ПОБЕГА: " + ("ПЕРЕОДЕЛСЯ, НО ЗАБЫЛ ПРО ТАЧКУ" if i == 4 else "ROCKSTAR, НЕ ДЕЛАЙ ИЗ МЕНЯ УГОЛОВНИКА")
            card = make_meme_card(i, meme_text)
            scenes.append((card, 0, phrase_dur, "meme", i))
        else:
            # Fast random game cuts, 1.1–1.8s, no long static trailer segments.
            pos = 0.0
            while pos < phrase_dur:
                dur = min(random.uniform(1.1, 1.8), phrase_dur-pos)
                start = random.uniform(0, max(0.1, game_dur-dur-0.1))
                scenes.append((GAME_VIDEO, start, dur, "game", i))
                pos += dur
        timeline += phrase_dur

    concat_list = OUTPUT_DIR / "video_parts.txt"
    with concat_list.open("w", encoding="utf-8") as listing:
        for n, (source, start, dur, kind, phrase_i) in enumerate(scenes):
            out = OUTPUT_DIR / f"cut_{n:03}.mp4"
            if kind == "meme":
                run(["ffmpeg","-y","-loop","1","-i",str(source),"-t",f"{dur:.3f}",
                     "-vf",f"scale={W}:{H},setsar=1,format=yuv420p","-r",str(FPS),
                     "-an","-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p",str(out)])
            else:
                # Every cut gets a subtle animated push-in; police clips get a punchier crop.
                zoom = "1.10" if kind == "police" else "1.055"
                vf = f"scale=1200:2134:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='{zoom}':d=1:s=1080x1920:fps={FPS},eq=contrast=1.06:saturation=1.12,setsar=1"
                run(["ffmpeg","-y","-ss",f"{start:.3f}","-i",str(source),"-t",f"{dur:.3f}",
                     "-vf",vf,"-r",str(FPS),"-an","-c:v","libx264","-preset","veryfast",
                     "-pix_fmt","yuv420p",str(out)])
            listing.write(f"file '{out.as_posix()}'\n")
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat_list),
         "-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p",str(OUTPUT_DIR/"video.mp4")])

def main():
    random.seed()
    for folder in (GAME_DIR, BODYCAM_DIR, OUTPUT_DIR, SFX_DIR, MUSIC_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    print("=== GTA6 SHORT FACTORY / EDITOR V2 ===")
    download_game()
    durations = asyncio.run(make_voice())
    police = get_bodycam()
    if not police:
        raise RuntimeError("No verified police footage was downloaded. Refusing to publish another GTA-only video. Fix media_finder before retrying.")
    print(f"Verified police clips available: {len(police)}")
    build_montage(durations, police)
    ass = make_karaoke_ass(durations)
    total = sum(durations)
    music = make_music(total)
    siren = make_siren(total)
    # Police siren accents only around the real-life police section.
    police_start = sum(durations[:5])
    run(["ffmpeg","-y","-i",str(OUTPUT_DIR/"video.mp4"),"-i",str(OUTPUT_DIR/"voice.mp3"),
         "-i",str(music),"-i",str(siren),
         "-filter_complex",
         f"[2:a]volume=0.20,afade=t=in:st=0:d=1,afade=t=out:st={max(0,total-2):.2f}:d=2[m];"
         f"[3:a]atrim=0:4,adelay={int(police_start*1000)}|{int(police_start*1000)},volume=0.22[s];"
         "[1:a]volume=1.0[v];[m][s][v]amix=inputs=3:duration=first:dropout_transition=2,alimiter=limit=0.95[a]",
         "-vf",f"ass={ass.as_posix()}","-map","0:v:0","-map","[a]",
         "-c:v","libx264","-preset","veryfast","-crf","21","-c:a","aac","-b:a","192k",
         "-shortest","-movflags","+faststart",str(FINAL_VIDEO)])
    print("DONE:", FINAL_VIDEO)

if __name__ == "__main__":
    main()
