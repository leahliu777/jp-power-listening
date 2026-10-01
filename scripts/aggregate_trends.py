#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Trends CSV → 日聚合评分
输入: trends_brands_YYYYMMDD.csv / trends_categories_YYYYMMDD.csv (7天窗口, 小时粒度)
输出: stdout JSON { date, groups: {brands: {...}, categories: {...}}, day_change, series }
聚合口径: 每个自然日 = 当日24小时指数之和(相对搜索活跃度代理分); 今日(进行中)单独标注, 不参与环比
"""
import csv, json, sys, datetime, os


def load_csv(path):
    """Parse trends CSV: header row 'Time,kw1: (Japan),...' rows '2026-09-23T14,44'"""
    kws, rows = [], {}
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    hdr_idx = next(i for i, l in enumerate(lines) if l.startswith("Time,"))
    hdr = lines[hdr_idx]
    kws = [c.split(":")[0].strip() for c in hdr.split(",")[1:]]
    for l in lines[hdr_idx + 1:]:
        parts = l.split(",")
        if len(parts) < 2:
            continue
        ts, vals = parts[0], parts[1:]
        date_hour = ts.replace("T", " ")[:13]
        try:
            day = date_hour.split(" ")[0]
            hour = int(date_hour.split(" ")[1].split(":")[0])
        except Exception:
            continue
        rows.setdefault(day, {})
        for i, k in enumerate(kws):
            v = int(vals[i]) if i < len(vals) and vals[i].strip().lstrip("-").isdigit() else 0
            rows[day].setdefault(k, 0)
            rows[day][k] += v
    return kws, rows


def aggregate(csv_path):
    kws, rows = load_csv(csv_path)
    days = sorted(rows.keys())
    today = datetime.date.today().isoformat()
    series = {}
    for d in days:
        for k in kws:
            series.setdefault(k, {})[d] = rows[d].get(k, 0)
    completed = [d for d in days if d < today]
    ref = completed[-1] if completed else days[-1]
    prev = days[days.index(ref) - 1] if ref in days and days.index(ref) >= 1 else None
    day_change = {}
    for k in kws:
        v_now = series[k].get(ref)
        v_prev = series[k].get(prev) if prev else None
        if v_now is not None and v_prev is not None and v_prev > 0:
            day_change[k] = {"date": ref, "prev_date": prev, "value": v_now,
                             "prev_value": v_prev, "pct": round((v_now - v_prev) / v_prev * 100, 1)}
        elif v_now is not None:
            day_change[k] = {"date": ref, "prev_date": prev, "value": v_now,
                             "prev_value": v_prev, "pct": None}
    return {"keywords": kws, "series": series, "day_change": day_change, "last_full_day": ref}


def main():
    brands_path = sys.argv[1] if len(sys.argv) > 1 else None
    cats_path = sys.argv[2] if len(sys.argv) > 2 else None
    out = {"as_of": datetime.date.today().isoformat(), "groups": {}}
    if brands_path and os.path.exists(brands_path):
        out["groups"]["brands"] = aggregate(brands_path)
    if cats_path and os.path.exists(cats_path):
        out["groups"]["categories"] = aggregate(cats_path)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
