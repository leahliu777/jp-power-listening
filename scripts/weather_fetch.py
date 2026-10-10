#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日本气象/灾害情报采集：NHK 灾害天气 RSS + 気象庁台风列表"""
import datetime, json, re, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")

FEEDS = [
    ("台风・灾害", "https://news.google.com/rss/search?q=%E5%8F%B0%E9%A2%A8+OR+%E5%9C%B0%E9%9C%87+OR+%E5%81%9C%E9%9B%BB+OR+%E5%A4%A7%E9%9B%A8+when:2d&hl=ja&gl=JP&ceid=JP:ja"),
]
ALERT_KEYS = ["台風", "地震", "停電", "大雨", "洪水", "津波", "暴風", "大雪", "竜巻"]

def curl(url):
    return subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", url],
                          capture_output=True, timeout=20).stdout

def main():
    alerts = []
    for cat, url in FEEDS:
        try:
            raw = curl(url)
            root = ET.fromstring(raw)
            for item in root.iter("item"):
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                link = item.findtext("link", "")
                date = item.findtext("pubDate", "")
                if any(k in title for k in ALERT_KEYS):
                    alerts.append({
                        "category": cat, "title": title, "summary": desc[:120],
                        "url": link, "date": date[:16],
                    })
        except Exception as e:
            print(f"rss {url} failed: {e}", file=sys.stderr)
    alerts.sort(key=lambda x: x["date"], reverse=True)
    out = BASE / "output" / f"weather_{DATE}.json"
    out.write_text(json.dumps({"date": DATE, "alerts": alerts[:15]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[weather] {len(alerts)} alerts -> {out.name}")
    for a in alerts[:5]:
        print(f"  {a['title'][:60]}")

if __name__ == "__main__":
    main()
