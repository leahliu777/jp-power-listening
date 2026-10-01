#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成两组自包含 SVG 折线图（供 make_brief.py 嵌入与 CLI 独立输出）。
CLI: python3 gen_charts.py [YYYYMMDD] [out_dir]
"""
import json, math, os, sys, datetime

PALETTE = {
    "Jackery": "#758092", "EcoFlow": "#3E5C9A", "Anker": "#1A2B4A",
    "Anker Solix": "#A8B3C4", "Bluetti": "#D8DDE4",
    "ポータブル電源": "#1A2B4A", "ポータブルバッテリー": "#758092",
}
TEXT = "#1F2329"; SUB = "#646A73"; GRID = "#DEE3E8"


def svg_line_chart(title, subtitle, series, dates, log=False, note=""):
    W, H = 820, 400
    ml, mr, mt, mb = 70, 40, 46, 64
    pw, ph = W - ml - mr, H - mt - mb
    allv = [v for s in series.values() for v in s]
    vmax = max(allv); vmin = 0

    def y(v):
        if log:
            v = max(v, 0.5)
            lo, hi = math.log10(0.5), math.log10(vmax * 1.15)
            return mt + ph - (math.log10(v) - lo) / (hi - lo) * ph
        return mt + ph - (v - vmin) / (vmax * 1.12 - vmin) * ph

    def x(i):
        return ml + pw * (i / (len(dates) - 1))

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',\'Hiragino Sans\',\'Noto Sans JP\',sans-serif;">']
    parts.append(f'<text x="{ml}" y="28" fill="{TEXT}" font-size="17" font-weight="700">{title}</text>')
    if subtitle:
        parts.append(f'<text x="{ml}" y="46" fill="{SUB}" font-size="13">{subtitle}</text>')
    if log:
        for t in [1, 3, 10, 30, 100, 300, 1000]:
            if t <= vmax * 1.15:
                yy = y(t)
                parts.append(f'<line x1="{ml}" y1="{yy:.1f}" x2="{W-mr}" y2="{yy:.1f}" stroke="{GRID}" stroke-width="1"/>')
                parts.append(f'<text x="{ml-8}" y="{yy+4:.1f}" fill="{SUB}" font-size="11" text-anchor="end">{t}</text>')
    else:
        step = max(1, round((vmax * 1.12) / 5 / 50) * 50)
        for v in range(0, int(vmax * 1.12) + 1, step):
            yy = y(v)
            parts.append(f'<line x1="{ml}" y1="{yy:.1f}" x2="{W-mr}" y2="{yy:.1f}" stroke="{GRID}" stroke-width="1"/>')
            parts.append(f'<text x="{ml-8}" y="{yy+4:.1f}" fill="{SUB}" font-size="11" text-anchor="end">{v}</text>')
    for i, d in enumerate(dates):
        parts.append(f'<text x="{x(i):.1f}" y="{H-mb+18}" fill="{SUB}" font-size="11" text-anchor="middle">{d[5:]}</text>')
    for name, vals in series.items():
        color = PALETTE.get(name, "#1A2B4A")
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>')
        lx, ly = x(len(vals) - 1), y(vals[-1])
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="{color}"/>')
        parts.append(f'<text x="{lx+8:.1f}" y="{ly+4:.1f}" fill="{TEXT}" font-size="12" font-weight="600">{vals[-1]}</text>')
    ly0 = H - mb + 34
    lx0 = ml
    for name in series:
        color = PALETTE.get(name, "#1A2B4A")
        parts.append(f'<rect x="{lx0}" y="{ly0-8}" width="14" height="3" rx="1.5" fill="{color}"/>')
        parts.append(f'<text x="{lx0+20}" y="{ly0}" fill="{TEXT}" font-size="12">{name}</text>')
        lx0 += 20 + 16 + len(name) * 12 + 18
    if note:
        parts.append(f'<text x="{ml}" y="{H-8}" fill="{SUB}" font-size="11">{note}</text>')
    parts.append("</svg>")
    return "".join(parts)


def build_svgs(data):
    """返回 {'brands': svg_html, 'categories': svg_html, 'dates': [...], 'today': '...'}"""
    dates = sorted(next(iter(data["groups"]["brands"]["series"].values())).keys())
    today = datetime.date.today().isoformat()
    dates = [d for d in dates if d != today]
    win_first, win_last = dates[0], dates[-1]

    def series_from(group):
        return {k: [v[d] for d in dates] for k, v in group["series"].items()}

    brands = data["groups"]["brands"]
    cats = data["groups"]["categories"]
    svg_brands = svg_line_chart(
        "品牌组：5 品牌近 7 日搜索活跃度对比（日本）",
        "日活跃评分 = 当日 24 小时指数之和（相对指数，组内归一化）；纵轴为对数刻度",
        series_from(brands), dates, log=True,
        note=f"数据：Google Trends 日本地区（geo=JP），窗口 {win_first[5:]}–{win_last[5:]}；{win_first[5:]} 为窗口首日含部分小时，{today[5:]} 当日进行中未计入。相对指数非绝对搜索量。")
    svg_cats = svg_line_chart(
        "品类词：ポータブル電源 vs ポータブルバッテリー 近 7 日活跃度（日本）",
        "日活跃评分 = 当日 24 小时指数之和（相对指数，组内归一化）；线性刻度",
        series_from(cats), dates, log=False,
        note=f"数据：Google Trends 日本地区（geo=JP），窗口 {win_first[5:]}–{win_last[5:]}。两组归一化集合独立，跨组数值不可直接比较。")
    return {"brands": svg_brands, "categories": svg_cats, "dates": dates, "today": today}


def wrap(title, svg_body):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="use-iframe" content="true">
<meta name="html-box-height-mode" content="auto">
<meta name="description" content="{title}，7日搜索活跃度对比折线图，含图例与口径说明">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#fff;">
{svg_body}
</body>
</html>
"""


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")
    out_dir = sys.argv[2] if len(sys.argv) > 2 else f"{os.path.dirname(os.path.abspath(__file__))}/../output/charts_{date_str}"
    data_path = f"{os.path.dirname(os.path.abspath(__file__))}/../output/trends_{date_str}.json"
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    svgs = build_svgs(data)
    with open(os.path.join(out_dir, "chart_brands.html"), "w", encoding="utf-8") as f:
        f.write(wrap("品牌组 7 日搜索活跃度对比（日本）", svgs["brands"]))
    with open(os.path.join(out_dir, "chart_categories.html"), "w", encoding="utf-8") as f:
        f.write(wrap("品类词 7 日搜索活跃度对比（日本）", svgs["categories"]))
    print("charts written:", os.listdir(out_dir))


if __name__ == "__main__":
    main()
