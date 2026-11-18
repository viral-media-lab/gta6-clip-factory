#!/usr/bin/env python3
"""Modular narration and sound-design prototype for GTA 6 Shorts.

The engine keeps narration, music and SFX on separate tracks. Voice is generated
per line so delivery can be tuned without replacing the editing pipeline.
"""
import argparse
import asyncio
import json
import subprocess
import time
import wave
from pathlib import Path

import numpy as np
import edge_tts
from gtts import gTTS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "audio_test"
VOICE = "ru-RU-DmitryNeural"
DELIVERY = {
    "excited": {"rate": "+12%", "pitch": "+3Hz"},
    "angry": {"rate": "+8%", "pitch": "-2Hz"},
    "sarcastic": {"rate": "-4%", "pitch": "-3Hz"},
    "deadpan": {"rate": "-8%", "pitch": "-5Hz"},
}

TEST_LINES = [
    {"text": "БЛЯТЬ, ЛОС-САНТОС ОПЯТЬ ПРЕВРАТИЛСЯ В ЦИРК!", "delivery": "excited", "pause_before": 0.15, "sfx": "impact"},
    {"text": "Ты просто хотел спокойно доехать до магазина.", "delivery": "deadpan", "pause_before": 0.18},
    {"text": "А игра решила, что сегодня у тебя день знакомства с асфальтом.", "delivery": "sarcastic", "pause_before": 0.12, "sfx": "whoosh"},
    {"text": "И вот за это мы, блядь, и любим GTA.", "delivery": "angry", "pause_before": 0.25, "sfx": "impact"},
]

def run(cmd):
    subprocess.run(cmd, check=True)

async def synthesize_line(line, path):
    """Try Edge TTS with retries; use gTTS only as a marked emergency fallback."""
    style = DELIVERY.get(line.get("delivery", "deadpan"), DELIVERY["deadpan"])
    last_error = None

    for attempt in range(3):
        try:
            path.unlink(missing_ok=True)
            tts = edge_tts.Communicate(
                line["text"], VOICE, rate=style["rate"], pitch=style["pitch"]
            )
            await asyncio.wait_for(tts.save(str(path)), timeout=60)
            if path.exists() and path.stat().st_size >= 1000:
                wav_path = path.with_suffix(".wav")
                run(["ffmpeg", "-y", "-i", str(path), "-ar", "44100", "-ac", "1", str(wav_path)])
                path.unlink(missing_ok=True)
                return wav_path, "edge-tts"
            last_error = RuntimeError("Edge TTS returned an empty audio file")
        except Exception as exc:
            last_error = exc
            path.unlink(missing_ok=True)
        if attempt < 2:
            delay = 2 ** (attempt + 1)
            print(f"Edge TTS attempt {attempt + 1}/3 failed: {last_error}. Retrying in {delay}s.")
            await asyncio.sleep(delay)

    print(f"Edge TTS unavailable for this line; trying gTTS fallback: {last_error}")
    try:
        await asyncio.wait_for(
            asyncio.to_thread(gTTS(text=line["text"], lang="ru").save, str(path)),
            timeout=60,
        )
        if not path.exists() or path.stat().st_size < 1000:
            raise RuntimeError("gTTS returned an empty audio file")
        wav_path = path.with_suffix(".wav")
        run(["ffmpeg", "-y", "-i", str(path), "-ar", "44100", "-ac", "1", str(wav_path)])
        path.unlink(missing_ok=True)
        return wav_path, "gtts-fallback"
    except Exception as fallback_error:
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Both TTS providers failed. Edge TTS: {last_error}; gTTS: {fallback_error}"
        ) from fallback_error

def probe_duration(path):
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ])
    return float(raw.decode().strip())

