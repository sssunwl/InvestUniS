import yfinance as yf
import json
import sys
import pandas as pd
from pathlib import Path

TICKERS_META = {
    "NVDY":    {"name":"YieldMax NVDA 期權收益 ETF",       "name_en":"YieldMax NVDA Option Income",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "TSLY":    {"name":"YieldMax TSLA 期權收益 ETF",       "name_en":"YieldMax TSLA Option Income",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "MSFO":    {"name":"YieldMax MSFT 期權收益 ETF",       "name_en":"YieldMax MSFT Option Income",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "CONY":    {"name":"YieldMax COIN 期權收益 ETF",       "name_en":"YieldMax COIN Option Income",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "PLTY":    {"name":"YieldMax PLTR 期權收益 ETF",       "name_en":"YieldMax PLTR Option Income",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "MSTY":    {"name":"YieldMax MSTR 期權收益 ETF",       "name_en":"YieldMax MSTR Option Income",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "YMAX":    {"name":"YieldMax 全系列組合 ETF",          "name_en":"YieldMax Universe Fund",                  "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "YMAG":    {"name":"YieldMax Mag7 組合 ETF",           "name_en":"YieldMax Magnificent 7 Fund",             "market":"US","currency":"USD","series":"YieldMax","tax_note":"ROC，通常豁免預扣稅"},
    "FEPI":    {"name":"REX FANG 創新期權收益 ETF",        "name_en":"REX FANG & Innovation Income ETF",        "market":"US","currency":"USD","series":"REX",      "tax_note":"ROC/普通收入混合，部分需扣"},
    "QDTE":    {"name":"Roundhill S&P500 零日到期收益 ETF","name_en":"Roundhill S&P 500 Zero Days to Expiry",   "market":"US","currency":"USD","series":"Roundhill","tax_note":"1256 合約收益，部分需扣"},
    "XDTE":    {"name":"Roundhill S&P500 週度期權收益 ETF","name_en":"Roundhill S&P 500 Weekly Options",        "market":"US","currency":"USD","series":"Roundhill","tax_note":"1256 合約收益，部分需扣"},
    "JEPI":    {"name":"JPMorgan 股票溢價收益 ETF",        "name_en":"JPMorgan Equity Premium Income",          "market":"US","currency":"USD","series":"JPMorgan", "tax_note":"ELN 結構，部分需扣"},
    "JEPQ":    {"name":"JPMorgan 納斯達克溢價收益 ETF",    "name_en":"JPMorgan Nasdaq Equity Premium Income",   "market":"US","currency":"USD","series":"JPMorgan", "tax_note":"ELN 結構，部分需扣"},
    "SPYI":    {"name":"NEOS S&P500 高收益 ETF",           "name_en":"NEOS S&P 500 High Income ETF",            "market":"US","currency":"USD","series":"NEOS",     "tax_note":"1256 合約，較優惠稅務待遇"},
    "QQQI":    {"name":"NEOS 納斯達克100 高收益 ETF",      "name_en":"NEOS Nasdaq-100 High Income ETF",         "market":"US","currency":"USD","series":"NEOS",     "tax_note":"1256 合約，較優惠稅務待遇"},
    "3416.HK": {"name":"CSOP 恆生科技每週派息 ETF",        "name_en":"CSOP HS Tech Weekly Distribution ETF",   "market":"HK","currency":"HKD","series":"CSOP",     "tax_note":"港股 ETF，不適用美國預扣稅"},
}

def detect_freq(divs):
    if len(divs) < 2:
        return "monthly", "月息", 12
    idx = divs.index.sort_values()
    # If the last 2 gaps are both ≤10 days, the ETF recently switched to weekly
    if len(idx) >= 3:
        last2 = [(idx[-(i)] - idx[-(i+1)]).days for i in range(1, 3)]
        if all(g <= 10 for g in last2):
            return "weekly", "週息", 52
    # Fall back to full-year average
    all_gaps = [(idx[i] - idx[i-1]).days for i in range(1, len(idx))]
    avg = sum(all_gaps) / len(all_gaps)
    if avg <= 10:
        return "weekly", "週息", 52
    elif avg <= 45:
        return "monthly", "月息", 12
    else:
        return "quarterly", "季息", 4

def main():
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=365)
    out = {
        "updated": pd.Timestamp.now(tz="Asia/Hong_Kong").strftime("%Y-%m-%d %H:%M HKT"),
        "tickers": {}
    }

    for ticker, meta in TICKERS_META.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            divs = t.dividends

            if hist.empty:
                print(f"SKIP {ticker}: no price data", file=sys.stderr)
                continue

            price = round(float(hist["Close"].iloc[-1]), 4)
            price_1y_ago = round(float(hist["Close"].iloc[0]), 4)
            price_chg_1y = round((price - price_1y_ago) / price_1y_ago, 4)

            if not divs.empty:
                tz = divs.index.tz
                cutoff_local = cutoff.tz_convert(tz) if tz else cutoff.tz_localize(None)
                divs_1y = divs[divs.index > cutoff_local]
                count_1y = len(divs_1y)
                recent_div = round(float(divs.iloc[-1]), 6)
                total_div_1y = round(float(divs_1y.sum()), 4)
                annual_yield = round(total_div_1y / price, 4) if price > 0 else 0
                freq, freq_cn, divs_per_year = detect_freq(divs)
            else:
                count_1y = 0; recent_div = 0; total_div_1y = 0; annual_yield = 0
                freq, freq_cn, divs_per_year = "unknown", "未知", 0

            net_1y = round(price_chg_1y + annual_yield, 4)
            health = "green" if net_1y > 0.05 else ("yellow" if net_1y >= -0.05 else "red")

            out["tickers"][ticker] = {
                **meta,
                "price": price,
                "price_1y_ago": price_1y_ago,
                "price_chg_1y": price_chg_1y,
                "freq": freq,
                "freq_cn": freq_cn,
                "divs_per_year": divs_per_year,
                "recent_div": recent_div,
                "total_div_1y": total_div_1y,
                "annual_yield": annual_yield,
                "net_1y": net_1y,
                "health": health,
            }
            print(f"OK  {ticker:8s} ${price:7.3f} | {freq_cn} | yield {annual_yield*100:.1f}% | 1y {price_chg_1y*100:+.1f}% | net {net_1y*100:+.1f}% | {health}")
        except Exception as e:
            print(f"ERR {ticker}: {e}", file=sys.stderr)

    dest = Path(__file__).parent.parent / "data" / "etf_data.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nSaved {len(out['tickers'])} tickers → {dest}")

if __name__ == "__main__":
    main()
