#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YouTube 社媒采集：按品牌/品类关键词搜索最近 48h 新视频，存 output/youtube_YYYYMMDD.json
环境变量: YOUTUBE_API_KEY
"""
import datetime, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
BASE = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")

QUERIES = [
    ("Jackery", "Jackery"),
    ("EcoFlow", "EcoFlow"),
    ("Anker", "Anker"),
    ("Anker Solix", "Anker Solix"),
    ("Bluetti", "Bluetti"),
    ("ポータブル電源", "ポータブル電源"),
    ("ポータブルバッテリー", "ポータブルバッテリー"),
]

# 相关性过滤：标题/频道必须命中任一词（大小写不敏感）
RELEVANCE = {
    "Jackery": ["jackery"],
    "EcoFlow": ["ecoflow"],
    "Anker": ["anker"],
    "Anker Solix": ["anker solix", "solix"],
    "Bluetti": ["bluetti"],
    "ポータブル電源": ["ポータブル電源"],
    "ポータブルバッテリー": ["ポータブルバッテリー"],
}

def relevant(title, channel, label):
    text = (title + " " + channel).lower()
    return any(w in text for w in RELEVANCE.get(label, []))

def fetch_videos_details(ids, key):
    """批量拉视频 description，用于提取 #hashtag"""
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ",".join(ids[i:i+50])
        params = urllib.parse.urlencode({"part": "snippet", "id": chunk, "key": key})
        url = "https://www.googleapis.com/youtube/v3/videos?" + params
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
        for it in data.get("items", []):
            desc = it.get("snippet", {}).get("description", "")
            out[it["id"]] = desc
    return out

def extract_hashtags(desc):
    import re
    return re.findall(r"#([\w\u3040-\u30ff\u4e00-\u9fff]+)", desc)[:5]

def search(q, key):
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)).strftime("%Y-%m-%dT00:00:00Z")
    params = urllib.parse.urlencode({
        "part": "snippet", "type": "video", "maxResults": 10,
        "q": q, "publishedAfter": after, "key": key,
    })
    url = "https://www.googleapis.com/youtube/v3/search?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    if not API_KEY:
        raise SystemExit("YOUTUBE_API_KEY not set")
    items, seen = [], set()
    for kw, label in QUERIES:
        try:
            data = search(kw, API_KEY)
        except Exception as e:
            print(f"[youtube] {kw} failed: {e}", file=sys.stderr)
            continue
        for it in data.get("items", []):
            vid = it.get("id", {}).get("videoId")
            if not vid or vid in seen:
                continue
            sn = it.get("snippet", {})
            title = sn.get("title", "")
            channel = sn.get("channelTitle", "")
            if not relevant(title, channel, label):
                continue
            seen.add(vid)
            items.append({
                "video_id": vid,
                "title": title,
                "channel": channel,
                "published": sn.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "keyword": label,
            })
    # 拉 description 提取 hashtag
    if items:
        details = fetch_videos_details([v["video_id"] for v in items], API_KEY)
        for v in items:
            v["hashtags"] = extract_hashtags(details.get(v["video_id"], ""))
    items.sort(key=lambda x: x["published"], reverse=True)
    out = BASE / "output" / f"youtube_{DATE}.json"
    out.write_text(json.dumps({"as_of": DATE, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[youtube] {len(items)} relevant videos -> {out.name}")

if __name__ == "__main__":
    main()
