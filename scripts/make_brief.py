#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成单文件 HTML 简报（云端版 v1，发布到 gh-pages 供钉钉链接查看）。
输入: output/trends_YYYYMMDD.json、output/news_YYYYMMDD.json、assets/jp_holidays_2026_2027.json
输出: output/html/brief-YYYYMMDD.html、output/summary-YYYYMMDD.json（供钉钉推送组装）
"""
import datetime, json, sys
from pathlib import Path
import gen_charts

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
HTML_OUT = OUT / "html"
HTML_OUT.mkdir(exist_ok=True)
ASSETS = BASE / "assets"
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")
DATE_ISO = datetime.date.today().isoformat()

NAVY = "#1A2B4A"; SUB = "#646A73"; BG = "#F7F8FA"; LINE = "#DEE3E8"; ACCENT = "#C0392B"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_pct(pct):
    if pct is None:
        return "—"
    return f"{pct:+.1f}%"


def trend_table(series, day_change, day_keys):
    """series: {kw: {day: v}}; day_keys: 最近 6 个完整日"""
    keys = sorted(day_change.keys())
    thead = "<tr><th>关键词</th>" + "".join(f"<th>{k[5:]}</th>" for k in day_keys) + "<th>环比</th></tr>"
    rows = []
    for k in keys:
        cells = "".join(f"<td>{series[k].get(d, '—')}</td>" for d in day_keys)
        rows.append(f"<tr><td><b>{k}</b></td>{cells}<td>{fmt_pct(day_change[k]['pct'])}</td></tr>")
    return f"<table>{thead}{''.join(rows)}</table>"


def news_groups(items):
    """按 keyword 分组，返回有序 [(group_name, [items])]"""
    order = ["Jackery", "EcoFlow", "Anker Solix", "BLUETTI", "ポータブル電源", "portable power station Japan", "便携电源 日本"]
    groups = {}
    for it in items:
        groups.setdefault(it["keyword"], []).append(it)
    out = []
    for kw in order:
        if kw in groups:
            out.append((kw, groups[kw][:8]))
    return out


def upcoming_nodes(holidays_data, days):
    """返回 (today+days) 内的节假日/节点列表"""
    today = datetime.date.today()
    end = today + datetime.timedelta(days=days)
    res = []
    for h in holidays_data.get("holidays", {}).get(str(today.year), []):
        d = datetime.date.fromisoformat(h["date"])
        if today <= d <= end:
            res.append((h["date"], h["name"], "国民の祝日"))
    for n in holidays_data.get("nodes", []):
        for ds in n.get("dates", []):
            try:
                d = datetime.date.fromisoformat(ds)
            except Exception:
                continue
            if today <= d <= end:
                res.append((ds, n["name"], n.get("desc", "")))
    return sorted(res)


def main():
    trends = load_json(OUT / f"trends_{DATE}.json")
    news = load_json(OUT / f"news_{DATE}.json") if (OUT / f"news_{DATE}.json").exists() else {"items": []}
    holidays = load_json(ASSETS / "jp_holidays_2026_2027.json")

    svgs = gen_charts.build_svgs(trends)
    dates = svgs["dates"]
    brands = trends["groups"]["brands"]
    cats = trends["groups"]["categories"]
    day_keys = dates[-6:]  # 表用最近 6 个完整日

    # 今日速览
    movers = sorted([(k, v["pct"]) for k, v in brands["day_change"].items() if v.get("pct") is not None],
                    key=lambda x: (x[1] or 0), reverse=True)
    cat_movers = sorted([(k, v["pct"]) for k, v in cats["day_change"].items() if v.get("pct") is not None],
                        key=lambda x: (x[1] or 0), reverse=True)
    top_abs = max(brands["day_change"].items(), key=lambda x: x[1]["value"])[0]
    news_top = sorted(news["items"], key=lambda x: x["date"], reverse=True)[:6]
    nodes14 = upcoming_nodes(holidays, 14)

    bullets = []
    if movers:
        up = movers[0]
        bullets.append(f"<li><b>品牌热度</b>：{up[0]} 日活跃度环比 <b>{fmt_pct(up[1])}</b> 领涨（{brands['day_change'][up[0]]['value']}）；{top_abs} 仍居首位（{brands['day_change'][top_abs]['value']}，环比 {fmt_pct(brands['day_change'][top_abs]['pct'])}）</li>")
    if cat_movers:
        c0 = cat_movers[0]
        bullets.append(f"<li><b>品类需求</b>：{c0[0]} 日活跃度 {cats['day_change'][c0[0]]['value']}（环比 {fmt_pct(c0[1])}），{'回落' if (c0[1] or 0) < 0 else '回升'}至{('中高位平台' if (c0[1] or 0) < 0 else '上行通道')}</li>")
    if news_top:
        top3 = news_top[:3]
        titles = "；".join(f"「{t['title'][:28]}…」" if len(t['title']) > 28 else f"「{t['title']}」" for t in top3)
        bullets.append(f"<li><b>今日新闻</b>：{titles}</li>")
    if nodes14:
        nd = nodes14[0]
        bullets.append(f"<li><b>节点提醒</b>：{nd[1]}（{nd[0][5:]}）临近{('，' + nd[2]) if nd[2] != '国民の祝日' and len(nd[2]) < 40 else ''}</li>")
    if not bullets:
        bullets.append("<li>今日无显著波动与重大新闻，详见下方明细。</li>")
    callout = f"""<div style="background:{BG};border-left:4px solid {NAVY};padding:14px 18px;border-radius:6px;margin:18px 0;">
