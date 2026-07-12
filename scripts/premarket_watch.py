"""
開市前 30 分鐘關注清單 — 跟 breakout_scanner.py（開盤後 Scanner A/B）邏輯不同：
這裡沒有「今天的RVOL」可用（市場還沒開盤，沒有正式成交量），所以改用 Yahoo
自家的伺服器端篩選器（yf.screen）抓「盤前漲幅最大」「異動最活躍」的股票，
不用像 breakout_scanner.py 那樣自己掃全市場 5000+ 檔（那個成本只值得開盤後
用RVOL篩選時付）。

輸出：盤前漲幅前5、成交最活躍前5，附盤前價格變化%，供你開盤前快速掃過一眼。
不是 Scanner A/B 的替代品，是互補的「開盤前先看有什麼在動」。
"""
import html as _html
import os
import sys

import requests
import yfinance as yf

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TG_CHAT_ID", "")


def esc(text):
    return _html.escape(str(text or ""), quote=False)


def fetch_screen(query_name, count=10):
    try:
        res = yf.screen(query_name, count=count)
        return res.get("quotes", [])
    except Exception as e:
        print(f"screen({query_name}) failed: {e}", file=sys.stderr)
        return []


def pick_fields(quotes):
    rows = []
    for q in quotes:
        rows.append({
            "ticker": q.get("symbol", ""),
            "name": q.get("shortName") or q.get("longName") or "",
            "price": q.get("regularMarketPrice"),
            "pm_price": q.get("preMarketPrice"),
            "pm_change_pct": q.get("preMarketChangePercent"),
            "regular_change_pct": q.get("regularMarketChangePercent"),
        })
    return rows


def format_message(gainers, actives):
    lines = ["🌅 <b>盤前關注清單</b>（開市前約30分鐘）\n"]

    lines.append("📈 <b>盤前漲幅 Top</b>")
    any_pm = any(r["pm_change_pct"] is not None for r in gainers)
    if not any_pm:
        lines.append("（目前抓不到盤前逐筆變化%，改顯示昨日收盤異動排名，僅供參考）")
    for r in gainers[:5]:
        chg = r["pm_change_pct"] if r["pm_change_pct"] is not None else r["regular_change_pct"]
        chg_str = f"{chg:+.1f}%" if chg is not None else "N/A"
        lines.append(f"• <b>{esc(r['ticker'])}</b> {esc(r['name'])}  {chg_str}")
    lines.append("")

    lines.append("🔥 <b>成交最活躍 Top</b>")
    for r in actives[:5]:
        chg = r["pm_change_pct"] if r["pm_change_pct"] is not None else r["regular_change_pct"]
        chg_str = f"{chg:+.1f}%" if chg is not None else "N/A"
        lines.append(f"• <b>{esc(r['ticker'])}</b> {esc(r['name'])}  {chg_str}")
    lines.append("")

    lines.append(
        "⚠️ 這是盤前初步異動清單，不是 Scanner A/B 確認突破（那個要等開盤後30-60分鐘"
        "RVOL算出來才發）。進場前先查有沒有真實催化劑（財報/新聞），別看到漲就追。"
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
    gainers = pick_fields(fetch_screen("day_gainers", count=10))
    actives = pick_fields(fetch_screen("most_actives", count=10))

    msg = format_message(gainers, actives)
    print(msg.replace("<b>", "").replace("</b>", ""))

    if BOT_TOKEN and CHAT_ID:
        send_tg(msg)
    else:
        print("\n(TG_BOT_TOKEN/TG_CHAT_ID 未設定，僅本地輸出，不發送)", file=sys.stderr)


if __name__ == "__main__":
    main()
