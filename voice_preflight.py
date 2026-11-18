#!/usr/bin/env python3
"""Generate and audit narration only. This never renders a video."""
import asyncio
import json
from pathlib import Path

import make_short


def main():
    durations = asyncio.run(make_short.make_voice())
    audit_path = make_short.OUTPUT_DIR / "audio_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("provider") != "edge-tts" or audit.get("fallback_used") is not False:
        raise RuntimeError("Voice preflight detected an unexpected provider or fallback")
    if audit.get("line_count") != len(make_short.SCRIPT):
        raise RuntimeError("Not every narration line was generated")
    if len(durations) != len(make_short.SCRIPT):
        raise RuntimeError("Narration duration audit is incomplete")
    print("VOICE_PREFLIGHT_OK")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
