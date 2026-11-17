
import os
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("YOUTUBE_API_KEY")

# Темы, по которым ищем популярные видео
QUERIES = [
    "GTA 6",
    "GTA VI",
    "GTA 6 новости",
    "GTA 6 теория",
    "GTA 6 reaction"
]

DAYS_BACK = 30
MAX_RESULTS = 50

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


def parse_duration(duration):
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration
    )

    if not match:
        return 0

    hours, minutes, seconds = match.groups()

    return (
        int(hours or 0) * 3600
        + int(minutes or 0) * 60
        + int(seconds or 0)
    )


def is_relevant(video):
    snippet = video.get("snippet", {})

    title = snippet.get("title", "").lower()
    description = snippet.get("description", "").lower()

    text = title + " " + description

    keywords = [
        "gta 6",
        "gta6",
        "gta vi",
        "grand theft auto vi",
        "гта 6",
        "гта6"
    ]

    if not any(keyword in text for keyword in keywords):
        return False

    # Убираем явно посторонний контент
    excluded = [
        "roblox",
        "minecraft",
        "gta 6 in roblox"
    ]

    if any(word in title for word in excluded):
        return False

    return True


def find_videos():
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is missing!")

    published_after = (
        datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")

    video_ids = set()

    print("Searching for popular GTA 6 videos...")

    for query in QUERIES:
        print(f"Searching: {query}")

        data = youtube_request("search", {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after,
            "maxResults": MAX_RESULTS
        })

        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")

            if video_id:
                video_ids.add(video_id)

    if not video_ids:
        print("No videos found.")
        return []

    videos = []
    ids = list(video_ids)

    print(f"\nFound {len(ids)} unique videos. Getting statistics...")

    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]

        data = youtube_request("videos", {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch)
        })

        videos.extend(data.get("items", []))

    results = []
    now = datetime.now(timezone.utc)

    for video in videos:
        if not is_relevant(video):
            continue

        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        content = video.get("contentDetails", {})

        published_at = snippet.get("publishedAt", "")

        try:
            published = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            )
            age_hours = max(
                (now - published).total_seconds() / 3600,
                1
            )
        except (ValueError, TypeError):
            age_hours = 1

        views = int(statistics.get("viewCount", 0))
        likes = int(statistics.get("likeCount", 0))
        comments = int(statistics.get("commentCount", 0))

        views_per_hour = round(views / age_hours, 1)

        results.append({
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "url": f"https://www.youtube.com/watch?v={video['id']}",
            "views": views,
            "likes": likes,
            "comments": comments,
            "views_per_hour": views_per_hour,
            "published_at": published_at,
            "duration_seconds": parse_duration(
                content.get("duration", "")
            ),
            "description": snippet.get("description", "")[:1500]
        })

    # Сначала ролики с самой высокой скоростью набора просмотров
    results.sort(
        key=lambda x: x["views_per_hour"],
        reverse=True
    )

    return results


def main():
    videos = find_videos()

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_videos": len(videos),
        "videos": videos
    }

    os.makedirs("results", exist_ok=True)

    with open(
        "results/youtube_streams.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"\nFound {len(videos)} relevant videos.")

    for video in videos[:20]:
        print(
            f"\n{video['views']:,} views | "
            f"{video['views_per_hour']} views/hour"
        )
        print(video["title"])
        print(video["url"])


if __name__ == "__main__":
    main()
