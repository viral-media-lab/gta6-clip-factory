#!/usr/bin/env python3
"""Find short, openly licensed meme/reaction footage for the current episode."""
import json, re, time, random
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "assets" / "memes"
MANIFEST = DEST / "sources.json"
API = "https://commons.wikimedia.org/w/api.php"
MAX_BYTES = 20 * 1024 * 1024
MAX_CLIPS = 5
S = requests.Session()
S.headers.update({"User-Agent": "GTA6ClipFactory/3.0 (openly licensed short-form edit assets)"})

# Current episode theme: wanted-level escalation, pursuit and escape.
# Broad "funny video" searches produced unrelated dance clips in run #18.
SEARCHES = [
    "goose chasing people video", "funny goose chase video",
    "animal chasing person video", "person running away funny video",
    "car chase comedy video", "funny vehicle escape video",
    "hide and seek running away video",
]
RELEVANT_TITLE = re.compile(
    r"goose|chase|chasing|pursuit|escape|runaway|running away|car|vehicle|hide|hiding",
    re.I
)
BAD = re.compile(r"death|dead|killed|shooting|fatal|murder|suicide|graphic|gore|war crime", re.I)
EXTS = (".mp4", ".webm", ".ogv", ".mov", ".mkv")


def clean(value):
    return re.sub(r"<[^>]*>", "", str(value or "")).strip()


def license_ok(value):
    value = (value or "").lower()
    if any(x in value for x in ("noncommercial", "non-commercial", "by-nc", "by-nd", "no derivatives")):
        return False
    return any(x in value for x in (
        "creativecommons.org/licenses/by/", "creativecommons.org/licenses/by-sa/",
        "creativecommons.org/publicdomain/zero", "creativecommons.org/publicdomain/mark",
        "cc by 4.0", "cc by-sa", "cc0", "public domain"
    ))


def search(term):
    response = S.get(API, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:video {term}", "gsrnamespace": 6, "gsrlimit": 35,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size"
    }, timeout=35)
    response.raise_for_status()
    return list(response.json().get("query", {}).get("pages", {}).values())


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    old = []
    if MANIFEST.exists():
        try:
            old = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Keep only previously downloaded assets that still match this episode's theme.
    records = {
        item.get("file"): item for item in old
        if item.get("file")
        and RELEVANT_TITLE.search(item.get("title", ""))
        and (DEST / item.get("file", "")).exists()
    }
    seen, candidates = set(), []
    for term in SEARCHES:
        try:
            pages = search(term)
        except Exception as exc:
            print("Commons search failed:", term, exc)
            time.sleep(1.2)
            continue
        for page in pages:
            title = page.get("title", "")
            if title in seen or BAD.search(title) or not RELEVANT_TITLE.search(title):
                continue
            seen.add(title)
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("url", "")
            metadata = info.get("extmetadata", {})
            license_name = clean(
                metadata.get("LicenseUrl", {}).get("value")
                or metadata.get("LicenseShortName", {}).get("value")
            )
            size = int(info.get("size", 0) or 0)
            if not url.lower().split("?")[0].endswith(EXTS) or not license_ok(license_name):
                continue
            if size and size > MAX_BYTES:
                continue
            candidates.append({
                "title": clean(title),
                "url": url,
                "license": license_name,
                "creator": clean(metadata.get("Artist", {}).get("value", "")),
                "source_page": "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"))
            })
        time.sleep(1.2)

    random.Random(61).shuffle(candidates)
    for item in candidates:
        if len(records) >= MAX_CLIPS:
            break
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", item["title"]).strip("_")[:55] or "odd_clip"
        extension = Path(item["url"].split("?")[0]).suffix.lower()
        filename = stem + extension
        path = DEST / filename
        if path.exists() and path.stat().st_size > 250_000:
            records[filename] = {**item, "file": filename}
            continue
        try:
            print("Downloading relevant meme/reaction clip:", item["title"])
            with S.get(item["url"], stream=True, timeout=(20, 90)) as response:
                response.raise_for_status()
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length and length > MAX_BYTES:
                    continue
                total = 0
                temporary = path.with_suffix(path.suffix + ".part")
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(512 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError("clip exceeds size limit")
                        output.write(chunk)
                if total < 250_000:
                    raise ValueError("clip too small")
                temporary.replace(path)
            records[filename] = {
                **item, "file": filename,
                "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except Exception as exc:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)
            print("Skip clip:", exc)

    MANIFEST.write_text(
        json.dumps(list(records.values()), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("Relevant meme/reaction clips ready:", len(records))


if __name__ == "__main__":
    main()
