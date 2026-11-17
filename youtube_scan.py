
import os
import json
import re
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3/"

QUERIES = [
    "GTA 6",
    "GTA VI",
    "GTA 6 новости",
    "GTA 6 теория",
    "GTA 6 reaction",
    "GTA 6 сравнение",
    "GTA 6 детали"
]

DAYS_BACK = 30
MAX_RESULTS = 50

EXCLUDED_WORDS = [
    "roblox", "minecraft", "pre-load", "preload",
    "unboxing", "countdown", "live stream",
    "24 hours left", "tomorrow", "buying gta 6"
]

OFFICIAL_CHANNELS = [
    "rockstar games", "playstation", "xbox"
]


def youtube_request(endpoint, params):
    params["key"] = API_KEY
    url = BASE_URL + endpoint + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_duration(duration):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    h, m, s = match.groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)


def is_relevant(video):
    snippet = video.get("snippet", {})
    title = snippet.get("title", "").lower()
    description = snippet.get("description", "").lower()
    text = title + " " + description

    keywords = [
        "gta 6", "gta6", "gta vi",
        "grand theft auto vi", "гта 6", "гта6"
    ]

    if not any(word in text for word in keywords):
        return False

    if any(word in title for word in EXCLUDED_WORDS):
        return False

    channel = snippet.get("channelTitle", "").lower()
    if channel in OFFICIAL_CHANNELS:
        return False

    return True


def make_idea(title):
    t = title.lower()

    if "fps" in t or "frame rate" in t or "30 fps" in t:
        return {
            "topic": "Производительность и 30 FPS",
            "hook": "Ты ждёшь GTA 6 больше десяти лет. Но готов ли ты играть в неё при 30 FPS?",
            "angle": "Разобрать влияние частоты кадров на плавность и управление. Отделить подтверждённые данные от слухов."
        }

    if "map" in t or "карта" in t or "empty" in t:
        return {
            "topic": "Карта GTA 6",
            "hook": "А что, если огромная карта GTA 6 окажется не такой интересной, как кажется?",
            "angle": "Сравнить известные детали карты и обсудить плотность мира."
        }

    if "rob" in t or "store" in t or "магазин" in t or "ограб" in t:
        return {
            "topic": "Ограбления и интерактивность",
            "hook": "В GTA 6 даже обычное ограбление магазина может стать отдельным приключением.",
            "angle": "Разобрать показанные механики и сравнить их с GTA 5."
        }

    if "empathy" in t or "эмпат" in t or "character" in t:
        return {
            "topic": "Персонажи и эмоции",
            "hook": "А если главная особенность GTA 6 — не графика, а живые персонажи?",
            "angle": "Обсудить анимации, отношения героев и эмоциональную подачу."
        }

    if "gta 5" in t and "gta 6" in t:
        return {
            "topic": "GTA 5 против GTA 6",
            "hook": "Пять отличий GTA 6 от GTA 5, которые легко пропустить.",
            "angle": "Сравнить конкретные детали двух игр."
        }

    return {
        "topic": title[:100],
        "hook": "Все обсуждают GTA 6, но эту деталь многие могли пропустить.",
        "angle": "Проверить утверждение из ролика, найти подтверждения и объяснить зрителю."
    }


def find_videos():
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is missing!")

    published_after = (
        datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")

    video_ids = set()

    print("Searching for GTA 6 trends...")

    for query in QUERIES:
        print("Searching:", query)

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

    print("Unique videos:", len(video_ids))

    videos = []
    ids = list(video_ids)

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
        stats = video.get("statistics", {})
        content = video.get("contentDetails", {})

        title = snippet.get("title", "")
        channel = snippet.get("channelTitle", "")
        published_at = snippet.get("publishedAt", "")

        try:
            published = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            )
            age_hours = max((now - published).total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            age_hours = 1

        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        duration = parse_duration(content.get("duration", ""))

        if duration < 15 or duration > 900:
            continue

        views_per_hour = views / age_hours
        comment_rate = comments / max(views, 1)
        russian = bool(re.search(r"[а-яё]", title.lower()))

        # Рейтинг учитывает скорость просмотров и активность комментариев
        score = (
            math.log1p(views_per_hour) * 10
            + math.log1p(comments) * 1.5
            + min(comment_rate * 10000, 10)
            + (8 if russian else 0)
        )

        idea = make_idea(title)

        results.append({
            "title": title,
            "channel": channel,
            "url": "https://www.youtube.com/watch?v=" + video["id"],
            "views": views,
            "likes": likes,
            "comments": comments,
            "views_per_hour": round(views_per_hour, 1),
            "published_at": published_at,
            "duration_seconds": duration,
            "russian_title": russian,
            "score": round(score, 2),
            **idea
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def main():
    results = find_videos()

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_videos": len(results),
        "top_ideas": results[:10],
        "all_videos": results
    }

    os.makedirs("results", exist_ok=True)

    with open("results/youtube_streams.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n========== TOP 10 GTA 6 SHORTS IDEAS ==========")

    for i, video in enumerate(results[:10], 1):
        print(f"\n#{i} | SCORE: {video['score']}")
        print("ТЕМА:", video["topic"])
        print("ЗАГОЛОВОК:", video["title"])
        print("ХУК:", video["hook"])
        print("УГОЛ:", video["angle"])
        print("ПРОСМОТРЫ:", f"{video['views']:,}")
        print("КОММЕНТАРИИ:", video["comments"])
        print("ССЫЛКА:", video["url"])

    print("\nВсего подходящих видео:", len(results))
    print("TOP 10 saved to results/youtube_streams.json")


if __name__ == "__main__":
    main()
