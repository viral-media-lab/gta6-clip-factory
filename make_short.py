
import asyncio
import os
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import edge_tts

W, H = 1080, 1920
FPS = 24
OUT = Path("output")
OUT.mkdir(exist_ok=True)

SCRIPT = [
    ("Представь: выходит GTA шесть...", 0, 3),
    ("и интернет буквально сходит с ума.", 3, 7),
    ("Миллионы игроков одновременно заходят в игру.", 7, 12),
    ("YouTube заполняется трансляциями,", 12, 16),
    ("а TikTok — невероятными моментами.", 16, 20),
    ("Эту игру ждали больше десяти лет.", 20, 24),
    ("Но сможет ли GTA шесть стать главным событием интернета?", 24, 29),
    ("А ты будешь играть в первый же день?", 29, 33),
]

VOICE = "ru-RU-DmitryNeural"
AUDIO = OUT / "voice.mp3"
VIDEO = OUT / "background.mp4"
FINAL = OUT / "gta6_short.mp4"

def run(cmd):
    subprocess.run(cmd, check=True)

async def make_voice():
    text = " ".join(item[0] for item in SCRIPT)
    communicate = edge_tts.Communicate(text, VOICE, rate="+5%", volume="+0%")
    await communicate.save(str(AUDIO))

def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def make_frame(t):
    img = Image.new("RGB", (W, H))
    pixels = img.load()

    shift = int(t * 5)
    for y in range(H):
        for x in range(W):
            glow = max(0, 1 - abs(x - (W * 0.55 + shift)) / 900)
            glow2 = max(0, 1 - abs(y - (H * 0.35)) / 1000)
            pixels[x, y] = (
                int(8 + 22 * glow),
                int(8 + 5 * glow2),
                int(28 + 75 * glow + 35 * glow2),
            )

    draw = ImageDraw.Draw(img)
    title_font = get_font(74)
    small_font = get_font(34)

    draw.text((65, 130), "GTA VI", font=title_font, fill=(255, 95, 190))
    draw.text((68, 225), "VICE CITY // 2026", font=small_font, fill=(100, 220, 255))

    # Neon horizon
    horizon = 1180 + int(12 * __import__("math").sin(t * 1.2))
    draw.line((0, horizon, W, horizon), fill=(255, 70, 180), width=5)

    # Stylized skyline
    for i in range(12):
        x = i * 100 - 20
        height = 100 + ((i * 73) % 260)
        draw.rectangle(
            (x, horizon - height, x + 65, horizon),
            fill=(12, 13, 42),
            outline=(70, 80, 150),
            width=3
        )
        for wy in range(horizon - height + 25, horizon - 10, 45):
            draw.rectangle((x + 15, wy, x + 28, wy + 16), fill=(255, 170, 90))

    # Moving neon sun
    sun_y = 650 + int(22 * __import__("math").sin(t * 0.7))
    draw.ellipse((340, sun_y, 740, sun_y + 400), fill=(255, 95, 145))
    for yy in range(sun_y + 240, sun_y + 390, 32):
        draw.rectangle((340, yy, 740, yy + 10), fill=(20, 15, 45))

    # Caption
    caption = next((s for s, start, end in SCRIPT if start <= t < end), "")
    if caption:
        font = get_font(64)
        lines = textwrap.wrap(caption, width=25)
        line_height = 82
        total_h = len(lines) * line_height
        y = 1450 - total_h // 2

        draw.rounded_rectangle(
            (45, y - 35, 1035, y + total_h + 35),
            radius=28,
            fill=(5, 5, 18)
        )

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=2)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((W - tw) // 2, y),
                line,
                font=font,
                fill="white",
                stroke_width=2,
                stroke_fill=(0, 0, 0)
            )
            y += line_height

    return img

def make_background():
    frames_dir = OUT / "frames"
    frames_dir.mkdir(exist_ok=True)

    duration = 34
    for i in range(duration * FPS):
        frame = make_frame(i / FPS)
        frame.save(frames_dir / f"{i:05d}.jpg", quality=88)
        if i % 120 == 0:
            print(f"Rendering: {i // FPS}/{duration} sec")

    run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "%05d.jpg"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        str(VIDEO)
    ])

async def main():
    print("Creating Russian voice...")
    await make_voice()

    print("Creating animated vertical video...")
    make_background()

    print("Combining voice and video...")
    run([
        "ffmpeg", "-y",
        "-i", str(VIDEO),
        "-i", str(AUDIO),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(FINAL)
    ])

    print(f"SUCCESS: {FINAL}")

if __name__ == "__main__":
    asyncio.run(main())
