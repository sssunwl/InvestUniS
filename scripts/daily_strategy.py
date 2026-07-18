"""
QQQ 日內期權 · 每日策略引擎 → 推送 Discord #n-investunis

這不是「預測漲跌」，是把 index.html「⚡ 期權」Tab 的決策樹，
機械地套上當天的真實數字（現價 / VIX / 預期波幅 / 事件），輸出：
  · 今天規則指向哪種策略
  · 用預期波幅算出的具體履約價（賣什麼、買什麼）
  · 去期權鏈抓那幾個履約價的真實 bid/ask，算出真實權利金與最大虧損

刻意不做的事：
  · 不捏造「成功率 87%／信心 89 分」——沒有歷史期權鏈就沒有真回測，
    假的信心分數最危險。勝率一律用常態近似並標明「非回測」。
  · 沒有驗證過的方向優勢 → 預設中性（Iron Condor），不硬猜漲跌。

依賴 market_state.json（workflow 會先跑 fetch_market_state.py 產生它）。
"""
import json
import sys
from datetime import date
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).parent.parent
# 可傳 ticker 當第一個參數（如 `python daily_strategy.py MU`）；不傳預設 QQQ。
TICKER = (sys.argv[1] if len(sys.argv) > 1 else "QQQ").upper()


def load_config(ticker):
    """讀 options_watchlist.json 取該標的參數；缺檔或缺標的用內建預設。"""
    default = {"spread_width": 5, "earnings_avoid_days": 2, "enabled": True}
    f = ROOT / "data" / "options_watchlist.json"
    if not f.exists():
        return default
    try:
        cfg = json.loads(f.read_text())
        return {**default, **cfg.get("_default", {}), **cfg.get(ticker, {})}
    except Exception as e:
        print(f"config err: {e}", file=sys.stderr)
        return default


CFG = load_config(TICKER)
SPREAD_WIDTH = CFG["spread_width"]  # 價差寬度（美元）


def nearest_strike(strikes, x):
    """吸附到期權鏈實際存在、最接近 x 的履約價；空鏈就原值回傳。"""
    strikes = [float(s) for s in strikes]
    return min(strikes, key=lambda k: abs(k - x)) if strikes else x


def mid(row):
    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    last = float(row.get("lastPrice", 0) or 0)
    return round(last, 2) if last > 0 else None


def leg_mid(chain_df, strike):
    """取某履約價的中間價；找不到精確履約價回傳 None。"""
    row = chain_df[chain_df["strike"] == strike]
    if row.empty:
        return None
    return mid(row.iloc[0])


def load_state():
    f = ROOT / "data" / ("market_state.json" if TICKER == "QQQ"
                         else f"market_state_{TICKER}.json")
    if not f.exists():
        # 保險：state 檔不在就即時產生（fetch 也吃同一個 TICKER 參數）
        import fetch_market_state
        fetch_market_state.main()
    return json.loads(f.read_text())


def round_strike(x):
    """QQQ 近月履約價間距為 $1，四捨五入到整數。"""
    return round(x)


def spread_credit(oc, kind, short_k, long_k):
    """從期權鏈算某垂直價差的真實淨權利金（賣腿中間價 − 買腿中間價）。"""
    if oc is None:
        return None
    df = oc.puts if kind == "put" else oc.calls
    smid, lmid = leg_mid(df, short_k), leg_mid(df, long_k)
    if smid is None or lmid is None:
        return None
    return round(smid - lmid, 2)


