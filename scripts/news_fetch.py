#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新闻/社媒聚合（云端版 v1）
数据源：
  1. Google News RSS —— 日/英/中三语关键词（品牌词 + 品类词），近 3 天窗口
  2. Jackery Japan 官方 news 页（jackery.jp/blogs/news）解析
输出: output/news_YYYYMMDD.json
局限（如实写入简报）：YouTube/X 无公开关键词检索 API，云端版暂不采集，简报标注。
"""
import datetime, json, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")

QUERIES = [
    # (lang, keyword, google-news-locale-params)
    ("ja", "Jackery", "hl=ja&gl=JP&ceid=JP:ja"),
    ("ja", "EcoFlow", "hl=ja&gl=JP&ceid=JP:ja"),
    ("ja", "Anker Solix", "hl=ja&gl=JP&ceid=JP:ja"),
    ("ja", "BLUETTI", "hl=ja&gl=JP&ceid=JP:ja"),
    ("ja", "ポータブル電源", "hl=ja&gl=JP&ceid=JP:ja"),
    ("en", "portable power station Japan", "hl=en-US&gl=US&ceid=US:en"),
    ("zh", "便携电源 日本", "hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_google_news_rss(lang, kw, params):
    q = urllib.parse.quote(kw)
    url = f"https://news.google.com/rss/search?q={q}&{params}"
    items = []
    try:
        xml = fetch(url)
        root = ET.fromstring(xml)
    except Exception as e:
        print(f"  [{lang}] {kw}: RSS error {e}")
        return items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src = ""
        s = it.find("source")
        if s is not None:
            src = (s.text or "").strip()
        if not title or not pub:
            continue
        try:
            # pubDate: 'Wed, 30 Sep 2026 08:00:00 GMT'
            dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S")
        except Exception:
            continue
        age = (datetime.datetime.utcnow() - dt).days
        if age > 3:
            continue
        items.append({
            "lang": lang, "keyword": kw, "title": title, "source": src,
            "link": link, "date": dt.strftime("%Y-%m-%d"),
        })
    print(f"  [{lang}] {kw}: {len(items)} items")
    return items


def fetch_jackery_jp():
    """jackery.jp/blogs/news 列表页：标题 + 日期"""
    items = []
    try:
        html = fetch("https://www.jackery.jp/blogs/news")
    except Exception as e:
        print(f"  jackery.jp: {e}")
        return items
    # 找 <time datetime=...> 与标题（article/h2/h3 结构）
    times = re.findall(r'<time[^>]*datetime="([\d-]+)"', html)
    titles = re.findall(r'<h[23][^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html)
    for i, (href, t) in enumerate(titles):
        d = times[i] if i < len(times) else datetime.date.today().isoformat()
        t = t.strip()
        if not t:
            continue
        items.append({
            "lang": "ja", "keyword": "Jackery", "title": t,
            "source": "Jackery Japan", "link": "https://www.jackery.jp" + href if href.startswith("/") else href,
            "date": d,
        })
    print(f"  jackery.jp: {len(items)} items")
    return items


def main():
    items = []
    for lang, kw, params in QUERIES:
        items.extend(parse_google_news_rss(lang, kw, params))
        time.sleep(0.5)
    items.extend(fetch_jackery_jp())
    # 去重（按标题）
    seen, uniq = set(), []
    for it in items:
        key = it["title"].lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda x: x["date"], reverse=True)
    out = {"as_of": datetime.date.today().isoformat(), "items": uniq[:60]}
    path = OUT / f"news_{DATE}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total: {len(uniq)} -> {path.name}")


if __name__ == "__main__":
    main()
