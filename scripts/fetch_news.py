#!/usr/bin/env python3
"""Fetch market news from Google News RSS and update data/news.json"""

import feedparser
import json
import os
import sys
import html
import time as time_module
from datetime import datetime, timedelta
from urllib.parse import quote
import pytz

HK_TZ = pytz.timezone('Asia/Hong_Kong')
NY_TZ = pytz.timezone('America/New_York')

TICKER_MAP = {
    'NVDA':    ['NVIDIA', '輝達', '英偉達'],
    'AAPL':    ['蘋果', 'Apple', 'iPhone'],
    'TSLA':    ['特斯拉', 'Tesla'],
    'MU':      ['美光', 'Micron'],
    'TSM':     ['台積電', 'TSMC'],
    'AMZN':    ['亞馬遜', 'Amazon'],
    'MSFT':    ['微軟', 'Microsoft'],
    'GOOGL':   ['谷歌', 'Google', 'Alphabet'],
    'META':    ['Meta', '臉書', 'Facebook'],
    'PLTR':    ['Palantir', '鈀蘭提爾'],
    '^HSI':    ['恒生', '恒指', 'HSI'],
    '^TWII':   ['加權指數', 'TAIEX'],
    '^N225':   ['日經', 'Nikkei', 'N225'],
    'SPY':     ['標普', 'S&P 500', 'S&P500'],
    'QQQ':     ['納指', 'Nasdaq', '那斯達克'],
    '0700.HK': ['騰訊', 'Tencent'],
    '9988.HK': ['阿里巴巴', 'Alibaba'],
    'BTC':     ['比特幣', 'Bitcoin'],
    'ETH':     ['以太坊', 'Ethereum'],
    'BNB':     ['幣安', 'BNB'],
}


def extract_tickers(text):
    found = []
    for ticker, keywords in TICKER_MAP.items():
        for kw in keywords:
            if kw in text and ticker not in found:
                found.append(ticker)
                break
    return found


def build_queries(now_hk):
    """Build time-aware queries. On weekends, look back to Friday's news."""
    weekday = now_hk.weekday()  # 0=Mon ... 6=Sun

    if weekday == 5:   # Saturday → look back 1 day (Friday)
        days_back = 1
    elif weekday == 6:  # Sunday → look back 2 days (Friday)
        days_back = 2
    else:
        days_back = 1   # Weekday → yesterday + today

    cutoff = (now_hk - timedelta(days=days_back)).strftime('%Y-%m-%d')
    df = f"after:{cutoff}"   # Google News date filter

    return {
        'us':     f'美股 市場 {df}',
        'hk':     f'港股 恒生指數 {df}',
        'tw':     f'台股 加權指數 {df}',
        'jp':     f'日股 日經225 {df}',
        'crypto': f'比特幣 以太坊 加密貨幣 {df}',
    }, days_back * 24 + 12   # max_age_hours


def is_recent(entry, max_hours):
    """True if the entry was published within the last max_hours hours."""
    published = entry.get('published_parsed')
    if not published:
        return True   # include if no date info
    pub_dt = datetime(*published[:6], tzinfo=pytz.utc)
    cutoff = datetime.now(pytz.utc) - timedelta(hours=max_hours)
    return pub_dt >= cutoff


def fetch_google_news(query, limit=3, max_hours=36):
    url = (
        f"https://news.google.com/rss/search"
        f"?q={quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; InvestUni/1.0)'}
    try:
        feed = feedparser.parse(url, request_headers=headers)

        # Sort by newest first
        sorted_entries = sorted(
            feed.entries,
            key=lambda e: e.get('published_parsed') or time_module.gmtime(0),
            reverse=True,
        )

        # Filter to only recent articles
        recent = [e for e in sorted_entries if is_recent(e, max_hours)]

        if not recent:
            print(f"  [WARN] No recent articles (max_hours={max_hours}) — using all", file=sys.stderr)
            recent = sorted_entries   # fallback: use whatever we got

        items = []
        for entry in recent[:limit]:
            title = html.unescape(entry.get('title', ''))
            link = entry.get('link', '')
            source = ''
            if hasattr(entry, 'source') and isinstance(entry.source, dict):
                source = entry.source.get('title', '')
            pub = ''
            if entry.get('published_parsed'):
                dt = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
                pub = dt.astimezone(HK_TZ).strftime('%m/%d %H:%M')

            items.append({
                'title': title,
                'url': link,
                'source': source,
                'published_hkt': pub,
                'related': extract_tickers(title),
            })
        return items

    except Exception as e:
        print(f"[WARN] Failed to fetch '{query}': {e}", file=sys.stderr)
        return []


def get_section(market, now_utc):
    """
    盤前 = 30-45 min window before market opens
    盤後 = after all sessions (including 夜盤) end
    Returns 'pre_market', 'post_market', 'all', or None (skip)
    """
    if market == 'crypto':
        return 'all'

    now_hk = now_utc.astimezone(HK_TZ)
    hk_t = now_hk.hour * 60 + now_hk.minute

    if market == 'us':
        now_ny = now_utc.astimezone(NY_TZ)
        ny_t = now_ny.hour * 60 + now_ny.minute
        if 8 * 60 + 45 <= ny_t < 9 * 60 + 30:
            return 'pre_market'
        if ny_t >= 20 * 60 or (7 * 60 <= hk_t <= 13 * 60):
            return 'post_market'
        return None

    elif market == 'hk':
        if 8 * 60 + 45 <= hk_t < 9 * 60 + 30:
            return 'pre_market'
        if hk_t >= 16 * 60 + 30:
            return 'post_market'
        return None

    elif market == 'tw':
        if 8 * 60 + 30 <= hk_t < 9 * 60:
            return 'pre_market'
        if hk_t >= 14 * 60:
            return 'post_market'
        return None

    elif market == 'jp':
        if 7 * 60 + 30 <= hk_t < 8 * 60 + 15:
            return 'pre_market'
        if hk_t >= 15 * 60:
            return 'post_market'
        return None

    return None


def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ensure_structure(data):
    template = {'updated_at': None, 'news': []}
    for m in ['us', 'hk', 'tw', 'jp']:
        data.setdefault(m, {})
        data[m].setdefault('pre_market', dict(template))
        data[m].setdefault('post_market', dict(template))
    data.setdefault('crypto', {'updated_at': None, 'news': []})
    return data


def main():
    now_utc = datetime.now(pytz.utc)
    now_hk  = now_utc.astimezone(HK_TZ)
    now_str = now_hk.strftime('%Y-%m-%d %H:%M HKT')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path  = os.path.normpath(os.path.join(script_dir, '..', 'data', 'news.json'))

    data = ensure_structure(load_json(data_path))

    queries, max_hours = build_queries(now_hk)
    print(f"Time: {now_str} | max_age: {max_hours}h")

    for market, query in queries.items():
        section = get_section(market, now_utc)
        if section is None:
            print(f"  [{market}] Not in update window — skip")
            continue

        print(f"  [{market}] Fetching ({section})  query: {query[:60]}...")
        news = fetch_google_news(query, limit=3, max_hours=max_hours)
        if not news:
            print(f"  [{market}] No results")
            continue

        if market == 'crypto':
            data['crypto'] = {'updated_at': now_str, 'news': news}
        else:
            data[market][section] = {'updated_at': now_str, 'news': news}
        print(f"  [{market}] ✓ {len(news)} articles")

    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {data_path}")


if __name__ == '__main__':
    main()
