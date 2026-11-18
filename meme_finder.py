#!/usr/bin/env python3
"""Find short, openly licensed meme/reaction footage for the current episode."""
import json, re, time, random, os, subprocess, sys
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "assets" / "memes"
MANIFEST = DEST / "sources.json"
API = "https://commons.wikimedia.org/w/api.php"
IA_SEARCH = "https://archive.org/advancedsearch.php"
IA_METADATA = "https://archive.org/metadata"
MAX_BYTES = 20 * 1024 * 1024
MAX_CLIPS = 6
S = requests.Session()
S.headers.update({"User-Agent": "GTA6ClipFactory/3.0 (openly licensed short-form edit assets)"})

# Current episode theme: wanted-level escalation, pursuit and escape.
# Broad "funny video" searches produced unrelated dance clips in run #18.
SEARCHES = [
    "car chase video", "goose chase video", "funny chase video",
    "slapstick chase video", "person running away video",
    "cartoon chase video", "vehicle escape video",
]
RELEVANT_TITLE = re.compile(
    r"goose|chase|chasing|pursuit|escape|run|running|car|vehicle|hide|hiding|"
    r"slapstick|cartoon",
    re.I
)
BAD = re.compile(
    r"death|dead|killed|shooting|fatal|murder|suicide|graphic|gore|war crime|"
    r"bodycam|body cam|police|cop|officer|arrest|traffic stop|deputy|sheriff",
    re.I
)
EXTS = (".mp4", ".webm", ".ogv", ".mov", ".mkv")
IA_SEARCHES = ("chase", "car", "escape", "runaway", "slapstick", "goose")
YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
YT_QUERIES = (
    "funny cartoon chase",
    "animated car chase",
    "slapstick chase",
    "goose chase funny",
)