def write_silence(path, duration, sr=44100):
    samples = np.zeros(max(1, int(duration * sr)), dtype=np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(samples.tobytes())

def write_sfx(path, kind, sr=44100):
    rng = np.random.default_rng(42 if kind == "impact" else 43)
    duration = 0.32 if kind == "impact" else 0.24
    t = np.arange(int(sr * duration)) / sr
    noise = rng.normal(0, 1, len(t))
    if kind == "impact":
        signal = 0.72 * np.sin(2 * np.pi * (95 - 55*t) * t) * np.exp(-14*t) + 0.18*noise*np.exp(-35*t)
    else:
        signal = 0.24 * noise * np.exp(-10*t) + 0.12*np.sin(2*np.pi*(700-1500*t)*t)*np.exp(-8*t)
    signal = np.clip(signal / max(1e-6, np.max(np.abs(signal))) * 0.72, -1, 1)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((signal * 32767).astype("<i2").tobytes())

async def build_test():
    OUT.mkdir(parents=True, exist_ok=True)
    # Remove stale files so a failed run cannot upload an old prototype as new.
    for stale in OUT.iterdir():
        if stale.is_file():
            stale.unlink()

    voice_parts = []
    events = []
    providers = []
    cursor = 0.0
    for i, line in enumerate(TEST_LINES):
        pause = float(line.get("pause_before", 0))
        if pause:
            silence = OUT / f"pause_{i:02}.wav"
            write_silence(silence, pause)
            voice_parts.append(silence)
            cursor += pause
        mp3 = OUT / f"line_{i:02}.mp3"
        wav_line, provider = await synthesize_line(line, mp3)
        providers.append(provider)
        duration = probe_duration(wav_line)
        voice_parts.append(wav_line)
        events.append({
            "line": i, "start": round(cursor, 3), "duration": round(duration, 3),
            "delivery": line["delivery"], "tts_provider": provider
        })
        if line.get("sfx"):
            events.append({"sfx": line["sfx"], "at": round(cursor, 3)})
        cursor += duration

    concat = OUT / "voice_concat.txt"
    concat.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in voice_parts), encoding="utf-8")
    voice = OUT / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-ar", "44100", "-ac", "2", str(voice)])

    total = probe_duration(voice)
    sfx_events = [event for event in events if "sfx" in event]
    sfx_paths = []
    for idx, event in enumerate(sfx_events):
        path = OUT / f"sfx_{idx:02}.wav"
        write_sfx(path, event["sfx"])
        sfx_paths.append((path, event["at"]))

    music = ROOT / "assets" / "music" / "test_bed.mp3"
    inputs = ["-i", str(voice)]
    filters = []
    if music.exists():
        inputs.extend(["-stream_loop", "-1", "-i", str(music)])
        filters.extend(["[1:a]volume=0.12[bed]", "[0:a][bed]amix=inputs=2:duration=first:dropout_transition=2[base]"])
        base = "[base]"
        next_input = 2
    else:
        base = "[0:a]"
        next_input = 1
    sfx_labels = []
    for idx, (path, at) in enumerate(sfx_paths):
        inputs.extend(["-i", str(path)])
        delay = int(at * 1000)
        label = f"[s{idx}]"
        filters.append(f"[{next_input + idx}:a]volume=0.42,adelay={delay}|{delay}{label}")
        sfx_labels.append(label)
    if sfx_labels:
        filters.append(base + "".join(sfx_labels) + f"amix=inputs={1+len(sfx_labels)}:duration=first:dropout_transition=0,alimiter=limit=0.95[mix]")
        output_label = "[mix]"
    else:
        output_label = base
    final = OUT / "audio_test.wav"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", output_label, "-t", f"{total:.3f}", str(final)])
    (OUT / "audio_audit.json").write_text(json.dumps({
        "voice": VOICE, "tts_providers": providers, "music_used": music.exists(),
        "duration": round(total, 3), "events": events,
        "status": "audio prototype rendered; listen before production integration"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"AUDIO_TEST_COMPLETE duration={total:.2f}s providers={','.join(providers)} music={'yes' if music.exists() else 'no'}")
    print(f"AUDIO_TEST_FILE={final}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if not args.test:
        raise SystemExit("Use --test for the short audio prototype.")
    asyncio.run(build_test())
