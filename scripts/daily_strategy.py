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
SPREAD_WIDTH = 5  # 價差寬度（點）


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
    f = ROOT / "data" / "market_state.json"
    if not f.exists():
        # 保險：market_state.json 不在就即時產生
        import fetch_market_state
        fetch_market_state.main()
    return json.loads(f.read_text())


def round_strike(x):
    """QQQ 近月履約價間距為 $1，四捨五入到整數。"""
    return round(x)


def build_message(s):
    und = s.get("underlying", "QQQ")
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
    lines.append("")

    # ── 決策樹 ──
    has_high_event = any((e.get("impact") == "high") for e in ev) or bool(ev)
    light = s.get("light", "unknown")
    em = s.get("expected_move")

    if has_high_event or light == "red":
        reason = "有重大事件" if has_high_event else "VIX 恐慌區"
        lines.append(f"🚫 今日規則輸出: 不做賣方價差")
        lines.append(f"理由: {reason} → IV 劇烈、賣方尾部風險高。")
        lines.append("傾向觀望；若真要參與，只用有限風險的買方策略")
        lines.append("（Long Call/Put 或 Straddle，但注意 IV Crush 成本）。")
    elif em is None or spot is None:
        lines.append("⏸ 目前無即時 Straddle 報價（非交易時段）。")
        lines.append("開盤後本引擎會用當日預期波幅算出履約價。")
    else:
        # 中性賣方：短履約價設在 ±1 個預期波幅（≈1 標準差）處
        put_short = round_strike(spot - em)
        put_long = put_short - SPREAD_WIDTH
        call_short = round_strike(spot + em)
        call_long = call_short + SPREAD_WIDTH

        lines.append("🎯 今日規則輸出: Iron Condor（中性收租）")
        lines.append(f"理由: 無重大事件 + VIX{s.get('vix_label','')} + 無驗證方向優勢")
        lines.append("      → 預設中性賣方，不猜漲跌。")
        lines.append("")

        # 抓真實權利金
        credit = None
        try:
            t = yf.Ticker(und)
            oc = t.option_chain(s["expiry"])
            ps, pl = leg_mid(oc.puts, put_short), leg_mid(oc.puts, put_long)
            cs, cl = leg_mid(oc.calls, call_short), leg_mid(oc.calls, call_long)
            if None not in (ps, pl, cs, cl):
                credit = round((ps - pl) + (cs - cl), 2)
        except Exception as e:
            print(f"credit fetch err: {e}", file=sys.stderr)

        lines.append(f"賣 Put  {put_short}  /  買 Put  {put_long}")
        lines.append(f"賣 Call {call_short}  /  買 Call {call_long}")
        lines.append(f"→ 收盤落在 {put_short}~{call_short} 之間，兩邊權利金全收")
        if credit is not None and credit > 0:
            max_loss = round((SPREAD_WIDTH - credit) * 100, 0)
            lines.append(f"實際權利金≈ ${credit} /組  ·  單邊最大虧損≈ ${max_loss:.0f}")
        lines.append("約略勝率: ~68%（常態近似，非歷史回測）")

    # ── 免責 ──
    lines.append("")
    lines.append("⚠️ 這不是投資建議，是把頁面決策樹套上今天的數字。")
    lines.append("勝率為常態近似非回測；履約價/手數/是否進場請自行判斷。")
    lines.append("賣方策略負偏態＝贏小輸大，務必控制單筆最大虧損。")

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