def parse_iso_duration(value):
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def download_youtube_candidates(records):
    """Find and download only videos YouTube marks as Creative Commons."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YouTube CC search skipped: YOUTUBE_API_KEY is unavailable")
        return

    for query in YT_QUERIES:
        try:
            response = S.get(YT_SEARCH, params={
                "part": "snippet",
                "type": "video",
                "videoLicense": "creativeCommon",
                "maxResults": 10,
                "q": query,
                "key": api_key
            }, timeout=30)
            response.raise_for_status()
            search_items = response.json().get("items", [])
            video_ids = [
                item.get("id", {}).get("videoId")
                for item in search_items
                if item.get("id", {}).get("videoId")
            ]
            if not video_ids:
                continue

            details = S.get(YT_VIDEOS, params={
                "part": "snippet,contentDetails,status",
                "id": ",".join(video_ids),
                "key": api_key
            }, timeout=30)
            details.raise_for_status()
            for video in details.json().get("items", []):
                status = video.get("status", {})
                if status.get("license") != "creativeCommon":
                    continue
                if status.get("privacyStatus") != "public":
                    continue
                snippet = video.get("snippet", {})
                title = clean(snippet.get("title", ""))
                description = clean(snippet.get("description", ""))
                if BAD.search(title + " " + description):
                    continue
                if not RELEVANT_TITLE.search(title + " " + description):
                    continue
                duration = parse_iso_duration(video.get("contentDetails", {}).get("duration", ""))
                if not 5 <= duration <= 120:
                    continue

                video_id = video.get("id", "")
                filename = f"youtube_cc_{video_id}.mp4"
                path = DEST / filename
                if path.exists() and path.stat().st_size > 250_000:
                    records[filename] = {
                        "source_type": "youtube",
                        "video_id": video_id,
                        "title": title,
                        "file": filename,
                        "license": "Creative Commons Attribution (YouTube API verified)",
                        "creator": snippet.get("channelTitle", ""),
                        "source_page": f"https://www.youtube.com/watch?v={video_id}",
                        "approved_for_edit": bool(records.get(filename, {}).get("approved_for_edit", False))
                    }
                    continue

                try:
                    print("Downloading YouTube CC candidate:", title)
                    subprocess.run([
                        sys.executable, "-m", "yt_dlp",
                        "--no-warnings", "--no-playlist",
                        "--format", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
                        "--merge-output-format", "mp4",
                        "--max-filesize", f"{MAX_BYTES // (1024 * 1024)}M",
                        "--download-sections", "*0:25",
                        "--force-keyframes-at-cuts",
                        "--output", str(path),
                        f"https://www.youtube.com/watch?v={video_id}"
                    ], check=True, timeout=180)
                    if not path.exists() or path.stat().st_size < 250_000 or path.stat().st_size > MAX_BYTES:
                        raise ValueError("downloaded YouTube clip is empty or exceeds size limit")
                    records[filename] = {
                        "source_type": "youtube",
                        "video_id": video_id,
                        "title": title,
                        "file": filename,
                        "license": "Creative Commons Attribution (YouTube API verified)",
                        "creator": snippet.get("channelTitle", ""),
                        "source_page": f"https://www.youtube.com/watch?v={video_id}",
                        "approved_for_edit": False,
                        "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                except Exception as exc:
                    path.unlink(missing_ok=True)
                    print("Skip YouTube CC clip:", title, exc)
                if len(records) >= MAX_CLIPS:
                    return
        except Exception as exc:
            print("YouTube CC search failed:", query, exc)


def search_archive_candidates():
    """Find openly licensed movie items on Internet Archive; no API key is required."""
    found = []
    seen = set()
    for term in IA_SEARCHES:
        for license_query in ("licenseurl:http*by*",):
            query = f"mediatype:movies AND {license_query} AND title:{term}"
            try:
                response = S.get(IA_SEARCH, params={
                    "q": query,
                    "fl[]": ["identifier", "title", "licenseurl"],
                    "rows": 15,
                    "page": 1,
                    "output": "json"
                }, timeout=30)
                response.raise_for_status()
                docs = response.json().get("response", {}).get("docs", [])
            except Exception as exc:
                print("Archive.org search failed:", term, exc)
                continue

            for doc in docs:
                identifier = doc.get("identifier", "")
                if not identifier or identifier in seen:
                    continue
                seen.add(identifier)
                try:
                    meta_response = S.get(f"{IA_METADATA}/{identifier}", timeout=30)
                    meta_response.raise_for_status()
                    metadata = meta_response.json().get("metadata", {})
                    license_name = metadata.get("licenseurl") or doc.get("licenseurl", "")
                    rights = str(metadata.get("rights", ""))
                    if not license_ok(license_name):
                        continue

                    title = clean(metadata.get("title") or doc.get("title") or identifier)
                    if BAD.search(title) or not RELEVANT_TITLE.search(title):
                        continue

                    files = []
                    for item in meta_response.json().get("files", []):
                        name = item.get("name", "")
                        if not name.lower().endswith(EXTS):
                            continue
                        if item.get("private") == "true":
                            continue
                        size = int(item.get("size", 0) or 0)
                        if size and size > MAX_BYTES:
                            continue
                        files.append((size or MAX_BYTES, name))
                    if not files:
                        continue
                    files.sort(key=lambda entry: entry[0])
                    size, filename = files[0]
                    found.append({
                        "source_type": "archive.org",
                        "identifier": identifier,
                        "title": title,
                        "filename": filename,
                        "size": size,
                        "license": license_name or "Public domain (rights statement)",
                        "creator": clean(metadata.get("creator", "")),
                        "source_page": f"https://archive.org/details/{identifier}",
                        "url": f"https://archive.org/download/{identifier}/{quote(filename)}"
                    })
                except Exception as exc:
                    print("Archive.org metadata failed:", identifier, exc)
            time.sleep(0.5)
    return found


def clean(value):
    return re.sub(r"<[^>]*>", "", str(value or "")).strip()


def license_ok(value):
    value = (value or "").lower()
    if any(x in value for x in ("noncommercial", "non-commercial", "by-nc", "by-nd", "no derivatives")):
        return False
    return any(x in value for x in (
        "creativecommons.org/licenses/by/", "creativecommons.org/licenses/by-sa/",
        "creativecommons.org/publicdomain/zero", "cc by 4.0", "cc by-sa", "cc0"
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
    # Prefer YouTube's API-verified Creative Commons clips, then Archive.org, then Wikimedia.
    download_youtube_candidates(records)
    for item in search_archive_candidates():
        if len(records) >= MAX_CLIPS:
            break
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", item["identifier"] + "_" + item["filename"]).strip("_")[:90]
        extension = Path(item["filename"]).suffix.lower()
        filename = stem + extension
        path = DEST / filename
        if path.exists() and path.stat().st_size > 250_000:
            records[filename] = {
                **item, "file": filename,
                "approved_for_edit": bool(records.get(filename, {}).get("approved_for_edit", False))
            }
            continue
        try:
            print("Downloading Archive.org candidate:", item["title"])
            with S.get(item["url"], stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
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
                **item, "file": filename, "size": total,
                "approved_for_edit": False,
                "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except Exception as exc:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)
            print("Skip Archive.org clip:", exc)

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
            records[filename] = {
                **item, "file": filename,
                "approved_for_edit": bool(records.get(filename, {}).get("approved_for_edit", False))
            }
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
                "approved_for_edit": False,
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