def directional_signal(und):
    """
    透明動能評分（-3 ~ +3），沿用頁面「日內／動能」Tab 教的均線邏輯：
      · 收盤 vs EMA20（短期趨勢）
      · EMA20 vs EMA50（中期趨勢）
      · 近 5 日動能（>+1% 偏多 / <-1% 偏空 / 之間中性）
    這是機械指標、會看錯，只用來在「中性收租」外多給一個方向傾向，不是預測。
    """
    try:
        hist = yf.Ticker(und).history(period="3mo")
    except Exception as e:
        print(f"signal hist err: {e}", file=sys.stderr)
        return None
    if hist.empty or len(hist) < 50:
        return None
    close = hist["Close"]
    last = float(close.iloc[-1])
    ema20 = float(close.ewm(span=20).mean().iloc[-1])
    ema50 = float(close.ewm(span=50).mean().iloc[-1])
    ret5 = (last / float(close.iloc[-6]) - 1) * 100

    score = 0
    factors = []
    if last > ema20:
        score += 1; factors.append(("收盤>EMA20", "✔"))
    else:
        score -= 1; factors.append(("收盤<EMA20", "✘"))
    if ema20 > ema50:
        score += 1; factors.append(("EMA20>EMA50", "✔"))
    else:
        score -= 1; factors.append(("EMA20<EMA50", "✘"))
    if ret5 > 1:
        score += 1; factors.append((f"5日動能{ret5:+.1f}%", "✔"))
    elif ret5 < -1:
        score -= 1; factors.append((f"5日動能{ret5:+.1f}%", "✘"))
    else:
        factors.append((f"5日動能{ret5:+.1f}%", "—"))

    bias = "bull" if score >= 2 else "bear" if score <= -2 else "neutral"
    return {"bias": bias, "score": score, "factors": factors}


