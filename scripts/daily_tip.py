#!/usr/bin/env python3
"""
Send 4 daily TG investment digests:
  00:00 UTC (08:00 HKT) — 美股夜盤後總結 + 加密市場
  01:00 UTC (09:00 HKT) — 亞洲盤前合集（港/台/日）
  09:00 UTC (17:00 HKT) — 亞洲盤後合集（港/台/日）
  13:30 UTC (21:30 HKT) — 美股盤前預覽 + 加密市場
"""

import html as _html
import json
import os
import sys
import requests
from datetime import datetime, timedelta
import pytz


def esc(text):
    """Escape HTML special chars for Telegram HTML mode."""
    return _html.escape(str(text or ''), quote=False)

BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
CHAT_ID = os.environ.get('TG_CHAT_ID', '')
ACADEMY_URL = 'https://sssunwl.github.io/InvestUni'

HK_TZ = pytz.timezone('Asia/Hong_Kong')

# ── 2026 市場休市日曆 ──────────────────────────────────────────
# 標注 (暫定) 的日期依農曆推算，可能有1-2日誤差
MARKET_HOLIDAYS = {
    'us': {
        '2026-06-19': 'Juneteenth',
        '2026-07-03': '獨立日（7/4週六提前）',
        '2026-09-07': '勞工節 Labor Day',
        '2026-11-26': '感恩節 Thanksgiving',
        '2026-12-25': '聖誕節 Christmas',
    },
    'hk': {
        '2026-06-19': '端午節（暫定）',
        '2026-07-01': '香港回歸紀念日',
        '2026-10-01': '中秋節翌日（暫定）',
        '2026-10-02': '國慶日',
        '2026-10-19': '重陽節（暫定）',
        '2026-12-25': '聖誕節',
        '2026-12-26': '聖誕節翌日',
    },
    'tw': {
        '2026-06-19': '端午節（暫定）',
        '2026-10-09': '國慶補假（暫定）',
        '2026-10-10': '國慶日（雙十節）',
    },
    'jp': {
        '2026-07-20': '海の日',
        '2026-08-11': '山の日',
        '2026-09-21': '敬老の日（暫定）',
        '2026-09-23': '秋分の日（暫定）',
        '2026-10-12': 'スポーツの日',
        '2026-11-03': '文化の日',
        '2026-11-23': '勤労感謝の日',
        '2026-12-30': '年末最終取引日',
    },
}

MARKET_LABELS = {
    'us': '🇺🇸 美股',
    'hk': '🇭🇰 港股',
    'tw': '🇹🇼 台股',
    'jp': '🇯🇵 日股',
}


def get_upcoming_holidays(now_hk, days=7):
    """Return list of formatted strings for holidays in the next `days` days."""
    alerts = []
    for i in range(days):
        date_str = (now_hk + timedelta(days=i)).strftime('%Y-%m-%d')
        weekday_str = (now_hk + timedelta(days=i)).strftime('%a')
        for market, holidays in MARKET_HOLIDAYS.items():
            if date_str in holidays:
                name = holidays[date_str]
                label = MARKET_LABELS[market]
                alerts.append(f"  {date_str}（{weekday_str}）{label} — {name}")
    return alerts

