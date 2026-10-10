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

# 品牌官方 YouTube 频道（含日本本土账号）
BRAND_CHANNELS = [
    ("Jackery", "Jackery 官方", "UCjDZe7g_sX9vFjg3uDQEqHA"),
    ("Jackery", "Jackery Japan", "UCWrXThDkHpRpOHmtDiE9McQ"),
    ("EcoFlow", "EcoFlow 官方", "UCk8Zk8tUAwBN_NKkORh4q2Q"),
    ("EcoFlow", "EcoFlow Japan", "UCocdSTuRBT5qJDNgg5qe0mA"),
    ("Anker", "Anker 官方", "UCgipHNmNjShcP2xH5k1OXfQ"),
    ("Anker", "Anker Japan", "UCqClkwAYuuBpaM_qWs8TsOQ"),
    ("Anker Solix", "Anker SOLIX 官方", "UCv6bA2FHQhi4yzSnDo1TXAg"),
    ("Bluetti", "BLUETTI 官方", "UC__Tu8lHDpThTB2EIpfbJ7Q"),
    ("Bluetti", "BLUETTI JAPAN", "UCUOiCoBFhN7Hrf0kMZ3w17g"),
]

# 内容类型分类规则：强信号命中即定类；弱信号次之；官方频道无命中=官方内容
STRONG_RULES = [
    ("评测", ["レビュー", "review", "実測", "検証", "比較", "インプレ", "unboxing", "開封", "hands on", "試用", "months later", "long term", "テスト"]),
    ("新品", ["新製品", "発売", "発表", "登場", "unveil", "pre-order", "予約", "新色", "新登場", "introducing", "new product", "coming soon"]),
    ("促销", ["セール", "オフ", "割引", "クーポン", "キャンペーン", "プライム", "値下げ", "特価", "giveaway", "抽選", "live"]),
    ("教程", ["使い方", "how to", "howto", "セットアップ", "tutorial", "academy", "設置", "導入"]),
]
WEAK_RULES = [
    ("促销", ["sale", "discount", "deal", "promo", "off"]),
    ("评测", ["reviewed", "first look"]),
    ("新品", ["launch", "announcement"]),
    ("教程", ["guide", "tips", "how"]),
]

def classify(title, desc, official=False):
    text = (title + " " + (desc or "")).lower()
    for cat, kws in STRONG_RULES:
        for kw in kws:
            if kw in text:
                return cat
    for cat, kws in WEAK_RULES:
        for kw in kws:
            if kw in text:
                return cat
    return "官方内容" if official else "其他"

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

def search_channel_videos(channel_id, key, max_results=8):
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)).strftime("%Y-%m-%dT00:00:00Z")
    params = urllib.parse.urlencode({
        "part": "snippet", "type": "video", "maxResults": max_results,
        "channelId": channel_id, "publishedAfter": after, "key": key,
    })
    url = "https://www.googleapis.com/youtube/v3/search?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    if not API_KEY:
        raise SystemExit("YOUTUBE_API_KEY not set")
    items, seen = [], set()

    # 1) 品牌官方频道（含日本本土账号）
    for brand, chan_label, chan_id in BRAND_CHANNELS:
        try:
            data = search_channel_videos(chan_id, API_KEY)
        except Exception as e:
            print(f"[youtube] channel {chan_label} failed: {e}", file=sys.stderr)
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
                "keyword": brand,
                "official": True,
                "channel_label": chan_label,
            })

    # 2) 关键词搜索（第三方/社媒内容）
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
                "official": False,
                "channel_label": "",
            })

    # 拉 description → hashtag + 内容类型分类
    if items:
        details = fetch_videos_details([v["video_id"] for v in items], API_KEY)
        for v in items:
            desc = details.get(v["video_id"], "")
            v["hashtags"] = extract_hashtags(desc)
            v["content_type"] = classify(v["title"], desc, v.get("official", False))
    items.sort(key=lambda x: x["published"], reverse=True)
    out = BASE / "output" / f"youtube_{DATE}.json"
    out.write_text(json.dumps({"as_of": DATE, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[youtube] {len(items)} videos ({sum(1 for i in items if i['official'])} official) -> {out.name}")

if __name__ == "__main__":
    main()
