#!/usr/bin/env python3
"""Find and download reusable police video from Wikimedia Commons.

Only downloads files with an explicit reuse-friendly license:
Public domain, CC0, CC BY, or CC BY-SA. Files with NC or ND terms are
excluded because this project edits and monetizes video.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

ROOT = Path(__file__).resolve().parent
BODYCAM_DIR = ROOT / "assets" / "bodycam"
MANIFEST = BODYCAM_DIR / "sources.json"

API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "GTA6ClipFactory/1.0 (automated media discovery; contact: project maintainer)"
SEARCH_TERMS = [
    '"police body camera"',
    '"body-worn camera" police',
    '"police dashcam"',
    '"police pursuit"',
]
MAX_DOWNLOADS = 3
MAX_FILE_BYTES = 180 * 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogv", ".ogg", ".mov", ".mkv"}


def request_json(params):
    response = requests.get(
        API_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def license_is_reusable(extmetadata):
    raw = extmetadata.get("LicenseShortName", {}).get("value", "")
    license_name = re.sub(r"<[^>]+>", "", raw).strip().lower()

    # Non-commercial and no-derivatives licenses are unsuitable here.
    if "nc" in license_name or "nd" in license_name:
        return False, license_name

    allowed = (
        "public domain" in license_name
        or "cc0" in license_name
        or "cc by" in license_name
        or "cc-by" in license_name
    )
    return allowed, license_name


def search_commons(term):
    data = request_json({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:video {term}",
        "gsrnamespace": 6,
        "gsrlimit": 30,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    })
    pages = data.get("query", {}).get("pages", {})
    return list(pages.values())


def safe_filename(title, extension):
    stem = title.rsplit(":", 1)[-1]
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_")
    return (stem[:70] or "commons_video") + extension.lower()


def download_candidate(page):
    title = page.get("title", "")
    imageinfo = (page.get("imageinfo") or [{}])[0]
    url = imageinfo.get("url", "")
    metadata = imageinfo.get("extmetadata", {})

    allowed, license_name = license_is_reusable(metadata)
    if not allowed or not url:
        return None

    extension = Path(urlparse(url).path).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        return None

    BODYCAM_DIR.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(title, extension)
    destination = BODYCAM_DIR / filename

    if destination.exists() and destination.stat().st_size > 1024 * 1024:
        return None

    with requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        stream=True,
        timeout=(20, 90),
    ) as response:
        response.raise_for_status()
        length = int(response.headers.get("Content-Length", "0"))
        if length and length > MAX_FILE_BYTES:
            print(f"Skip oversized file: {title}")
            return None

        downloaded = 0
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > MAX_FILE_BYTES:
                    output.close()
                    destination.unlink(missing_ok=True)
                    print(f"Skip oversized stream: {title}")
                    return None
                output.write(chunk)

    if destination.stat().st_size < 256 * 1024:
        destination.unlink(missing_ok=True)
        return None

    record = {
        "file": filename,
        "commons_title": title,
        "source_url": url,
        "description_page": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
        "license": license_name,
        "creator": metadata.get("Artist", {}).get("value", ""),
        "attribution_required": "cc by" in license_name or "cc-by" in license_name,
        "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return record


def main():
    BODYCAM_DIR.mkdir(parents=True, exist_ok=True)
    found = []
    seen = set()

    print("Searching Wikimedia Commons for reusable police footage...")

    for term in SEARCH_TERMS:
        if len(found) >= MAX_DOWNLOADS:
            break
        print(f"Search: {term}")
        try:
            pages = search_commons(term)
        except Exception as error:
            print(f"Search failed ({term}): {error}")
            continue

        for page in pages:
            title = page.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)

            try:
                record = download_candidate(page)
                if record:
                    found.append(record)
                    print(f"Downloaded: {record['file']} [{record['license']}]")
                    if len(found) >= MAX_DOWNLOADS:
                        break
            except Exception as error:
                print(f"Download failed ({title}): {error}")

    existing = []
    if MANIFEST.exists():
        try:
            existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    by_file = {item.get("file"): item for item in existing if item.get("file")}
    for item in found:
        by_file[item["file"]] = item

    MANIFEST.write_text(
        json.dumps(list(by_file.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"New reusable videos: {len(found)}")
    print(f"Manifest: {MANIFEST}")
    if not found:
        print("No qualifying video found. Existing assets were left untouched.")


if __name__ == "__main__":
    main()
