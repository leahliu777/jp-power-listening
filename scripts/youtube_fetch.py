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
    ("ポータブル電源 レビュー", "ポータブル電源"),
]

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
            seen.add(vid)
            sn = it.get("snippet", {})
            items.append({
                "video_id": vid,
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "published": sn.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "keyword": label,
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    out = BASE / "output" / f"youtube_{DATE}.json"
    out.write_text(json.dumps({"as_of": DATE, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[youtube] {len(items)} videos -> {out.name}")

if __name__ == "__main__":
    main()
