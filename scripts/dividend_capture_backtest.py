"""
股息套利（Dividend Capture）回測 MVP。

對每一次除息，比較幾種進出場策略的報酬：
  - hold0：除息前一天收盤買 → 除息當天收盤賣（只吃股息，最短曝險）
  - hold1 / hold3 / hold5：除息前一天收盤買 → 除息後 N 個交易日收盤賣（觀察除息後回補力道）

輸出：每檔 ETF 在每種策略下的勝率、平均單次報酬、年化次數換算後的粗略年化貢獻。
不含稅務/手續費，稅率用 --tax 參數整體打折（預設 0 = 稅前）。
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from fetch_etf_data import TICKERS_META  # noqa: E402

HOLD_DAYS = [0, 1, 3, 5, 10, 20]


def backtest_ticker(ticker: str, period: str = "1y", tax_rate: float = 0.0):
    t = yf.Ticker(ticker)
    hist = t.history(period=period, auto_adjust=False)
    divs = t.dividends

    if hist.empty or divs.empty:
        return None

    hist = hist.sort_index()
    closes = hist["Close"]
    trading_days = closes.index

    if period == "max":
        cutoff = trading_days[0]
    else:
        days = {"1y": 365, "2y": 730, "3y": 1095}[period]
        cutoff = pd.Timestamp.now(tz=trading_days.tz) - pd.Timedelta(days=days)
    divs = divs[divs.index > cutoff]

    rows = []
    for ex_date, div_amount in divs.items():
        # 找除息日當天或之後最近的交易日（除息日若非交易日，往後找）
        pos = trading_days.searchsorted(ex_date)
        if pos >= len(trading_days):
            continue
        ex_idx = pos
        buy_idx = ex_idx - 1
        if buy_idx < 0:
            continue

        buy_price = float(closes.iloc[buy_idx])
        row = {"ex_date": trading_days[ex_idx].date(), "div": float(div_amount), "buy_price": buy_price}

        for h in HOLD_DAYS:
            sell_idx = ex_idx + h
            if sell_idx >= len(trading_days):
                row[f"ret_hold{h}"] = None
                continue
            sell_price = float(closes.iloc[sell_idx])
            div_after_tax = float(div_amount) * (1 - tax_rate)
            ret = (sell_price - buy_price + div_after_tax) / buy_price
            row[f"ret_hold{h}"] = ret

        rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, ticker: str):
    out = {"ticker": ticker, "trades": len(df)}
    for h in HOLD_DAYS:
        col = f"ret_hold{h}"
        s = df[col].dropna()
        if s.empty:
            continue
        out[f"win_rate_hold{h}"] = round((s > 0).mean(), 4)
        out[f"avg_ret_hold{h}"] = round(s.mean(), 5)
        out[f"cum_ret_hold{h}"] = round((1 + s).prod() - 1, 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="*", default=None, help="預設用 fetch_etf_data.py 的清單")
    ap.add_argument("--period", default="1y", choices=["1y", "2y", "3y", "max"])
    ap.add_argument("--tax", type=float, default=0.0, help="股息預扣稅率，例如 0.15")
    args = ap.parse_args()

    tickers = args.tickers or list(TICKERS_META.keys())

    results = []
    for ticker in tickers:
        try:
            df = backtest_ticker(ticker, period=args.period, tax_rate=args.tax)
            if df is None:
                print(f"SKIP {ticker}: no data", file=sys.stderr)
                continue
            results.append(summarize(df, ticker))
            print(f"OK   {ticker:8s} {len(df)} 次除息")
        except Exception as e:
            print(f"ERR  {ticker}: {e}", file=sys.stderr)

    if not results:
        print("no results", file=sys.stderr)
        return

    out_df = pd.DataFrame(results).set_index("ticker")
    cols = ["trades"] + [c for h in HOLD_DAYS for c in (f"win_rate_hold{h}", f"avg_ret_hold{h}", f"cum_ret_hold{h}")]
    out_df = out_df[[c for c in cols if c in out_df.columns]]

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print("\n" + out_df.sort_values("cum_ret_hold0", ascending=False).to_string())

    dest = Path(__file__).parent.parent / "data" / "dividend_capture_backtest.csv"
    out_df.to_csv(dest)
    print(f"\nSaved → {dest}")


if __name__ == "__main__":
    main()
