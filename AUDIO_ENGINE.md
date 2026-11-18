# Audio engine prototype

## Purpose
Separate narration, music and sound effects into independent layers. This is a prototype and is not yet wired into the full video renderer.

## Voice
- Primary provider: Edge TTS, Russian voice `ru-RU-DmitryNeural`.
- Each phrase is synthesized separately with delivery presets: excited, angry, sarcastic, deadpan.
- Edge TTS is retried up to three times. If it continues to fail, gTTS is used as an emergency fallback.
- Important limitation: gTTS does not apply the Edge TTS rate/pitch presets and sounds like a different speaker. A mixed-provider result can therefore change voice mid-video.
- This is synthetic narration, not a clone of the user's voice.

## Sound layers
- Narration is assembled with explicit pauses.
- Short impact and whoosh sounds are generated as temporary procedural placeholders.
- Optional licensed music can be supplied as `assets/music/test_bed.mp3`. No third-party track is downloaded or assumed licensed.
- When a bed is present, it is mixed quietly under speech. Production ducking and side-chain tuning remain to be completed.

## Confirmed test — 2026-11-18
- Workflow run #3: https://github.com/viral-media-lab/gta6-clip-factory/actions/runs/44352628418
- Branch: `fix/audio-tts-retry-fallback`
- Commit: `e5f6ad7a077f35d8ee34fcae4a63caed2ca2d9cb`
- Artifact: `GTA6-Audio-Test` (ID `14447849809`).
- Rendered WAV: 18.1 seconds, stereo, 44.1 kHz.
- Audit: first line used Edge TTS; the remaining three lines used gTTS fallback.
- No music bed was present. SFX are placeholders.
- CI generation and artifact upload succeeded. This proves the technical fallback path works, not that the voice is approved for production.
- The WAV was checked for existence, duration, sample rate, peak and silence metrics. Human listening approval is still required.

## Run
`python audio_engine.py --test`

Output: `output/audio_test/audio_test.wav` and `audio_audit.json`.

Do not connect this to the full video render until the voice has been listened to and approved. The generated SFX are temporary technical placeholders, not the final sound library.
