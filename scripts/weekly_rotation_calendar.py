"""
週息ETF輪動日曆：預測未來7天各檔ETF的除息日，並附上歷史 hold1（除息前一天收盤買、
隔天收盤賣）勝率與平均報酬，方便決定「這週三買誰、週四買誰」。

除息週期抓最近6次的間隔天數取中位數來預測下一次，比單純 +7 天更抗雜訊
（部分ETF偶爾因假日順延1天）。
"""
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from dividend_capture_backtest import backtest_ticker  # noqa: E402

WEEKLY_TICKERS = ["FEPI", "NVDY", "TSLY", "MSFO", "CONY", "PLTY", "MSTY", "YMAX", "YMAG", "QDTE", "XDTE"]


def predict_next_ex_date(divs: pd.Series) -> pd.Timestamp:
    recent = divs.index[-6:]
    if len(recent) < 2:
        median_gap = 7
    else:
        gaps = [(recent[i] - recent[i - 1]).days for i in range(1, len(recent))]
        gaps.sort()
        median_gap = gaps[len(gaps) // 2]

    today = pd.Timestamp.now(tz=recent[-1].tz).normalize()
    next_ex = recent[-1]
    while next_ex <= today:
        next_ex = next_ex + pd.Timedelta(days=median_gap)
    return next_ex


def main():
    rows = []
    for ticker in WEEKLY_TICKERS:
        try:
            divs = yf.Ticker(ticker).dividends
            if divs.empty:
                continue
            next_ex = predict_next_ex_date(divs)

            bt = backtest_ticker(ticker, period="1y", tax_rate=0.15)
            if bt is not None and len(bt) >= 4:
                recent8 = bt.tail(8)  # 近期表現比全年平均更有參考性（規律會變）
                win1 = round((recent8["ret_hold1"].dropna() > 0).mean(), 2)
                avg1 = round(recent8["ret_hold1"].dropna().mean(), 4)
            else:
                win1, avg1 = None, None

            rows.append({
                "ticker": ticker,
                "next_ex_date": next_ex.date(),
                "weekday": next_ex.day_name(),
                "recent8_win_rate_hold1": win1,
                "recent8_avg_ret_hold1": avg1,
                "last_div": round(float(divs.iloc[-1]), 4),
            })
        except Exception as e:
            print(f"ERR {ticker}: {e}", file=sys.stderr)

    df = pd.DataFrame(rows).sort_values(["next_ex_date", "ticker"])
    pd.set_option("display.width", 160)
    print(df.to_string(index=False))
    print("\n提醒：recent8 是近8次操作的統計，樣本仍偏小，僅供參考，不是保證。")
    print("hold1 = 除息前一天收盤買 → 除息隔天收盤賣（含 15% 預扣稅估算）。")


if __name__ == "__main__":
    main()
