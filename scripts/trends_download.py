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

RANGE_LEAF_RE = "過去 (12|6|3|1) か月間|Past (12|6|3|1) months|過去 12 個月|過去 3 個月"
_7D_TEXTS = ["過去 7 日間", "Past 7 days", "過去 7 天"]

CLICK_PERIOD_JS = """() => {
  const bs = [...document.querySelectorAll('button, [role=button]')];
  const b = bs.find(x => ['期間','Time','時間'].some(k => (x.textContent || '').replace(/\\s+/g, ' ').includes(k)));
  if (b) { b.click(); return 'ok'; }
  return 'missing';
}"""

CLICK_DOWNLOAD_JS = """() => {
  let b = [...document.querySelectorAll('button')].find(x => (x.textContent || '').trim() === 'file_download');
  if (b) { b.click(); return 'ok'; }
  b = [...document.querySelectorAll('button,[role=button],a')].find(x =>
    /download/i.test((x.getAttribute('aria-label')||'') + '|' + (x.getAttribute('title')||'')));
  if (b) { b.click(); return 'aria-ok'; }
  return 'missing';
}"""


def click_download_with_retry(page, name):
    """轮询下载按钮（页面切换后重新挂载），找不到则重载 7 天视图再试"""
    for attempt in range(2):
        for _ in range(20):
            r = page.evaluate(CLICK_DOWNLOAD_JS)
            if r != "missing":
                return r
            page.wait_for_timeout(3000)
        if attempt == 0:
            print(f"[{name}] download button not found, reloading 7d view")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(12000)
            page.evaluate(DISMISS_JS, ["OK, got it", "Dismiss", "同意", "Accept all"])
    return "missing"


def dump_state(page, name, reason):
    """失败诊断：输出页面标题/URL/按钮列表/文本片段到日志"""
    try:
        title = page.title()
        btns = page.evaluate("""() => [...document.querySelectorAll('button')].slice(0,30).map(b => (b.textContent||'').trim()).filter(Boolean)""")
        body = page.evaluate("""() => (document.body ? document.body.innerText.slice(0, 400) : '')""")
        print(f"[DIAG {name}] reason={reason} title={title!r} url={page.url}")
        print(f"[DIAG {name}] buttons={btns}")
        print(f"[DIAG {name}] body={body!r}")
    except Exception as e:
        print(f"[DIAG {name}] failed: {e}")


def has_7d_option(page):
    """菜单中是否出现可见的「過去 7 日間」选项"""
    try:
        return page.evaluate(
            """(texts) => [...document.querySelectorAll('md-item,[role=menuitem],[role=option],li,md-option,div,span,button')]
              .filter(e => e.children.length === 0 && texts.includes((e.textContent||'').trim()) && e.offsetParent !== null).length""",
            _7D_TEXTS,
        )
    except Exception:
        return 0


def click_7d_option(page):
    """点击菜单中的「過去 7 日間」选项"""
    return page.evaluate(
        """(texts) => {
  const all = [...document.querySelectorAll('md-item,[role=menuitem],[role=option],li,md-option,div,span,button')];
  let el = all.find(e => texts.includes((e.textContent || '').trim()));
  if (el) { el.click(); return 'ok'; }
  el = [...document.querySelectorAll('*')].find(e => e.children.length === 0 &&
        texts.some(t => (e.textContent || '').trim() === t) && e.offsetParent !== null);
  if (el) { el.click(); return 'leaf-ok'; }
  return 'missing';
}""",
        _7D_TEXTS,
    )


def switch_to_7d(page, name, cfg):
    """多策略切换 7 天窗口：
    1) 旧 UI：点「期間/Time/時間」按钮打开菜单
    2) 新 UI：点范围文本（過去 12 か月間…）叶子并逐层向上点击，直到菜单出现
    3) 兜底：URL 直接追加 date=now%207-d 重载
    """
    # 策略1: 旧 UI 按钮
    page.evaluate(CLICK_PERIOD_JS)
    page.wait_for_timeout(1200)
    if has_7d_option(page):
        return click_7d_option(page)
    # 策略2: 新 UI 逐层点击范围文本
    for i in range(1, 4):
        page.evaluate(
            f"""() => {{
  const re = /{RANGE_LEAF_RE}/;
  let el = [...document.querySelectorAll('*')].find(e =>
    e.children.length === 0 && re.test((e.textContent||'').trim()) && e.offsetParent !== null);
  if (!el) return 'none';
  for (let d = 0; d < {i}; d++) {{ el = el.parentElement; if (!el) break; }}
  if (el) {{ el.click(); return 'clicked:' + el.tagName; }}
  return 'none';
}}"""
        )
        page.wait_for_timeout(1000)
        if has_7d_option(page):
            return click_7d_option(page)
    # 策略3: 兜底 URL 重载
    page.goto(cfg["url"] + "&date=now%207-d", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    return None


def download_group(page, name, cfg):
    page.goto(cfg["url"], wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(15000)  # 等待 widget 完整渲染
    page.evaluate(DISMISS_JS, ["OK, got it", "Dismiss", "同意", "Accept all"])
    r = switch_to_7d(page, name, cfg)
    if r == "missing":
        dump_state(page, name, "7d option click failed")
        raise RuntimeError(f"{name}: 過去 7 日間 option missing")
    # 等待 URL 变为 date=now 7-d
    for _ in range(20):
        page.wait_for_timeout(1000)
        if "date=now%207-d" in page.url or "date=today%207-d" in page.url:
            break
    else:
        dump_state(page, name, "7-day URL not applied")
        raise RuntimeError(f"{name}: 7-day URL not applied, url={page.url}")
    page.wait_for_timeout(10000)  # 小时序列加载
    page.evaluate(DISMISS_JS, ["Dismiss", "OK, got it"])
    with page.expect_download(timeout=150000) as dl_info:
        r3 = click_download_with_retry(page, name)
    if r3 == "missing":
        dump_state(page, name, "download button missing after retry")
        raise RuntimeError(f"{name}: download button missing")
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
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"},
        )
        page = ctx.new_page()
        for name, cfg in GROUPS.items():
            download_group(page, name, cfg)
        ctx.close()
        browser.close()
    print("ALL DONE")


if __name__ == "__main__":
    main()
