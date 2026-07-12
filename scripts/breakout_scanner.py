"""
Momentum Breakout Radar V1 — 每日全美股（NASDAQ + NYSE/AMEX）動能突破掃描。

分兩階段避免對每一檔股票都呼叫慢的 yfinance .info()：
  1. 從 nasdaqtrader.com 抓完整美股清單（公開、免登入），過濾掉 ETF、測試代碼、
     權證/單位/優先股等非普通股。
  2. 用 yfinance 批次下載（每批 ~300 檔）1年價量資料，用便宜的欄位先篩一輪：
     Price>$10、Avg Volume(20d)>500K、RVOL>2、股價站上 SMA20。
  3. 只對通過第2步的少數候選呼叫 .info() 查市值/Float，套用 Scanner A/B 最終條件
     （Market Cap>$300M、Float 20M-100M；Scanner A 另外要求距52週高點≤3%）。
  4. 依 RVOL 排序，各取前5名發送到 TG。

已知風險：這是對 Yahoo Finance 做大量批次請求，GitHub Actions 的共用 IP 有機率被
Yahoo 限流/擋掉，若某天發現候選數異常變 0 或整批失敗，先檢查是不是被限流，不代表
篩選邏輯壞了。
"""
import html as _html
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TG_CHAT_ID", "")

NEAR_52W_HIGH_PCT = 0.03
BATCH_SIZE = 300
BATCH_SLEEP_SEC = 1.5

EXCLUDE_NAME_KEYWORDS = [
    "Warrant", "Right", "Rights", "Unit", "Units", "Preferred",
    "Depositary", "Notes ", "Debenture", "Trust Pfd",
]

UNIVERSE_URLS = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}


def esc(text):
    return _html.escape(str(text or ""), quote=False)


def fetch_universe():
    tickers = set()

    r = requests.get(UNIVERSE_URLS["nasdaq"], timeout=20)
    for line in r.text.splitlines()[1:-1]:
        parts = line.split("|")
        if len(parts) < 7:
            continue
        symbol, name, _cat, test_issue, _fin, _lot, etf = parts[:7]
        if test_issue == "Y" or etf == "Y":
            continue
        if any(k in name for k in EXCLUDE_NAME_KEYWORDS):
            continue
        if "." in symbol or "$" in symbol:
            continue
        tickers.add(symbol)

    r = requests.get(UNIVERSE_URLS["other"], timeout=20)
    for line in r.text.splitlines()[1:-1]:
        parts = line.split("|")
        if len(parts) < 7:
            continue
        act_symbol, name, _exch, _cqs, etf, _lot, test_issue = parts[:7]
        if test_issue == "Y" or etf == "Y":
            continue
        if any(k in name for k in EXCLUDE_NAME_KEYWORDS):
            continue
        if "." in act_symbol or "$" in act_symbol:
            continue
        tickers.add(act_symbol)

    return sorted(tickers)


def cheap_screen_batch(tickers):
    """回傳通過便宜篩選（不含市值/Float）的候選 dict 列表。"""
    try:
        data = yf.download(tickers, period="1y", group_by="ticker", threads=True, progress=False)
    except Exception as e:
        print(f"batch download failed: {e}", file=sys.stderr)
        return []

    survivors = []
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                sub = data
            else:
                sub = data[ticker]
        except (KeyError, TypeError):
            continue

        close = sub["Close"].dropna()
        volume = sub["Volume"].dropna()
        if len(close) < 25 or len(volume) < 25:
            continue

        price = float(close.iloc[-1])
        sma20 = float(close.iloc[-20:].mean())
        avg_vol20 = float(volume.iloc[-21:-1].mean())
        today_vol = float(volume.iloc[-1])
        rvol = today_vol / avg_vol20 if avg_vol20 > 0 else 0
        high_52w = float(close.max())
        dist_to_high = (high_52w - price) / high_52w if high_52w > 0 else 1

        if price > 10 and avg_vol20 > 500_000 and rvol > 2 and price > sma20:
            survivors.append({
                "ticker": ticker,
                "price": round(price, 2),
                "rvol": round(rvol, 2),
                "dist_to_52w_high_pct": round(dist_to_high * 100, 1),
            })

    return survivors


