#!/usr/bin/env python3
"""Discover reusable, non-graphic police pursuit/bodycam clips.
Only explicit public-domain/CC0/CC-BY/CC-BY-SA licensing is accepted.
Internet Archive is tried first; Wikimedia Commons is a fallback.
"""
import json, re, time, random
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "assets" / "bodycam"
MANIFEST = DEST / "sources.json"
UA = "GTA6ClipFactory/2.0 (automated media discovery)"
MAX_BYTES = 180 * 1024 * 1024
MAX_CLIPS = 3
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})

SEARCHES = [
    '"police body camera" AND (pursuit OR chase OR traffic stop)',
    '"police dashcam" AND (pursuit OR chase)',
    '"police pursuit" AND video',
    '"body worn camera" police arrest',
]
BAD = re.compile(r"death|dead|killed|shooting|fatal|murder|suicide|execution|officer.involved.death", re.I)
GOOD = re.compile(r"police|body.?cam|body.?worn|dash.?cam|pursuit|traffic stop|chase", re.I)

def license_ok(value):
    s = (value or "").lower()
    if any(x in s for x in ("noncommercial", "non-commercial", "by-nc", "by-nd", "no derivatives", "all rights reserved")):
        return False
    return any(x in s for x in ("creativecommons.org/licenses/by/", "creativecommons.org/publicdomain/zero", "creativecommons.org/publicdomain/mark", "public domain", "cc by 4.0", "cc by-sa", "cc0"))

def clean(s):
    return re.sub(r"<[^>]*>", "", str(s or "")).strip()

def get(url, params=None, stream=False):
    last = None
    for attempt in range(4):
        try:
            r = SESSION.get(url, params=params, timeout=(20, 90), stream=stream)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep((2 ** attempt) + random.random())
                last = requests.HTTPError(f"HTTP {r.status_code}")
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            if attempt < 3:
                time.sleep((2 ** attempt) + random.random())
    raise last

def safe_name(title, ext):
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", title).strip("_")[:65] or "police_clip"
    return stem + ext.lower()

def save_stream(url, path):
    tmp = path.with_suffix(path.suffix + ".part")
    total = 0
    with get(url, stream=True) as r, tmp.open("wb") as f:
        length = int(r.headers.get("Content-Length", "0") or 0)
        if length and length > MAX_BYTES:
            raise ValueError("file exceeds size limit")
        for chunk in r.iter_content(1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError("stream exceeds size limit")
            f.write(chunk)
    if total < 300_000:
        tmp.unlink(missing_ok=True)
        raise ValueError("file too small")
    tmp.replace(path)

def archive_search(query):
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": f'mediatype:movies AND ({query})',
        "fl[]": ["identifier", "title", "description"],
        "rows": 30, "page": 1, "output": "json",
    }
    data = get(url, params=params).json()
    return data.get("response", {}).get("docs", [])

def archive_license(meta):
    for key in ("licenseurl", "rights", "license", "rightsurl"):
        val = meta.get(key)
        if val and license_ok(str(val)):
            return str(val)
    return ""

def archive_candidates():
    seen = set()
    for query in SEARCHES:
        print("Internet Archive search:", query)
        try:
            docs = archive_search(query)
        except Exception as e:
            print("Archive search failed:", e)
            continue
        for doc in docs:
            ident = doc.get("identifier", "")
            title = clean(doc.get("title", ""))
            desc = clean(doc.get("description", ""))
            text = title + " " + desc
            if not ident or ident in seen or BAD.search(text) or not GOOD.search(text):
                continue
            seen.add(ident)
            try:
                meta = get(f"https://archive.org/metadata/{quote(ident)}").json()
                metadata = meta.get("metadata", {})
                lic = archive_license(metadata)
                if not lic:
                    continue
                files = meta.get("files", [])
                candidates = [f for f in files if str(f.get("name","")).lower().endswith((".mp4",".webm",".mov",".m4v"))]
                candidates.sort(key=lambda f: int(f.get("size", 0) or 0))
                for item in candidates:
                    size = int(item.get("size", 0) or 0)
                    if size and size > MAX_BYTES:
                        continue
                    name = item["name"]
                    url = f"https://archive.org/download/{quote(ident)}/{quote(name)}"
                    yield {"title": title, "identifier": ident, "url": url, "license": lic,
                           "creator": clean(metadata.get("creator","")), "description": desc[:500],
                           "source_page": f"https://archive.org/details/{ident}"}
                    break
            except Exception as e:
                print(f"Archive metadata failed ({ident}):", e)

def commons_candidates():
    api = "https://commons.wikimedia.org/w/api.php"
    terms = ['"police pursuit" video', '"police dashcam" video', '"body-worn camera" police']
    seen = set()
    for term in terms:
        print("Wikimedia search:", term)
        try:
            data = get(api, params={
                "action":"query","format":"json","generator":"search",
                "gsrsearch":f"filetype:video {term}","gsrnamespace":6,"gsrlimit":30,
                "prop":"imageinfo","iiprop":"url|extmetadata"
            }).json()
        except Exception as e:
            print("Wikimedia search failed:", e)
            continue
        for page in data.get("query",{}).get("pages",{}).values():
            title = page.get("title","")
            if title in seen or BAD.search(title) or not GOOD.search(title):
                continue
            seen.add(title)
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata",{})
            lic = clean(meta.get("LicenseUrl",{}).get("value") or meta.get("LicenseShortName",{}).get("value"))
            url = info.get("url","")
            if not url or not license_ok(lic):
                continue
            if not url.lower().split("?")[0].endswith((".mp4",".webm",".ogv",".mov",".mkv")):
                continue
            yield {"title":title,"url":url,"license":lic,
                   "creator":clean(meta.get("Artist",{}).get("value","")),
                   "description":"","source_page":"https://commons.wikimedia.org/wiki/"+title.replace(" ","_")}

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    records = []
    existing = []
    if MANIFEST.exists():
        try: existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception: existing = []
    known = {r.get("file"): r for r in existing if r.get("file")}
    candidates = list(archive_candidates())
    candidates.extend(list(commons_candidates()))
    for item in candidates:
        if len(records) >= MAX_CLIPS:
            break
        title = item["title"]
        if BAD.search(title) or not GOOD.search(title):
            continue
        ext = Path(item["url"].split("?")[0]).suffix.lower()
        if ext not in (".mp4",".webm",".mov",".m4v",".ogv",".mkv"):
            continue
        filename = safe_name(title, ext)
        path = DEST / filename
        if path.exists() and path.stat().st_size > 300_000:
            continue
        try:
            print("Downloading licensed police footage:", title)
            save_stream(item["url"], path)
            record = {
                "file": filename, "title": title, "source_url": item["url"],
                "source_page": item["source_page"], "license": item["license"],
                "creator": item.get("creator",""), "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            known[filename] = record
            records.append(record)
            print("Downloaded:", filename, "|", item["license"])
        except Exception as e:
            (DEST / filename).unlink(missing_ok=True)
            print("Download failed:", title, "|", e)
    MANIFEST.write_text(json.dumps(list(known.values()),ensure_ascii=False,indent=2),encoding="utf-8")
    print("New reusable police videos:",len(records))
    if not any((DEST / r.get("file","")).exists() for r in known.values()):
        raise SystemExit("No reusable police footage available. Refusing to generate a GTA-only Short.")

if __name__ == "__main__":
    main()