<p style="margin:0 0 8px;font-weight:700;color:{NAVY};">今日速览（数据窗口 {dates[0][5:]}–{dates[-1][5:]}，环比 = {brands['day_change'][list(brands['day_change'])[0]]['date'][5:]} vs {brands['day_change'][list(brands['day_change'])[0]]['prev_date'][5:]}）</p>
<ul style="margin:0;padding-left:20px;">{''.join(bullets)}</ul>
</div>"""

    # 新闻 HTML
    news_html = []
    for kw, its in news_groups(news["items"]):
        rows = []
        for it in its[:6]:
            rows.append(f'<li><span style="color:{SUB}">[{it["date"]}]</span> <a href="{it["link"]}" style="color:{NAVY};text-decoration:none;">{it["title"]}</a> <span style="color:{SUB}">（{it["source"]}）</span></li>')
        news_html.append(f'<h2 style="font-size:17px;color:{NAVY};margin:20px 0 6px;">{kw}</h2><ul style="margin:4px 0 8px;padding-left:20px;line-height:1.7;">{"".join(rows)}</ul>')
    if not news_html:
        news_html = ['<p style="color:' + SUB + ';">今日无窗口内新闻（检索如实标注，未编造）。</p>']

    # 节点 HTML
    nodes30 = upcoming_nodes(holidays, 30)
    nodes60 = upcoming_nodes(holidays, 60)
    if nodes14:
        rows14 = "".join(f"<tr><td>{d[5:]}</td><td><b>{n}</b></td><td>{desc}</td></tr>" for d, n, desc in nodes14)
        nodes14_html = f'<table style="border-collapse:collapse;width:100%;font-size:14px;"><thead><tr style="background:{BG};"><th style="padding:6px;border:1px solid {LINE};text-align:left;">日期</th><th style="padding:6px;border:1px solid {LINE};text-align:left;">节点</th><th style="padding:6px;border:1px solid {LINE};text-align:left;">说明</th></tr></thead><tbody>{rows14}</tbody></table>'
    else:
        nodes14_html = '<p style="color:' + SUB + ';">未来 14 天无法定假日/重大节点。</p>'
    fwd = "、".join(f"{n}（{d[5:]}）" for d, n, desc in nodes60 if d > (nodes14[-1][0] if nodes14 else "0000"))
    fwd_html = f'<p style="margin-top:10px;"><b>前瞻 30–60 天</b>：{fwd or "无"}（黑五/年末节点建议提前 2–3 周布局内容与投放）。</p>' if fwd else ""

    # 表格标题变量
    b_table = trend_table(brands["series"], brands["day_change"], day_keys)
    c_table = trend_table(cats["series"], cats["day_change"], day_keys)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>日本便携电源市场监听日报 {DATE_ISO}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;margin:0;padding:24px;background:#fff;color:#1F2329;line-height:1.6;}}
h1{{font-size:22px;color:{NAVY};margin:0 0 4px;}}
.sub{{color:{SUB};font-size:13px;margin-bottom:18px;}}
h2{{font-size:18px;color:{NAVY};border-bottom:2px solid {LINE};padding-bottom:4px;margin:28px 0 10px;}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0;}}
th{{background:{BG};padding:6px 8px;border:1px solid {LINE};text-align:right;}}
td{{padding:6px 8px;border:1px solid {LINE};text-align:right;}}
td:first-child,th:first-child{{text-align:left;}}
.src{{color:{SUB};font-size:12px;margin:2px 0 14px;}}
a{{color:{NAVY};}}
</style>
</head>
<body>
<h1>日本便携电源市场监听日报（{DATE_ISO}）</h1>
<div class="sub">监听范围：Google Trends（日本 JP，品牌组 + 品类组）· 日/英/中媒体新闻 · 日本节假日与营销节点 · 每日 10:00（北京时间）自动生成</div>
{callout}
<h2>一、Google Trends 趋势总览</h2>
<p>日活跃评分 = 当日 24 小时相对指数之和（组内归一化，最高=100）；<b>品牌组与品类组为两组独立归一化集合，跨组数值不可直接比较</b>；{dates[0][5:]} 为窗口首日（含部分小时），{svgs['today'][5:]} 当日进行中不参与环比。</p>
<h2 style="font-size:17px;">1.1 品牌组：5 品牌近 7 日活跃度</h2>
{svgs['brands']}
{b_table}
<p class="src">数据来源：Google Trends 日本（geo=JP），{DATE_ISO} 抓取。Anker Solix / Bluetti 绝对分值低，环比波动参考意义有限。</p>
<h2 style="font-size:17px;">1.2 品类组：ポータブル電源 vs ポータブルバッテリー</h2>
{svgs['categories']}
{c_table}
<p class="src">数据来源：Google Trends 日本（geo=JP），{DATE_ISO} 抓取。</p>
<h2>二、品牌与品类新闻（近 3 天窗口）</h2>
{''.join(news_html)}
<h2>三、社媒动态</h2>
<p>云端版 v1 采用 Google News RSS 与品牌官网新闻聚合；YouTube / X 无公开关键词检索接口，本版暂不采集（后续可接入 YouTube Data API / 第三方舆情服务补全）。</p>
<h2>四、节点与假日提醒</h2>
{nodes14_html}
{fwd_html}
<h2>五、数据说明与局限</h2>
<ul>
<li>Google Trends 为相对指数，非绝对搜索量；不同窗口各自归一化，与历史报告同日数值可能存在比例差异，属基准变化而非搜索量变化。</li>
<li>环比口径：最后一个完整日 vs 前一日；窗口首日与当日（进行中）为部分数据。</li>
<li>新闻来源：Google News RSS（日/英/中）+ Jackery Japan 官网；标题保留原文。</li>
<li>云端执行环境：GitHub Actions（免费计划，调度可能存在数分钟延迟）；X 社媒与部分品牌官方动态暂缺，如实标注。</li>
</ul>
<p style="color:{SUB};font-size:12px;margin-top:20px;">本简报由自动化监听工具每日生成，数据与结论以原文链接为准。</p>
</body>
</html>"""

    brief_path = HTML_OUT / f"brief-{DATE}.html"
    brief_path.write_text(html, encoding="utf-8")

    summary = {
        "date": DATE_ISO, "bullets": bullets, "news_top": news_top[:5],
        "nodes14": nodes14, "nodes60": nodes60,
        "brief_url": f"brief-{DATE}.html",
    }
    (OUT / f"summary-{DATE}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"brief written: {brief_path.name} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
