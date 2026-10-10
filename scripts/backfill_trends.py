#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 gh-pages 历史 brief HTML 回填趋势留档，合并进 data/index.json"""
import re, json, subprocess, urllib.request
from collections import defaultdict

BASE = "https://leahliu777.github.io/jp-power-listening"
BRIEFS = [f"2026100{i}" for i in range(2, 11)]  # 10/02-10/10

# 品牌行名 -> index.json key
BRAND_MAP = {"Anker":"Anker","Anker Solix":"Anker Solix","Jackery":"Jackery","EcoFlow":"EcoFlow","Bluetti":"Bluetti","BLUETTI":"Bluetti"}

def fetch(url):
    import subprocess
    return subprocess.run(["curl","-sL",url], capture_output=True, text=True, timeout=30).stdout

def parse_brief(html):
    """返回 {date_str: {brand: int}}, {date_str: {category: int}}"""
    out_b, out_c = {}, {}
    tables = re.findall(r"<table.*?</table>", html, re.S)
    for t in tables:
        rows = re.findall(r"<tr>(.*?)</tr>", t, re.S)
        if len(rows) < 2: continue
        header = re.findall(r"<t[dh]>(.*?)</t[dh]>", rows[0], re.S)
        # 日期列（MM-DD）
        date_cols = [c for c in header if re.match(r"\d{2}-\d{2}", c)]
        if not date_cols: continue
        is_cat = "ポータブル" in rows[1]
        for r in rows[1:]:
            cells = re.findall(r"<t[dh]>(.*?)</t[dh]>", r, re.S)
            if len(cells) < len(date_cols)+1: continue
            name = re.sub(r"<[^>]+>","",cells[0]).strip()
            for i, dc in enumerate(date_cols):
                val = cells[i+1].strip()
                try: v = int(val.replace(",",""))
                except: continue
                d = "2026-" + dc.replace("-", "-", 1)  # 10-04 -> 2026-10-04
                if is_cat:
                    out_b[d] = out_b.get(d, {})
                    out_c.setdefault(d, {})[name] = v
                else:
                    bkey = BRAND_MAP.get(name, name)
                    out_b.setdefault(d, {})[bkey] = v
    return out_b, out_c

# 收集所有日期
trends = {}  # date -> {"date":d, "brands":{}, "categories":{}}
for b in BRIEFS:
    html = fetch(f"{BASE}/brief-{b}.html")
    bd, cd = parse_brief(html)
    for d, vals in bd.items():
        trends.setdefault(d, {"date":d, "brands":{}, "categories":{}})["brands"].update(vals)
    for d, vals in cd.items():
        trends.setdefault(d, {"date":d, "brands":{}, "categories":{}})["categories"].update(vals)

# 合并现有 index.json
old = json.loads(fetch(f"{BASE}/data/index.json"))
existing_dates = {t["date"] for t in old.get("trends",[])}
new_trends = sorted(trends.values(), key=lambda x: x["date"])
# 保留已有的（今日 run 生成的，可能更准）
for t in old.get("trends",[]):
    if t["date"] not in {x["date"] for x in new_trends}:
        new_trends.append(t)
new_trends.sort(key=lambda x: x["date"])

old["trends"] = new_trends
old["as_of"] = old.get("as_of","2026-10-10")

out = "/tmp/new_index.json"
json.dump(old, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"trends days: {len(new_trends)} ({new_trends[0]['date']} ~ {new_trends[-1]['date']})")
print("sample:", json.dumps(new_trends[-1], ensure_ascii=False))
