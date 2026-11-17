
import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_KEY = os.environ.get("YOUTUBE_API_KEY")

QUERIES = [
    "GTA 6",
    "Grand Theft Auto VI",
    "GTA 6 funny moments",
    "GTA 6 gameplay"
]

BASE_URL = "https://www.googleapis.com/youtube/v3/"


def youtube_request(endpoint, params):
    params["key"] = API_KEY
    url = BASE_URL + endpoint + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_live_streams():
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is missing!")

    video_ids = set()

    print("Searching for GTA 6 live streams...")

    for query in QUERIES:
        print(f"Searching: {query}")

        data = youtube_request("search", {
            "part": "snippet",
            "q": query,
            "type": "video",
            "eventType": "live",
            "order": "viewCount",
            "maxResults": 50
        })

        for item in data.get("items", []):
            video_ids.add(item["id"]["videoId"])

    if not video_ids:
        print("No live streams found.")
        return []

    videos = []

    ids = list(video_ids)

    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]

        data = youtube_request("videos", {
            "part": "snippet,liveStreamingDetails,statistics",
            "id": ",".join(batch)
        })

        videos.extend(data.get("items", []))

    results = []

    for video in videos:
        live = video.get("liveStreamingDetails", {})
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})

        if not live.get("concurrentViewers"):
            continue

        results.append({
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "url": f"https://www.youtube.com/watch?v={video['id']}",
            "viewers": int(live["concurrentViewers"]),
            "likes": int(statistics.get("likeCount", 0)),
            "started_at": live.get("actualStartTime", "")
        })

    results.sort(key=lambda x: x["viewers"], reverse=True)

    return results


def main():
    streams = find_live_streams()

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_streams": len(streams),
        "streams": streams
    }

    os.makedirs("results", exist_ok=True)

    with open("results/youtube_streams.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"\nFound {len(streams)} live streams.")

    for stream in streams[:10]:
        print(f"{stream['viewers']} viewers | {stream['title']}")
        print(stream["url"])


if __name__ == "__main__":
    main()