def build_message(s):
    und = s.get("underlying", TICKER)
    spot = s.get("spot")
    today = date.today().isoformat()

    lines = [f"📊 {und} 日內期權 · 每日策略  {today}", "─" * 22]

    # 事實列
    if spot is not None:
        chg = s.get("chg_pct", 0)
        arrow = "▲" if (s.get("chg", 0) or 0) >= 0 else "▼"
        lines.append(f"現價 {spot}  {arrow}{abs(chg)}%")
    if s.get("vix") is not None:
        lines.append(f"VIX {s['vix']}  {s.get('vix_label','')}  "
                     f"{'🟢' if s['light']=='green' else '🟡' if s['light']=='yellow' else '🔴'}")
    if s.get("expected_move") is not None:
        lines.append(f"今日預期波幅 ({s.get('dte_label','')}): "
                     f"±{s['expected_move']}  → {s['em_low']} ~ {s['em_high']}")
    ev = s.get("events") or []
    lines.append(f"今日事件: {'、'.join(e.get('name','') for e in ev) if ev else '無'}")

    # 財報倒數（單一個股才有；指數/ETF 無此列）
    dte_earn = s.get("days_to_earnings")
    avoid_days = CFG.get("earnings_avoid_days", 0)
    earnings_block = False
    if dte_earn is not None:
        edate = s.get("earnings_date", "")
        if dte_earn < 0:
            lines.append(f"財報: 最近一次已過（{edate}）")
        else:
            flag = "⚠️ " if dte_earn <= avoid_days else ""
            lines.append(f"{flag}財報: {dte_earn} 天後（{edate}）")
            if dte_earn <= avoid_days:
                earnings_block = True
    lines.append("")

    # ── 決策樹 ──
    has_high_event = any((e.get("impact") == "high") for e in ev) or bool(ev)
    light = s.get("light", "unknown")
    em = s.get("expected_move")

    if earnings_block:
        lines.append(f"🚫 今日規則輸出: 不做賣方價差")
        lines.append(f"理由: {und} 財報 {dte_earn} 天內 → IV 灌爆、"
                     "財報後跳空會直接吃穿賣方價差。")
        lines.append("傾向觀望到財報消化完；若真要參與，只用有限風險的買方")
        lines.append("（Long Call/Put 或 Straddle 賭波幅，但注意賭錯方向/IV Crush）。")
    elif has_high_event or light == "red":
        reason = "有重大事件" if has_high_event else "VIX 恐慌區"
        lines.append(f"🚫 今日規則輸出: 不做賣方價差")
        lines.append(f"理由: {reason} → IV 劇烈、賣方尾部風險高。")
        lines.append("傾向觀望；若真要參與，只用有限風險的買方策略")
        lines.append("（Long Call/Put 或 Straddle，但注意 IV Crush 成本）。")
    elif em is None or spot is None:
        lines.append("⏸ 目前無即時 Straddle 報價（非交易時段）。")
        lines.append("開盤後本引擎會用當日預期波幅算出履約價。")
    else:
        # 透明方向訊號
        sig = directional_signal(und)
        bias = sig["bias"] if sig else "neutral"
        if sig:
            tag = {"bull": "偏多", "bear": "偏空", "neutral": "中性"}[bias]
            lines.append(f"📶 方向訊號: {tag}（評分 {sig['score']:+d}／範圍 -3~+3）")
            lines.append("  " + "  ·  ".join(f"{n}{m}" for n, m in sig["factors"]))
            lines.append("")

        try:
            oc = yf.Ticker(und).option_chain(s["expiry"])
        except Exception as e:
            print(f"chain err: {e}", file=sys.stderr)
            oc = None

        # 履約價：短腿設在 ±1 個預期波幅（≈1 標準差）處，
        # 再吸附到期權鏈實際存在的履約價（個股非 $1 一格，硬取整會抓不到報價）。
        put_strikes = list(oc.puts["strike"]) if oc is not None else []
        call_strikes = list(oc.calls["strike"]) if oc is not None else []
        put_short = nearest_strike(put_strikes, spot - em) if put_strikes else round_strike(spot - em)
        put_long = nearest_strike(put_strikes, put_short - SPREAD_WIDTH) if put_strikes else put_short - SPREAD_WIDTH
        call_short = nearest_strike(call_strikes, spot + em) if call_strikes else round_strike(spot + em)
        call_long = nearest_strike(call_strikes, call_short + SPREAD_WIDTH) if call_strikes else call_short + SPREAD_WIDTH

        def fmt(k):
            return f"{k:g}"

        def credit_line(kind, sk, lk):
            c = spread_credit(oc, kind, sk, lk)
            width = abs(sk - lk)
            if c is not None and c > 0 and width > 0:
                ml = round((width - c) * 100, 0)
                return f"實際權利金≈ ${c} /組  ·  最大虧損≈ ${ml:.0f}（寬度 ${width:g}）"
            return None

        if bias == "bull":
            lines.append("🎯 今日規則輸出: Bull Put Spread（偏多收租）")
            lines.append(f"賣 Put {fmt(put_short)}  /  買 Put {fmt(put_long)}")
            lines.append(f"→ 只要收盤 > {fmt(put_short)}（不必大漲、不跌破即可），權利金全收")
            cl = credit_line("put", put_short, put_long)
            if cl:
                lines.append(cl)
            lines.append("約略勝率: ~84%（單邊常態近似，非回測）")
        elif bias == "bear":
            lines.append("🎯 今日規則輸出: Bear Call Spread（偏空收租）")
            lines.append(f"賣 Call {fmt(call_short)}  /  買 Call {fmt(call_long)}")
            lines.append(f"→ 只要收盤 < {fmt(call_short)}（不必大跌、不突破即可），權利金全收")
            cl = credit_line("call", call_short, call_long)
            if cl:
                lines.append(cl)
            lines.append("約略勝率: ~84%（單邊常態近似，非回測）")
        else:
            lines.append("🎯 今日規則輸出: Iron Condor（中性收租）")
            lines.append(f"賣 Put {fmt(put_short)} / 買 Put {fmt(put_long)}")
            lines.append(f"賣 Call {fmt(call_short)} / 買 Call {fmt(call_long)}")
            lines.append(f"→ 收盤落在 {fmt(put_short)}~{fmt(call_short)} 之間，兩邊全收")
            c1 = spread_credit(oc, "put", put_short, put_long)
            c2 = spread_credit(oc, "call", call_short, call_long)
            if c1 and c2:
                tot = round(c1 + c2, 2)
                width = max(abs(put_short - put_long), abs(call_short - call_long))
                ml = round((width - tot) * 100, 0)
                lines.append(f"實際權利金≈ ${tot} /組  ·  單邊最大虧損≈ ${ml:.0f}（寬度 ${width:g}）")
            lines.append("約略勝率: ~68%（常態近似，非回測）")

    # ── 免責 ──
    lines.append("")
    lines.append("⚠️ 這不是投資建議，是把頁面決策樹套上今天的數字。")
    lines.append("方向訊號＝機械動能指標，會看錯；偏多/偏空代表你在賭方向，")
    lines.append("趨勢反向會直接吃掉那一邊。勝率為常態近似非回測。")
    lines.append("履約價/手數/是否進場請自行判斷；賣方負偏態＝贏小輸大。")

    return "\n".join(lines)


def main():
    s = load_state()
    msg = build_message(s)
    print(msg)
    print("\n" + "=" * 40)
    try:
        from _discord import notify_discord
        notify_discord(msg)
        print("→ 已嘗試推送 Discord #n-investunis")
    except Exception as e:
        print(f"discord err: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
