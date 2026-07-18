"""
市場狀態事實卡 — 每日自動抓取 QQQ 日內期權的「事實」，非買賣建議。

輸出 data/market_state.json，供 index.html「⏰ 日內」Tab 頂端的事實卡讀取。

三個核心事實：
  ① QQQ 現價與日變動
  ② VIX 波動率分級（市場對未來 30 天的恐慌程度）
  ③ 真實預期波幅 Expected Move —— 用最近到期的 ATM Straddle 中間價反推，
     而不是用 VIX×√T 硬套。VIX 是 30 天的，0DTE 要看當日 straddle 才對。

事件（CPI/FOMC/非農）走 data/econ_events.json（人工維護），今天命中才標示。
全程 try/except 包住，任何一項抓不到都不讓 workflow 掛掉。
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

import yfinance as yf
import pandas as pd

ROOT = Path(__file__).parent.parent
# 可傳 ticker 當第一個參數（如 `python fetch_market_state.py MU`）；不傳預設 QQQ。
UNDERLYING = (sys.argv[1] if len(sys.argv) > 1 else "QQQ").upper()


def state_path(ticker):
    """QQQ 沿用原檔名（index.html 事實卡讀它）；其餘個股各自一檔，互不覆蓋。"""
    return ROOT / "data" / ("market_state.json" if ticker == "QQQ"
                            else f"market_state_{ticker}.json")


def next_earnings(t):
    """抓最近一次『未來』財報日與距今天數；指數/ETF 沒財報就回 None。"""
    try:
        df = t.get_earnings_dates(limit=12)
    except Exception as e:
        print(f"earnings err: {e}", file=sys.stderr)
        return None
    if df is None or df.empty:
        return None
    try:
        future = df[df.index.date >= date.today()]
        if future.empty:
            return None
        d = min(future.index).date()
        return {"date": d.isoformat(), "days": (d - date.today()).days}
    except Exception as e:
        print(f"earnings parse err: {e}", file=sys.stderr)
        return None


def vix_regime(vix):
    """把 VIX 讀數對到市場狀態。門檻沿用頁面既有的教學分級。"""
    if vix is None:
        return "unknown", "—", "VIX 資料暫缺"
    if vix < 15:
        return "green", "平靜", "市場預期未來 30 天很平靜"
    if vix < 20:
        return "green", "正常", "市場預期未來 30 天波動正常"
    if vix < 30:
        return "yellow", "波動偏大", "市場開始不安，波動放大"
    if vix < 40:
        return "red", "恐慌", "市場恐慌，賣方策略風險升高"
    return "red", "極端", "極端事件等級（金融危機/系統性風險）"


def mid_price(row):
    """取 bid/ask 中間價；盤後 bid/ask 可能為 0，退回 lastPrice。"""
    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    last = float(row.get("lastPrice", 0) or 0)
    return last if last > 0 else None


def nearest_expiry_straddle(t, spot):
    """
    找最近到期日的 ATM Straddle（最接近現價的履約價 Call+Put），
    回傳 (expiry_str, dte, straddle_price, atm_iv)。
    Straddle 中間價 ≈ 市場對「到期前」波幅的定價。
    """
    expiries = t.options
    if not expiries:
        return None
    today = date.today()
    # 取第一個 >= 今天的到期日（通常就是 0DTE 或最近一檔）
    chosen = None
    for e in expiries:
        if datetime.strptime(e, "%Y-%m-%d").date() >= today:
            chosen = e
            break
    if chosen is None:
        chosen = expiries[0]

    dte = (datetime.strptime(chosen, "%Y-%m-%d").date() - today).days
    chain = t.option_chain(chosen)
    calls, puts = chain.calls, chain.puts
    if calls.empty or puts.empty:
        return None

    # ATM = 履約價最接近現價
    atm_strike = calls.iloc[(calls["strike"] - spot).abs().argmin()]["strike"]
    call_row = calls[calls["strike"] == atm_strike]
    put_row = puts[puts["strike"] == atm_strike]
    if call_row.empty or put_row.empty:
        return None

    c_mid = mid_price(call_row.iloc[0])
    p_mid = mid_price(put_row.iloc[0])
    if c_mid is None or p_mid is None:
        return None

    straddle = c_mid + p_mid
    # ATM IV：取 Call/Put 兩邊 impliedVolatility 平均
    ivs = [float(x) for x in (call_row.iloc[0].get("impliedVolatility"),
                              put_row.iloc[0].get("impliedVolatility")) if x]
    atm_iv = round(sum(ivs) / len(ivs), 4) if ivs else None

    return {
        "expiry": chosen,
        "dte": dte,
        "atm_strike": round(float(atm_strike), 2),
        "straddle": round(straddle, 2),
        "atm_iv": atm_iv,
    }


def todays_events():
    """讀人工維護的 econ_events.json，回傳今天命中的重大事件清單。"""
    f = ROOT / "data" / "econ_events.json"
    if not f.exists():
        return []
    try:
        events = json.loads(f.read_text())
        today = date.today().isoformat()
        return [e for e in events.get("events", []) if e.get("date") == today]
    except Exception as e:
        print(f"events read err: {e}", file=sys.stderr)
        return []


def main():
    out = {
        "updated": pd.Timestamp.now(tz="Asia/Hong_Kong").strftime("%Y-%m-%d %H:%M HKT"),
        "underlying": UNDERLYING,
        "disclaimer": "以下均為市場當下的『事實』與教學說明，非買賣建議。期權有歸零風險，交易前請自行判斷。",
    }

    # ── ① QQQ 現價 ──
    spot = None
    try:
        t = yf.Ticker(UNDERLYING)
        hist = t.history(period="5d")
        if not hist.empty:
            spot = round(float(hist["Close"].iloc[-1]), 2)
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else spot
            out["spot"] = spot
            out["chg"] = round(spot - prev, 2)
            out["chg_pct"] = round((spot - prev) / prev * 100, 2) if prev else 0
    except Exception as e:
        print(f"spot err: {e}", file=sys.stderr)

    # ── ② VIX 分級 ──
    try:
        vhist = yf.Ticker("^VIX").history(period="5d")
        vix = round(float(vhist["Close"].iloc[-1]), 2) if not vhist.empty else None
        state, label, desc = vix_regime(vix)
        out["vix"] = vix
        out["vix_state"] = state
        out["vix_label"] = label
        out["vix_desc"] = desc
    except Exception as e:
        print(f"vix err: {e}", file=sys.stderr)
        out["vix_state"] = "unknown"

    # ── ③ 真實預期波幅（ATM Straddle） ──
    if spot:
        try:
            sd = nearest_expiry_straddle(t, spot)
            if sd:
                em = round(sd["straddle"] * 0.85, 2)  # 1 標準差 ≈ straddle × 0.85
                out["expected_move"] = em
                out["em_low"] = round(spot - em, 2)
                out["em_high"] = round(spot + em, 2)
                out["dte"] = sd["dte"]
                out["dte_label"] = "0DTE（今日到期）" if sd["dte"] == 0 else f"{sd['dte']}DTE"
                out["atm_strike"] = sd["atm_strike"]
                out["straddle"] = sd["straddle"]
                out["expiry"] = sd["expiry"]
                # yfinance 在 0DTE 的 impliedVolatility 常崩壞（回傳接近 0 的垃圾值），
                # 只在 DTE≥1 且數值合理時才顯示 IV；否則以 straddle 反推的預期波幅為準。
                out["atm_iv"] = (round(sd["atm_iv"] * 100, 1)
                                 if sd["atm_iv"] and sd["dte"] >= 1 and sd["atm_iv"] > 0.03
                                 else None)
        except Exception as e:
            print(f"straddle err: {e}", file=sys.stderr)

    # ── 事件 ──
    out["events"] = todays_events()

    # ── 財報（單一個股才有；QQQ 回 None） ──
    try:
        ne = next_earnings(t) if spot else None
        if ne:
            out["earnings_date"] = ne["date"]
            out["days_to_earnings"] = ne["days"]
    except Exception as e:
        print(f"earnings block err: {e}", file=sys.stderr)

    # ── 綜合市場狀態燈號（取 VIX 燈號；有重大事件則至少黃燈） ──
    light = out.get("vix_state", "unknown")
    if out["events"] and light == "green":
        light = "yellow"
    out["light"] = light

    dest = state_path(UNDERLYING)
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"Saved {dest.name}")
    print(f"  {UNDERLYING} {out.get('spot','?')}  ({out.get('chg_pct','?')}%)")
    print(f"  VIX {out.get('vix','?')} [{out.get('vix_label','?')}]  light={out['light']}")
    if out.get("expected_move"):
        print(f"  {out.get('dte_label','')}  EM ±{out['expected_move']}  "
              f"→ {out.get('em_low')}~{out.get('em_high')}  (straddle {out.get('straddle')})")
    print(f"  events: {[e.get('name') for e in out['events']] or '無'}")
    if out.get("earnings_date"):
        print(f"  earnings: {out['earnings_date']} (D-{out.get('days_to_earnings')})")


if __name__ == "__main__":
    main()
