# GTA 6 SHORTS FACTORY — PROJECT MEMORY
Version: 1.2
Updated: 2026-11-18

## 1. Mission
Build an automated factory for viral Russian-language GTA 6 YouTube Shorts:
topic research → script → game footage and relevant meme cutaways → narration → edit → captions → QA → MP4.

A green CI status is not proof of a good video. Never mark a Short ready before reviewing the actual MP4 and audio.

## 2. Creative direction
- Full-frame vertical 9:16, 1080×1920.
- Usually around 30 seconds; pace must stay tight.
- Provocative hook from the first seconds, bold absurd/post-ironic humor.
- GTA gameplay as the visual base, with real meme/reaction footage only when it matches the spoken line.
- Dynamic edits and large synchronized subtitles with highlighted punch words.
- Lively emotional Russian narration. The user's own voice is the long-term priority.
- Music stays under the voice; SFX are sparse and contextual.
- No police/bodycam footage or sirens. This concept was explicitly abandoned.
- No blurred-background layout with a narrow horizontal gameplay strip.
- No Rockstar rating cards or logo intro.
- Do not use random dance/animal clips as memes merely because a search returned them.
- Do not use procedural impact/whoosh placeholders in production; the user rejected those sounds.

## 3. Work rules
- Before code changes, fetch current GitHub files and SHAs.
- Prefer automatic work; do not ask the user to download/upload or configure anything unless unavoidable.
- No unnecessary full renders.
- If required assets or narration are missing, stop with a clear error.
- Verify logs, artifacts, and the actual MP4 after changes.
- Be explicit about limitations and what has actually been tested.
- Update this document after significant project changes.

## 4. Repository
https://github.com/viral-media-lab/gta6-clip-factory

Important files:
- `youtube_scan.py`: topic discovery and ranking.
- `.github/workflows/youtube_scan.yml`: scheduled/manual topic scanner.
- `make_short.py`: video assembly.
- `meme_finder.py`: open-license meme/reaction footage discovery.
- `.github/workflows/make_short.yml`: video generation.
- `audio_engine.py` and `.github/workflows/audio_test.yml`: isolated audio prototype, not approved for production.
- `AUDIO_ENGINE.md`: voice/audio policy.

## 5. Topic scanner
The YouTube Data API scanner has previously produced a ranked JSON list of GTA 6 topics. Historical scan counts are not current performance metrics. The workflow uses the `YOUTUBE_API_KEY` secret.

## 6. Video generation status
### Run #18 — reviewed 2026-11-18
Workflow: https://github.com/viral-media-lab/gta6-clip-factory/actions/runs/44198823575
Commit: `47611ac33384f89b770b5609754bc102f1c2d3b5`
Artifact: `GTA6-Short`, downloaded and inspected.

Technical properties:
- MP4 exists and opens.
- H.264, 1080×1920, 30 fps.
- AAC mono, 24 kHz.
- Duration: 43.8 seconds.
- File size: 35,450,148 bytes.

Quality failures:
- The opening includes the age-rating card and Rockstar logo.
- Edge TTS failed with `No audio was received`; the script switched to Google TTS for the entire narration.
- The resulting voice was rejected by the user.
- Meme discovery selected unrelated clips: a fire hula-hoop dance, an Untitled Goose Game-related clip, and Lindy Hop dancing.
- Wikimedia returned many HTTP 429 responses.
- The Short is a technical artifact only and is NOT approved for publication.

## 7. Audio decisions
- No Google TTS fallback. A voice provider failure must stop the build.
- Current Edge voice `ru-RU-DmitryNeural` is only a temporary synthetic baseline, not the user's voice and not final approval.
- Retry the same Edge voice up to three times per line; if any line fails, delete partial/stale narration and stop.
- Do not silently switch voices.
- The user has not supplied a voice sample. Do not claim voice cloning is active.
- Do not add a paid provider or assume an API key/credits are available without explicit approval.
- Procedural SFX from the audio prototype are rejected. No random SFX in production.
- Four user reference Shorts are recorded in prior project context; do not claim to have watched/listened unless actually accessible.

## 8. Current code branch under review
Branch: `fix/single-voice-fail-fast`

Changes made on this branch:
- Removed Google TTS fallback and the unused `gTTS` dependency.
- One Edge voice is used for every line; each line retries up to three times.
- Build stops on any narration failure and removes partial/stale voice files.
- Writes `output/audio_audit.json` with provider, voice and duration details.
- Narration validation runs before downloading large gameplay media.
- Gameplay shot selection skips the first 3.5 seconds of the official trailer to avoid its rating/title cards.
- Meme discovery and insertion now filter titles toward chase/escape/vehicle/hiding relevance; unrelated dance clips are rejected.
- These changes are not yet merged and have not yet been validated by a new workflow run or a new MP4.

## 9. Open pull requests
- PR #2 (`Fix audio prototype TTS failures`) remains open and must NOT be merged as-is. It contains a Google fallback and the audio prototype that the user rejected.
- The new branch above is intended to become a separate review PR after static verification.

## 10. Next steps
1. Verify the current branch files and run static/syntax checks.
2. Open a focused PR for the single-voice fail-fast and relevant-meme gates.
3. Run only a short narration/preflight test first, not a full video render.
4. Confirm the voice path does not fall back to Google and that the audit records one provider.
5. Improve meme discovery so it returns genuinely relevant, licensed cutaways. If fewer than two usable clips exist, stop instead of inserting unrelated footage.
6. Improve the final voice toward the reference style. Do not pay for a provider or assume a secret exists without approval.
7. Only after voice and meme assets pass review, run one full video build and inspect the MP4 frame-by-frame and by listening.

## 11. Release checklist
- MP4 opens, correct 9:16 resolution and expected duration.
- No rating card, Rockstar logo intro, black frames or frozen frames.
- Hook lands immediately.
- GTA gameplay fills the frame.
- Meme clips are relevant to the line they accompany.
- Editing is fast but coherent.
- Captions are synchronized, readable and not cropped.
- One consistent voice; no fallback provider.
- Music sits below narration; SFX are intentional and reviewed.
- Actual video and audio have been inspected before release.

---
This document is the current source of truth. Re-check GitHub state at the start of every new work session.
