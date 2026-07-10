"""
Momentum Breakout Radar V1 — 每日掃描觀察清單（data/breakout_watchlist.txt），
套用網站「動能」Tab 記載的 Scanner A/B 條件，找出符合的候選股並推送到 TG。

篩選條件（對應 index.html 動能 Tab）：
  - Price > $10
  - Avg Volume(20d) > 500K
  - Market Cap > $300M
  - Float 20M–100M（甜蜜區間）
  - Price above SMA20
  - RVOL(今日量 / 20日均量) > 2
  - Scanner A 額外要求：距 52 週高點 ≤ 3%
  - Scanner B：不要求 52 週高點，抓「量開始異動但還沒突破」的股票

局限：只掃觀察清單裡的股票，不是全市場即時篩選（免費資料源做不到）。
清單需要你自己定期用 Finviz 免費篩選器維護，見 data/breakout_watchlist.txt。
"""
import html as _html
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

WATCHLIST_PATH = Path(__file__).parent.parent / "data" / "breakout_watchlist.txt"
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TG_CHAT_ID", "")

NEAR_52W_HIGH_PCT = 0.03


def esc(text):
    return _html.escape(str(text or ""), quote=False)


def load_watchlist():
    tickers = []
    for line in WATCHLIST_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tickers.append(line)
    return tickers


def scan_ticker(ticker: str):
    t = yf.Ticker(ticker)
    hist = t.history(period="1y")
    if hist.empty or len(hist) < 25:
        return None

    close = hist["Close"]
    volume = hist["Volume"]

    price = float(close.iloc[-1])
    sma20 = float(close.iloc[-20:].mean())
    avg_vol20 = float(volume.iloc[-21:-1].mean())  # 排除今天，避免今天巨量把自己均量拉高
    today_vol = float(volume.iloc[-1])
    rvol = today_vol / avg_vol20 if avg_vol20 > 0 else 0
    high_52w = float(close.max())
    dist_to_high = (high_52w - price) / high_52w if high_52w > 0 else 1

    try:
        info = t.get_info()
    except Exception:
        info = {}
    market_cap = info.get("marketCap") or 0
    float_shares = info.get("floatShares") or 0

    base_ok = (
        price > 10
        and avg_vol20 > 500_000
        and market_cap > 300_000_000
        and 20_000_000 <= float_shares <= 100_000_000
        and price > sma20
        and rvol > 2
    )
    scanner_a = base_ok and dist_to_high <= NEAR_52W_HIGH_PCT
    scanner_b = base_ok and not scanner_a

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "rvol": round(rvol, 2),
        "dist_to_52w_high_pct": round(dist_to_high * 100, 1),
        "above_sma20": price > sma20,
        "market_cap_m": round(market_cap / 1_000_000, 0),
        "float_m": round(float_shares / 1_000_000, 1),
        "scanner_a": scanner_a,
        "scanner_b": scanner_b,
    }


def format_message(rows_a, rows_b):
    lines = ["📈 <b>動能突破雷達 — 今日候選</b>\n"]

    if rows_a:
        lines.append("🚀 <b>Scanner A（已突破，立即行動型）</b>")
        for r in rows_a[:5]:
            lines.append(
                f"• <b>{esc(r['ticker'])}</b>  ${r['price']}  RVOL {r['rvol']}x  "
                f"距52週高 {r['dist_to_52w_high_pct']}%"
            )
        lines.append("")
    else:
        lines.append("🚀 Scanner A：今天沒有符合條件的候選股\n")

    if rows_b:
        lines.append("⏳ <b>Scanner B（準備突破，提前佈局型）</b>")
        for r in rows_b[:5]:
            lines.append(
                f"• <b>{esc(r['ticker'])}</b>  ${r['price']}  RVOL {r['rvol']}x  "
                f"距52週高 {r['dist_to_52w_high_pct']}%"
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
    tickers = load_watchlist()
    results = []
    for ticker in tickers:
        try:
            r = scan_ticker(ticker)
            if r:
                results.append(r)
                print(f"{ticker:6s} price={r['price']:<8} rvol={r['rvol']:<5} "
                      f"A={r['scanner_a']} B={r['scanner_b']}")
        except Exception as e:
            print(f"ERR {ticker}: {e}", file=sys.stderr)

    rows_a = sorted([r for r in results if r["scanner_a"]], key=lambda r: -r["rvol"])
    rows_b = sorted([r for r in results if r["scanner_b"]], key=lambda r: -r["rvol"])

    msg = format_message(rows_a, rows_b)
    print("\n" + msg.replace("<b>", "").replace("</b>", ""))

    if BOT_TOKEN and CHAT_ID:
        send_tg(msg)
    else:
        print("\n(TG_BOT_TOKEN/TG_CHAT_ID 未設定，僅本地輸出，不發送)", file=sys.stderr)


if __name__ == "__main__":
    main()
