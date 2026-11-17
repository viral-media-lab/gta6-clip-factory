#!/usr/bin/env python3
"""Fetch short, non-graphic, openly licensed police/pursuit footage from Wikimedia Commons."""
import json, re, time
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "assets" / "bodycam"
MANIFEST = DEST / "sources.json"
API = "https://commons.wikimedia.org/w/api.php"
MAX_BYTES = 55 * 1024 * 1024
MAX_CLIPS = 5
S = requests.Session()
S.headers.update({"User-Agent": "GTA6ClipFactory/4.0 (openly licensed short-form edit assets)"})
SEARCHES = [
    "police body camera footage", "police car dash camera video",
    "police pursuit video", "police traffic stop video", "police patrol video"
]
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
    r = S.get(API, params={
        "action":"query", "format":"json", "generator":"search",
        "gsrsearch":f"filetype:video {term}", "gsrnamespace":6, "gsrlimit":40,
        "prop":"imageinfo", "iiprop":"url|extmetadata|size"
    }, timeout=35)
    r.raise_for_status()
    return list(r.json().get("query",{}).get("pages",{}).values())

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    previous = []
    if MANIFEST.exists():
        try: previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception: pass
    records = {x.get("file"):x for x in previous if x.get("file") and (DEST/x.get("file","")).exists()}
    seen, candidates = set(), []
    for term in SEARCHES:
        try: pages = search(term)
        except Exception as exc:
            print("Commons police search failed:",term,exc)
            continue
        for page in pages:
            title = page.get("title","")
            if title in seen or BAD.search(title):
                continue
            seen.add(title)
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("url","")
            meta = info.get("extmetadata",{})
            lic = clean(meta.get("LicenseUrl",{}).get("value") or meta.get("LicenseShortName",{}).get("value"))
            size = int(info.get("size",0) or 0)
            if not url.lower().split("?")[0].endswith(EXTS) or not license_ok(lic):
                continue
            if size and size > MAX_BYTES:
                continue
            candidates.append({
                "title":clean(title), "url":url, "license":lic,
                "creator":clean(meta.get("Artist",{}).get("value","")),
                "source_page":"https://commons.wikimedia.org/wiki/"+quote(title.replace(" ","_"))
            })
    for item in candidates:
        if len(records) >= MAX_CLIPS:
            break
        stem = re.sub(r"[^a-zA-Z0-9_-]+","_",item["title"]).strip("_")[:55] or "police_clip"
        ext = Path(item["url"].split("?")[0]).suffix.lower()
        filename = stem+ext
        path = DEST/filename
        if path.exists() and path.stat().st_size > 300_000:
            continue
        try:
            print("Downloading licensed police footage:",item["title"])
            with S.get(item["url"],stream=True,timeout=(20,90)) as response:
                response.raise_for_status()
                length = int(response.headers.get("Content-Length","0") or 0)
                if length and length > MAX_BYTES:
                    continue
                total = 0
                tmp = path.with_suffix(path.suffix+".part")
                with tmp.open("wb") as out:
                    for chunk in response.iter_content(512*1024):
                        if not chunk: continue
                        total += len(chunk)
                        if total > MAX_BYTES: raise ValueError("clip exceeds size limit")
                        out.write(chunk)
                if total < 300_000: raise ValueError("clip too small")
                tmp.replace(path)
            records[filename] = {**item,"file":filename,"downloaded_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
        except Exception as exc:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix+".part").unlink(missing_ok=True)
            print("Skip police clip:",exc)
    MANIFEST.write_text(json.dumps(list(records.values()),ensure_ascii=False,indent=2),encoding="utf-8")
    print("Licensed police clips ready:",len(records))

if __name__ == "__main__":
    main()