TIPS = [
    ("📊 成交量 — 放量上漲",
     "成交量大幅增加同時價格上漲，代表多方主力積極入場。\n最健康的買入型態，趨勢可持續性強，跟進比追高更安全。"),
    ("📊 成交量 — 縮量上漲",
     "漲勢靠慣性維持，新的買盤沒有進場。\n動能正在悄悄流失，持倉者考慮部分止盈，不宜追入。"),
    ("📊 成交量 — 放量下跌",
     "成交量爆增同時價格急跌，空方主力大量出貨。\n是空方力量最明確的表現，此時抄底是最常見的散戶陷阱。"),
    ("📊 成交量 — 高位縮量",
     "股票在高位運行時成交量萎縮，主力悄悄退場。\n散戶接盤能力不足，反轉風險急劇上升，應考慮逐步減倉。"),
    ("📊 成交量 — 量價背離",
     "價格創新高但成交量反而下降——量與價走向相反。\n重要反轉前兆，多方背離時減倉是正確的選擇。"),
    ("📊 成交量 — 異常成交量",
     "成交量突然爆增至平日數倍，通常與重大消息掛鉤。\n先觀察方向確認，再決定操作。耐心等待比衝動更值錢。"),
    ("📊 成交量 — 溫和放量",
     "成交量平穩有節奏地小幅增加，最健康的上漲型態。\n市場充分消化籌碼，趨勢可持續性最強，教科書式的買點。"),
    ("📊 成交量 — 成交量極端",
     "成交量達歷史極端水平，極高可能代表主力出貨完成。\n極低量代表大行情蓄勢待發，注意突破方向。"),
    ("🕯 K線 — 錘子線",
     "下影線很長（≥實體2倍），出現在下跌趨勢末端。\n代表空方打壓後被多方強力反攻，是底部反轉的強力信號。"),
    ("🕯 K線 — 射擊之星",
     "上影線很長，出現在上漲趨勢高位。\n代表多方衝高後遭空方強力壓制，是頂部反轉的經典信號。"),
    ("🕯 K線 — 十字星",
     "開盤與收盤幾乎相同，多空雙方勢力相當。\n本身不構成操作信號，等待下一根K線確認方向後再行動。"),
    ("🕯 K線 — 晨星形態",
     "三根K線組合：大陰線 → 跳空小實體 → 大陽線收復。\n出現在下跌趨勢底部，是強力的底部反轉信號。"),
    ("🕯 K線 — 吞噬形態",
     "大陽線完全吞噬前一根陰線，多方力量壓倒性勝出。\n吞噬的實體越大信號越強，吞噬當天或次日可考慮建倉。"),
    ("⚡ 期權 — Call vs Put",
     "Call（看漲）= 賭正股上漲的彩券，最大損失僅限保費。\nPut（看跌）= 保護資產的保險單，大盤崩盤時的最佳對沖工具。"),
    ("⚡ 期權 — Theta 時間小偷",
     "每過一天，期權的時間溢價就自動融化一部分。\nTheta 對期權買方是敵人，對期權賣方是朋友。"),
    ("⚡ 期權 — IV Crush 陷阱",
     "財報前IV被炒高，財報出來後IV瞬間暴跌。\n即使股票真的大漲，保費蒸發的損失可能超過獲利——你賭對了方向還是虧錢。"),
    ("⚡ 期權 — Bull Call Spread",
     "同時買入低履約價Call + 賣出高履約價Call。\n最大風險固定，賣出的Call補貼保費，抗Theta流逝能力遠高於單腿買Call。"),
    ("⚡ 期權 — Long Straddle",
     "同時買入相同履約價的Call + Put，不賭方向，只賭大地震。\n大盤原地不動會雙殺，走出單邊行情回報可達100-160%+。"),
    ("📖 名詞 — 中間價 Mid Price",
     "永遠用限價單以Bid與Ask的中間價建倉，拒絕市價單。\n市價單 = 讓做市商決定你的成交價，等於主動送錢給對方。"),
    ("📖 名詞 — GTC 條件單",
     "Good 'Til Cancelled——掛單後在雲端保持有效長達90天。\n建倉後立刻掛GTC止盈，交給自動化全天候執行，安心生活。"),
    ("📖 名詞 — VWAP",
     "成交量加權平均價，機構投資者評估交易成本的基準線。\n股價在VWAP上方 = 短線強勢；跌破VWAP = 短線偏弱。"),
    ("📖 名詞 — Opening Range",
     "開盤後前15-30分鐘形成的最高價與最低價區間。\n突破OR高點 = 看漲；跌破OR低點 = 看跌。當日多空第一場博弈。"),
    ("💡 風險管理 — 位置大小",
     "手數×10 = 最大虧損×10 = 心理壓力×10 = 決策崩潰風險×10。\n實驗期嚴格1-2手，買到睡得著才是最重要的事。"),
    ("💡 風險管理 — 拒絕高頻",
     "每次交易都有Bid-Ask Spread與手續費摩擦損耗。\n高頻進出讓券商和做市商持續抽水，利潤被慢性吃掉。"),
    ("💡 風險管理 — 操盤SOP",
     "① 等開盤5-10分鐘 → ② 中間價建倉 → ③ 退出畫面\n→ ④ 掛GTC止盈單 → ⑤ 關閉軟體，安心享受生活。"),
]


