#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Trends CSV 下载（Playwright 无头浏览器）
复刻已验证的桌面 UI 链路：加载 → 关闭弹窗 → 点「期間」→ 选「過去 7 日間」→ 点下载按钮 → 保存 CSV。
两组分别保存 data/trends_brands_YYYYMMDD.csv / data/trends_categories_YYYYMMDD.csv。
"""
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

DATE = datetime.date.today().strftime("%Y%m%d")

GROUPS = {
    "brands": {
        "url": "https://trends.google.com/trends/explore?geo=JP&hl=ja&q=Jackery,EcoFlow,Anker,Anker%20Solix,Bluetti",
        "expect_kw": ["Jackery", "EcoFlow", "Anker", "Bluetti"],
    },
    "categories": {
        "url": "https://trends.google.com/trends/explore?geo=JP&hl=ja&q=%E3%83%9D%E3%83%BC%E3%82%BF%E3%83%96%E3%83%AB%E9%9B%BB%E6%BA%90,%E3%83%9D%E3%83%BC%E3%82%BF%E3%83%96%E3%83%AB%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC",
        "expect_kw": ["ポータブル電源", "ポータブルバッテリー"],
    },
}

DISMISS_JS = """(texts) => {
  const bs = [...document.querySelectorAll('button')];
  for (const t of texts) {
    const b = bs.find(x => (x.textContent || '').trim() === t);
    if (b) { b.click(); return 'dismissed:' + t; }
  }
  return 'none';
}"""

CLICK_PERIOD_JS = """() => {
  const bs = [...document.querySelectorAll('button, [role=button]')];
  const b = bs.find(x => (x.textContent || '').replace(/\\s+/g, ' ').includes('期間'));
  if (b) { b.click(); return 'ok'; }
  return 'missing';
}"""

CLICK_7D_JS = """() => {
  const all = [...document.querySelectorAll('md-item, [role=menuitem], li, md-option')];
  let el = all.find(e => (e.textContent || '').trim() === '過去 7 日間');
  if (el) { el.click(); return 'ok'; }
  el = [...document.querySelectorAll('*')].find(e => e.children.length === 0 &&
        (e.textContent || '').trim() === '過去 7 日間' && e.offsetParent !== null);
  if (el) { el.click(); return 'leaf-ok'; }
  return 'missing';
}"""

CLICK_DOWNLOAD_JS = """() => {
  const bs = [...document.querySelectorAll('button')];
  const b = bs.find(x => (x.textContent || '').trim() === 'file_download');
  if (b) { b.click(); return 'ok'; }
  return 'missing';
}"""


def download_group(page, name, cfg):
    page.goto(cfg["url"], wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(15000)  # 等待 widget 完整渲染
    page.evaluate(DISMISS_JS, ["OK, got it", "Dismiss", "同意", "Accept all"])
    r = page.evaluate(CLICK_PERIOD_JS)
    if r == "missing":
        page.wait_for_timeout(8000)
        r = page.evaluate(CLICK_PERIOD_JS)
    if r == "missing":
        raise RuntimeError(f"{name}: 期間 button missing")
    page.wait_for_timeout(2500)
    r2 = page.evaluate(CLICK_7D_JS)
    if r2 == "missing":
        raise RuntimeError(f"{name}: 過去 7 日間 option missing")
    # 等待 URL 变为 date=now 7-d
    for _ in range(20):
        page.wait_for_timeout(1000)
        if "date=now%207-d" in page.url or "date=today%207-d" in page.url:
            break
    else:
        raise RuntimeError(f"{name}: 7-day URL not applied, url={page.url}")
    page.wait_for_timeout(10000)  # 小时序列加载
    page.evaluate(DISMISS_JS, ["Dismiss", "OK, got it"])
    with page.expect_download(timeout=60000) as dl_info:
        r3 = page.evaluate(CLICK_DOWNLOAD_JS)
        if r3 != "ok":
            raise RuntimeError(f"{name}: download button missing ({r3})")
    dl = dl_info.value
    target = DATA / f"trends_{name}_{DATE}.csv"
    dl.save_as(str(target))
    # 校验
    text = target.read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    rows = [l for l in lines if l.startswith("202")]
    ok_kw = all(k in text for k in cfg["expect_kw"])
    if not ok_kw or len(rows) < 150:
        raise RuntimeError(f"{name}: CSV invalid rows={len(rows)} ok_kw={ok_kw}")
    print(f"{name}: OK rows={len(rows)} -> {target.name}")
    return str(target)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        page = ctx.new_page()
        for name, cfg in GROUPS.items():
            download_group(page, name, cfg)
        ctx.close()
        browser.close()
    print("ALL DONE")


if __name__ == "__main__":
    main()
