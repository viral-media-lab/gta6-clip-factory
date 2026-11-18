# Audio engine prototype

## Purpose
Separate narration, music and sound effects into independent layers. This is a prototype and is not yet wired into the full video renderer.

## Voice
- Edge TTS Russian male voice: ru-RU-DmitryNeural.
- Each phrase is synthesized separately with delivery presets: excited, angry, sarcastic, deadpan.
- Rate and pitch vary by delivery. These are expressive presets, not a voice clone.
- A single provider is used throughout; there is no Google TTS fallback that changes the speaker mid-video.

## Sound layers
- Narration is assembled with explicit pauses.
- Short impact and whoosh placeholders are generated and positioned from event timestamps.
- Optional licensed music can be supplied as assets/music/test_bed.mp3. No third-party track is downloaded or assumed licensed.
- When a bed is present, it is mixed quietly under speech. Production ducking and side-chain tuning remain to be completed.

## Test
Run: python audio_engine.py --test

Output: output/audio_test/audio_test.wav and audio_audit.json.

Do not connect this to the full video render until the audio has been listened to and approved. The generated SFX are temporary technical placeholders, not the final sound library.
