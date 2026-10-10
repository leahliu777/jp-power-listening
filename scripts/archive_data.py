#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""归档当日数据 → gh-pages data/，生成监听中台 index.json。

输入:
  output/trends_YYYYMMDD.json      (aggregate_trends.py)
  output/news_YYYYMMDD.json        (news_fetch.py)
  output/summary-YYYYMMDD.json     (make_brief.py)
  assets/jp_holidays_2026_2027.json

输出 (随 gh-pages 发布):
  output/html/data/index.json              全量历史索引（拉取旧版 merge 后写回）
  output/html/data/trends-YYYY-MM-DD.json 当日 trends 快照
"""
import datetime, json, sys, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
HTML = OUT / "html"
DATA = HTML / "data"
DATA.mkdir(parents=True, exist_ok=True)

DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")
DATE_ISO = f"{DATE[0:4]}-{DATE[4:6]}-{DATE[6:8]}"
BASE_URL = "https://leahliu777.github.io/jp-power-listening"


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [archive] no existing index.json ({e})")
        return None


def trend_impact_text(keyword, day_change):
    """根据当日环比生成关联趋势标签，如 'EcoFlow ↑ +194.4%'"""
    for k, v in (day_change or {}).items():
        if k.lower() == keyword.lower() or keyword.lower() in k.lower() or k.lower() in keyword.lower():
            pct = v.get("pct")
            if pct is None:
                return f"{k}（部分数据）"
            arrow = "↑" if pct > 0 else ("↓" if pct < 0 else "—")
            return f"{k} {arrow} {pct:+.1f}%"
    return f"{keyword}（监测中）"


def main():
    trends = load_json(OUT / f"trends_{DATE}.json", {})
    news = load_json(OUT / f"news_{DATE}.json", {"items": []})
    holidays_raw = load_json(BASE / "assets" / "jp_holidays_2026_2027.json", {})

    # 1) trends 当日记录：取 last_full_day 各词的值
    trends_today = None
    day_change = {}
    brands = {}
    categories = {}
    g = trends.get("groups", {})
    for group_name, bucket, key in [("brands", brands, "brands"), ("categories", categories, "categories")]:
        blk = g.get(group_name)
        if not blk:
            continue
        ref = blk.get("last_full_day")
        series = blk.get("series", {})
        for kw, byday in series.items():
            bucket[kw] = byday.get(ref, byday.get(sorted(byday.keys())[-1], 0))
        day_change.update(blk.get("day_change", {}))
        trends_today_date = ref

    if brands or categories:
        trends_today = {"date": trends_today_date, "brands": brands, "categories": categories}

    # 2) news → 中台 news 结构 + events
    news_out = []
    events = []
    for it in news.get("items", []):
        title = it.get("title", "").strip()
        if not title:
            continue
        kw = it.get("keyword", "")
        impact = trend_impact_text(kw, day_change)
        news_out.append({
            "date": it.get("date", DATE_ISO),
            "brand": kw,
            "title": title,
            "summary": "",
            "source": it.get("source", ""),
            "url": it.get("link", ""),
            "trend_impact": impact,
        })
        # events 只取近 3 天内、且品牌词相关的，作为曲线标注候选
        events.append({
            "date": it.get("date", DATE_ISO),
            "type": "新闻",
            "title": title,
            "brand": kw,
            "direction": "↑" if "↑" in impact else "—",
        })

    # 3) holidays 扁平化
    holidays = []
    for yr, lst in holidays_raw.get("holidays", {}).items():
        for h in lst:
            holidays.append({"date": h["date"], "name": h["name"], "type": "节假日"})
    for n in holidays_raw.get("nodes", []):
        for dt in n.get("dates", []):
            holidays.append({"date": dt, "name": n.get("name", ""), "type": "营销节点", "desc": n.get("desc", "")})
    holidays.sort(key=lambda x: x["date"])

    # 5) 拉旧 index.json merge
    old = fetch_url(f"{BASE_URL}/data/index.json") or {}

    # 4) YouTube 社媒 → social 字段（platform 分组）
    youtube = load_json(OUT / f"youtube_{DATE}.json", {"items": []})
    social_out = []
    old_social_keys = set()
    for s in old.get("social", []):
        social_out.append(s)
        old_social_keys.add((s.get("platform"), s.get("video_id") or s.get("url")))
    for v in youtube.get("items", []):
        key = ("youtube", v.get("video_id"))
        if key in old_social_keys:
            continue
        social_out.append({
            "platform": "youtube",
            "video_id": v.get("video_id"),
            "title": v.get("title", ""),
            "channel": v.get("channel", ""),
            "published": v.get("published", ""),
            "url": v.get("url", ""),
            "keyword": v.get("keyword", ""),
            "hashtags": v.get("hashtags", []),
        })
    social_out.sort(key=lambda x: x.get("published", ""), reverse=True)
    social_out = social_out[:200]

    merged_trends = old.get("trends", [])
    merged_news = old.get("news", [])
    merged_events = old.get("events", [])

    if trends_today:
        merged_trends = [t for t in merged_trends if t["date"] != trends_today["date"]]
        merged_trends.append(trends_today)
        merged_trends.sort(key=lambda x: x["date"])
        merged_trends = merged_trends[-120:]  # 保留 120 天

    old_keys = {(n["date"], n["title"]) for n in merged_news}
    for n in news_out:
        if (n["date"], n["title"]) not in old_keys:
            merged_news.append(n)
    merged_news.sort(key=lambda x: x["date"], reverse=True)
    merged_news = merged_news[:500]

    old_ekey = {(e["date"], e["title"]) for e in merged_events}
    for e in events:
        if (e["date"], e["title"]) not in old_ekey:
            merged_events.append(e)
    merged_events.sort(key=lambda x: x["date"], reverse=True)
    merged_events = merged_events[:500]

    index = {
        "as_of": DATE_ISO,
        "trends": merged_trends,
        "news": merged_news,
        "social": social_out,
        "events": merged_events,
        "holidays": holidays,
    }
    (DATA / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    # 当日快照
    if trends_today:
        (DATA / f"trends-{DATE_ISO}.json").write_text(
            json.dumps(trends_today, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[archive] trends days={len(merged_trends)} news={len(merged_news)} events={len(merged_events)} holidays={len(holidays)}")
    print(f"[archive] -> {DATA}/index.json")


if __name__ == "__main__":
    main()
