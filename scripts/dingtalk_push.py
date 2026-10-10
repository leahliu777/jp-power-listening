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
    import re
    def clean(s): return re.sub(r"<[^>]+>", "", s).strip()
    lines = [f"### 📊 监听日报 · {summary['date'][5:]}"]
    lines.append("")
    lines.append("**🎯 今日重点**")
    for b in summary.get("bullets", []):
        lines.append(f"• {clean(b)}")
    lines.append("")
    if summary.get("news_top"):
        lines.append("**🔔 需要关注**")
        for t in summary["news_top"][:2]:
            lines.append(f"• [{clean(t['title'])}]({t['link']})（{t['source']}）")
        lines.append("")
    if summary.get("nodes14"):
        d, n, desc = summary["nodes14"][0]
        extra = f"：{desc}" if desc and desc != "国民の祝日" and len(desc) < 30 else ""
        lines.append(f"**📅 临近节点**：{n}（{d[5:]}{extra}）")
        lines.append("")
    PORTAL_URL = "https://leahliu777.github.io/jp-power-listening/"
    lines.append(f"[📊 打开监听中台]({PORTAL_URL})")
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