def load_news():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(script_dir, '..', 'data', 'news.json'))
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def get_tip(now_hk, offset=0):
    idx = (now_hk.timetuple().tm_yday * 2 + offset) % len(TIPS)
    title, body = TIPS[idx]
    return f"<b>{title}</b>\n{body}"


def news_block(items, limit=3):
    if not items:
        return '  暫無資料\n'
    lines = []
    for item in items[:limit]:
        title = esc((item.get('title') or '')[:70])
        url   = esc(item.get('url') or '')
        tickers = ' '.join(f"#{esc(t)}" for t in (item.get('related') or [])[:2])
        src   = esc(item.get('source') or '')
        pub   = esc(item.get('published_hkt') or '')
        line = f'  • <a href="{url}">{title}</a>'
        if tickers:
            line += f'  {tickers}'
        meta = ' | '.join(filter(None, [pub, src]))
        if meta:
            line += f'\n    <i>{meta}</i>'
        lines.append(line)
    return '\n'.join(lines) + '\n'


def holiday_block(now_hk):
    """Return formatted holiday reminder block if any holidays in next 7 days."""
    alerts = get_upcoming_holidays(now_hk, days=7)
    if not alerts:
        return ''
    lines = '\n'.join(alerts)
    return f"\n⛔ <b>7日內休市提醒</b>\n{lines}\n"


def build_us_post(data, now_hk):
    """08:00 HKT — 美股夜盤後總結 + 加密市場"""
    tip = get_tip(now_hk, offset=0)
    us_post = data.get('us', {}).get('post_market', {}).get('news', [])
    crypto  = data.get('crypto', {}).get('news', [])
    return (
        f"🌅 <b>美股夜盤後總結 + 加密市場</b>\n"
        f"📅 {now_hk.strftime('%Y年%m月%d日')}　08:00 HKT\n\n"
        f"🇺🇸 <b>美股夜盤精選</b>\n"
        f"{news_block(us_post)}\n"
        f"🌐 <b>加密貨幣最新走勢</b>\n"
        f"{news_block(crypto, limit=2)}"
        f"{holiday_block(now_hk)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 {tip}\n\n"
        f"📚 <a href=\"{ACADEMY_URL}\">Suniverse 投資學堂</a>"
    )


def build_asia_pre(data, now_hk):
    """09:00 HKT — 亞洲盤前合集"""
    tip = get_tip(now_hk, offset=0)
    hk_pre = data.get('hk', {}).get('pre_market', {}).get('news', [])
    tw_pre = data.get('tw', {}).get('pre_market', {}).get('news', [])
    jp_pre = data.get('jp', {}).get('pre_market', {}).get('news', [])
    return (
        f"🌏 <b>亞洲股市盤前精選</b>\n"
        f"📅 {now_hk.strftime('%Y年%m月%d日')}　09:00 HKT\n\n"
        f"🇭🇰 <b>港股盤前</b>\n"
        f"{news_block(hk_pre, limit=2)}\n"
        f"🇹🇼 <b>台股盤前</b>\n"
        f"{news_block(tw_pre, limit=2)}\n"
        f"🇯🇵 <b>日股盤前</b>\n"
        f"{news_block(jp_pre, limit=2)}"
        f"{holiday_block(now_hk)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 {tip}\n\n"
        f"📚 <a href=\"{ACADEMY_URL}\">Suniverse 投資學堂</a>"
    )


