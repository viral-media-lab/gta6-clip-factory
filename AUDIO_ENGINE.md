# Audio engine and production voice policy

## Main video renderer
- The production renderer uses exactly one Edge TTS voice for the entire narration: `ru-RU-DmitryNeural` by default.
- The voice can be overridden with the `EDGE_TTS_VOICE` environment variable.
- Every line is retried up to three times. If any line fails, all partial/stale narration files are deleted and the build stops.
- No Google TTS or other provider fallback is allowed. A voice change inside one Short is a hard failure.
- The current Edge voice is only a temporary synthetic baseline. It is not the user's cloned voice and has not been approved as the final reference-matching voice.

## Audio quality gates
- The narration is generated before downloading the large GTA source video.
- `output/audio_audit.json` records provider, voice, line count and durations.
- No procedural placeholder SFX are used in production.
- The audio prototype's procedural impact/whoosh sounds remain rejected and must not be wired into the renderer.
- Music and SFX still require a reviewed, context-specific implementation. Do not claim production audio is ready.

## Test status (2026-11-18)
The previous successful video run #18 silently fell back to Google TTS after Edge TTS returned `No audio was received`. The user rejected the resulting voice and the unrelated Wikimedia meme cutaways. Run #18 is a technical artifact only, not an approved video.
