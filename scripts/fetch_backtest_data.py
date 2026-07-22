"""Build the lightweight historical dataset used by the Sterling web backtest.

This intentionally stores underlying daily bars only. The browser labels all
results as model estimates; it does not present them as historical option fills.
"""

import json
from datetime import datetime, timezone

import yfinance as yf


SYMBOLS = ["QQQ", "SPY", "MU", "^VIX"]


def main():
    raw = yf.download(
        SYMBOLS,
        period="5y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if raw.empty:
        raise RuntimeError("No historical prices returned")

    rows = []
    for timestamp, values in raw.iterrows():
        row = {"date": timestamp.strftime("%Y-%m-%d")}
        complete = True
        for symbol in SYMBOLS:
            key = "vix" if symbol == "^VIX" else symbol.lower()
            try:
                close = float(values[("Close", symbol)])
                high = float(values[("High", symbol)])
                low = float(values[("Low", symbol)])
            except (KeyError, TypeError, ValueError):
                complete = False
                break
            if close != close or high != high or low != low:
                complete = False
                break
            row[key] = round(close, 4)
            if symbol != "^VIX":
                row[f"{key}_h"] = round(high, 4)
                row[f"{key}_l"] = round(low, 4)
        if complete:
            rows.append(row)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Yahoo Finance via yfinance; adjusted daily underlying bars",
        "symbols": ["QQQ", "SPY", "MU"],
        "rows": rows,
    }
    with open("data/backtest_underlyings.json", "w", encoding="utf-8") as file:
        json.dump(output, file, separators=(",", ":"))
    print(f"Saved {len(rows)} rows to data/backtest_underlyings.json")


if __name__ == "__main__":
    main()
