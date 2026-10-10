#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""価格.com ポータブル電源 人気売れ筋ランキング 采集"""
import datetime, json, re, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")
URL = "https://kakaku.com/kaden/portable-battery/ranking_3113/"

BRANDS = ["Jackery", "EcoFlow", "Anker", "BLUETTI", "Bluetti", "PowerArQ", "EF EcoFlow"]

def fetch():
    return subprocess.run(
        ["curl", "-sL", "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", URL],
        capture_output=True, timeout=30).stdout

def main():
    raw = fetch()
    try:
        h = raw.decode("cp932")
    except:
        h = raw.decode("utf-8", errors="ignore")
    # 每个 rkgBox
    boxes = re.findall(r'<div class="rkgBox[ "][^"]*">(.*?)(?=<div class="rkgBox[ "]|$)', h, re.S)
    items = []
    for b in boxes[:20]:
        m_rank = re.search(r'class="num">(\d+)</span>位', b)
        m_maker = re.search(r'rkgBoxNameMaker">(.*?)</span>', b)
        m_item = re.search(r'rkgBoxNameItem">(.*?)</span>', b)
        m_price = re.search(r'(?:&#165;|¥)(?:&nbsp;)?\s*([\d,]+)', b)
        m_trend = re.search(r'rkgTrans"><span class="(same|up|down)[^"]*">([^<]*)</span>', b)
        if not (m_rank and m_maker and m_item):
            continue
        maker = re.sub(r"<[^>]+>", "", m_maker.group(1)).strip()
        item = re.sub(r"<[^>]+>", "", m_item.group(1)).strip()
        # 识别品牌
        brand = "其他"
        for bn in BRANDS:
            if bn.lower() in (maker + " " + item).lower():
                brand = "EcoFlow" if "ecoflow" in bn.lower() else ("BLUETTI" if "bluetti" in bn.lower() else bn)
                break
        items.append({
            "rank": int(m_rank.group(1)),
            "brand": brand,
            "maker": maker,
            "product": item,
            "price": m_price.group(1) if m_price else "",
            "trend": m_trend.group(2).strip() if m_trend else "",
        })
    out = BASE / "output" / f"kakaku_{DATE}.json"
    out.write_text(json.dumps({"date": DATE, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[kakaku] {len(items)} items -> {out.name}")
    for it in items[:8]:
        print(f"  #{it['rank']} {it['brand']} {it['product'][:40]}")

if __name__ == "__main__":
    main()