def build_asia_post(data, now_hk):
    """17:00 HKT — 亞洲盤後合集"""
    tip = get_tip(now_hk, offset=1)
    hk_post = data.get('hk', {}).get('post_market', {}).get('news', [])
    tw_post = data.get('tw', {}).get('post_market', {}).get('news', [])
    jp_post = data.get('jp', {}).get('post_market', {}).get('news', [])
    return (
        f"🌇 <b>亞洲股市收市總結</b>\n"
        f"📅 {now_hk.strftime('%Y年%m月%d日')}　17:00 HKT\n\n"
        f"🇭🇰 <b>港股收市總結</b>\n"
        f"{news_block(hk_post, limit=2)}\n"
        f"🇹🇼 <b>台股收市總結</b>\n"
        f"{news_block(tw_post, limit=2)}\n"
        f"🇯🇵 <b>日股收市總結</b>\n"
        f"{news_block(jp_post, limit=2)}"
        f"{holiday_block(now_hk)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 {tip}\n\n"
        f"📚 <a href=\"{ACADEMY_URL}\">Suniverse 投資學堂</a>"
    )


def build_us_pre(data, now_hk):
    """21:30 HKT — 美股盤前預覽 + 加密市場"""
    tip = get_tip(now_hk, offset=1)
    us_pre = data.get('us', {}).get('pre_market', {}).get('news', [])
    crypto  = data.get('crypto', {}).get('news', [])
    return (
        f"🌃 <b>美股即將開市 + 加密市場</b>\n"
        f"📅 {now_hk.strftime('%Y年%m月%d日')}　21:30 HKT\n\n"
        f"🇺🇸 <b>美股盤前精選</b>\n"
        f"{news_block(us_pre)}\n"
        f"🌐 <b>加密貨幣最新走勢</b>\n"
        f"{news_block(crypto, limit=2)}"
        f"{holiday_block(now_hk)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 {tip}\n\n"
        f"📚 <a href=\"{ACADEMY_URL}\">Suniverse 投資學堂</a>"
    )


def send_tg(text):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(api_url, json={
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False,
    }, timeout=20)
    if not r.ok:
        print(f"TG {r.status_code}: {r.text}", file=sys.stderr)
    r.raise_for_status()
    return r.json()


def main():
    if not BOT_TOKEN:
        print("ERROR: TG_BOT_TOKEN not set", file=sys.stderr); sys.exit(1)
    if not CHAT_ID:
        print("ERROR: TG_CHAT_ID not set", file=sys.stderr); sys.exit(1)

    now_utc = datetime.now(pytz.utc)
    now_hk  = now_utc.astimezone(HK_TZ)
    utc_h   = now_utc.hour

    data = load_news()

    # 優先依 workflow 傳入的 MSG_TYPE 派發（由觸發的 cron 表達式決定，
    # 不受 GitHub Actions 排程延遲影響；UTC 小時僅作手動觸發時的備援猜測）
    type_map = {
        'us_post':   (build_us_post,   '美股夜盤後總結'),
        'asia_pre':  (build_asia_pre,  '亞洲盤前'),
        'asia_post': (build_asia_post, '亞洲盤後'),
        'us_pre':    (build_us_pre,    '美股盤前預覽'),
    }
    msg_type = os.environ.get('MSG_TYPE', '')

    if msg_type in type_map:
        builder, label = type_map[msg_type]
        msg = builder(data, now_hk)
    elif utc_h == 0:
        msg, label = build_us_post(data, now_hk), '美股夜盤後總結（備援）'
    elif utc_h == 1:
        msg, label = build_asia_pre(data, now_hk), '亞洲盤前（備援）'
    elif utc_h == 9:
        msg, label = build_asia_post(data, now_hk), '亞洲盤後（備援）'
    elif utc_h in (13, 14):
        msg, label = build_us_pre(data, now_hk), '美股盤前預覽（備援）'
    else:
        msg, label = build_us_pre(data, now_hk), '美股盤前預覽（手動）'

    print(f"Sending: {label}...")
    result = send_tg(msg)
    if result.get('ok'):
        print("Done!")
    else:
        print(f"Failed: {result}", file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
