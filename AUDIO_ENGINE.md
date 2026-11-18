# Audio engine and production voice policy

## Main video renderer
- The current no-cost candidate is the local Piper voice model `ru_RU-dmitri-medium`.
- The model is downloaded automatically into `assets/voices`; no account, API key or paid credits are needed.
- Piper is used as the only narration provider for a complete Short. There is no Edge TTS or Google TTS fallback.
- `output/audio_audit.json` records provider, model, line count and durations.
- The model is listed with an MIT license in the Piper voice catalogue. The model is medium quality; naturalness and expressive delivery still need human review.
- This is not the user's cloned voice and is not yet approved as the final reference-matching voice.

## Audio quality gates
- The voice-only preflight runs without downloading GTA gameplay or rendering a video.
- Any missing model, failed segment, or invalid audio file stops the build.
- No procedural placeholder SFX are used in production.
- The audio prototype's procedural impact/whoosh sounds remain rejected and must not be wired into the renderer.
- Music and SFX still require a reviewed, context-specific implementation. Do not claim production audio is ready.

## Test status (2026-11-18)
- Run #18 used a Google TTS fallback after Edge TTS failed and was rejected.
- A voice-only preflight on Edge TTS also failed after retries with `No audio was received`.
- The project is testing Piper as a local, no-key alternative. Do not launch a full video render until the voice sample has been inspected.
