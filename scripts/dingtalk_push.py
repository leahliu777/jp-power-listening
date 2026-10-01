#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钉钉自定义机器人推送（加签模式）
读取 output/summary-YYYYMMDD.json 组装 markdown 摘要，POST 到 Webhook。
环境变量: DINGTALK_WEBHOOK, DINGTALK_SECRET, BRIEF_BASE_URL（简报页基础 URL，可选）
"""
import base64, datetime, hashlib, hmac, json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y%m%d")

WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")
SECRET = os.environ.get("DINGTALK_SECRET", "")
BRIEF_BASE = os.environ.get("BRIEF_BASE_URL", "").rstrip("/")


def sign_url(webhook, secret):
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"


def build_markdown(summary, dates):
    lines = [f"### 日本便携电源市场监听日报（{summary['date']}）"]
    lines.append("")
    for b in summary.get("bullets", []):
        # 去 HTML 标签
        import re
        txt = re.sub(r"<[^>]+>", "", b).strip()
        lines.append(f"- {txt}")
    lines.append("")
    if summary.get("news_top"):
        lines.append("**重点新闻**")
        for t in summary["news_top"][:3]:
            lines.append(f"- [{t['date']}] {t['title']}（{t['source']}）")
        lines.append("")
    if summary.get("nodes14"):
        lines.append("**临近节点**")
        for d, n, desc in summary["nodes14"][:3]:
            lines.append(f"- {d[5:]} {n}" + (f"：{desc}" if desc and len(desc) < 30 else ""))
        lines.append("")
    if BRIEF_BASE:
        lines.append(f"[查看完整简报（含趋势图与明细）]({BRIEF_BASE}/brief-{DATE}.html)")
    lines.append("")
    lines.append("> 数据口径：Google Trends 相对指数、按窗口归一化；环比为最后完整日 vs 前一日。")
    return "\n".join(lines)


def main():
    if not WEBHOOK or not SECRET:
        raise SystemExit("DINGTALK_WEBHOOK / DINGTALK_SECRET 未配置")
    summary_path = BASE / "output" / f"summary-{DATE}.json"
    if not summary_path.exists():
        raise SystemExit(f"summary not found: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    md = build_markdown(summary, DATE)
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": f"日本便携电源市场监听日报 {summary['date']}", "text": md},
    }
    url = sign_url(WEBHOOK, SECRET)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    print("dingtalk resp:", resp)
    if resp.get("errcode") != 0:
        raise SystemExit(f"DingTalk push failed: {resp}")


if __name__ == "__main__":
    main()