def enrich_with_fundamentals(candidates):
    out = []
    for c in candidates:
        try:
            info = yf.Ticker(c["ticker"]).get_info()
        except Exception:
            continue
        market_cap = info.get("marketCap") or 0
        float_shares = info.get("floatShares") or 0
        if not (market_cap > 300_000_000 and 20_000_000 <= float_shares <= 100_000_000):
            continue
        c["market_cap_m"] = round(market_cap / 1_000_000, 0)
        c["float_m"] = round(float_shares / 1_000_000, 1)
        c["scanner_a"] = c["dist_to_52w_high_pct"] <= NEAR_52W_HIGH_PCT * 100
        out.append(c)
    return out


def format_message(rows_a, rows_b, scanned_count):
    lines = [f"📈 <b>動能突破雷達 — 今日候選</b>（全市場掃描 {scanned_count} 檔）\n"]

    if rows_a:
        lines.append("🚀 <b>Scanner A（已突破，立即行動型）</b>")
        for r in rows_a[:5]:
            lines.append(
                f"• <b>{esc(r['ticker'])}</b>  ${r['price']}  RVOL {r['rvol']}x  "
                f"市值${r['market_cap_m']}M  Float{r['float_m']}M  距52週高{r['dist_to_52w_high_pct']}%"
            )
        lines.append("")
    else:
        lines.append("🚀 Scanner A：今天沒有符合條件的候選股\n")

    if rows_b:
        lines.append("⏳ <b>Scanner B（準備突破，提前佈局型）</b>")
        for r in rows_b[:5]:
            lines.append(
                f"• <b>{esc(r['ticker'])}</b>  ${r['price']}  RVOL {r['rvol']}x  "
                f"市值${r['market_cap_m']}M  Float{r['float_m']}M"
            )
        lines.append("")
    else:
        lines.append("⏳ Scanner B：今天沒有符合條件的候選股\n")

    lines.append(
        "⚠️ 只是篩選結果，不是買賣建議。進場前記得查催化劑、看圖表結構、確認板塊強弱、"
        "查財報日、對比量能（見網站「動能」Tab 五步流程）。"
    )
    return "\n".join(lines)


def send_tg(text):
    try:  # 同時鏡射到 Discord #n-investunis(失敗不影響 TG)
        from _discord import notify_discord
        notify_discord(text)
    except Exception:
        pass
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        api_url,
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=20,
    )
    if not r.ok:
        print(f"TG {r.status_code}: {r.text}", file=sys.stderr)
    r.raise_for_status()
    return r.json()


def main():
    universe = fetch_universe()
    print(f"股票清單: {len(universe)} 檔", file=sys.stderr)

    all_survivors = []
    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i + BATCH_SIZE]
        survivors = cheap_screen_batch(batch)
        all_survivors.extend(survivors)
        print(f"批次 {i}-{i+len(batch)}: {len(survivors)} 檔通過初篩", file=sys.stderr)
        time.sleep(BATCH_SLEEP_SEC)

    print(f"初篩後共 {len(all_survivors)} 檔候選，開始查市值/Float...", file=sys.stderr)
    candidates = enrich_with_fundamentals(all_survivors)

    rows_a = sorted([c for c in candidates if c["scanner_a"]], key=lambda r: -r["rvol"])
    rows_b = sorted([c for c in candidates if not c["scanner_a"]], key=lambda r: -r["rvol"])

    msg = format_message(rows_a, rows_b, len(universe))
    print("\n" + msg.replace("<b>", "").replace("</b>", ""))

    if BOT_TOKEN and CHAT_ID:
        send_tg(msg)
    else:
        print("\n(TG_BOT_TOKEN/TG_CHAT_ID 未設定，僅本地輸出，不發送)", file=sys.stderr)


if __name__ == "__main__":
    main()
