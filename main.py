# btc-cent-forecast-01 entry: shrunk short-window drift forecaster.
#
# Method: take the last price and extrapolate the mean log-return of the
# last 60 minutes, shrunk toward zero (factor 0.20) over the 240-minute
# horizon:
#     guess = last * exp(0.20 * mean_log_return_60min * 240)
# Backtested on the kit's practice cases p00..p04 (actual = next case's
# last price): MAE 32,450.9 cents vs persistence baseline 47,054.7 cents
# (31.0% lower). The 0.15-0.30 shrink range is a plateau (32.4k-35.2k),
# so 0.20 sits in the middle of it, not on a point optimum. See
# BACKTEST.md for the full candidate table.
#
# Deterministic: Python 3.13 stdlib only, no network, no clock/time
# calls, no randomness. Two runs on the same case write identical bytes.

import json
import math
import os
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999
WINDOW_MINUTES = 60
HORIZON_MINUTES = 240
SHRINK = 0.20


def price5(x):
    """Clamp into (0, 10,000,000) and round to the grid's 5 decimals."""
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def forecast(prices):
    """One price: last close extrapolated by shrunk 60-minute drift."""
    if not prices:
        raise ValueError("market has no prices")
    last = prices[-1]
    if not isinstance(last, (int, float)) or not math.isfinite(last):
        raise ValueError("last price is not a finite number")
    if last <= 0:
        raise ValueError("last price is not positive")
    n = min(WINDOW_MINUTES, len(prices) - 1)
    if n < 1:
        # Degenerate one-price series: nothing to extrapolate from.
        return price5(last)
    # Mean log-return per minute over the last n minutes.
    total = 0.0
    for i in range(len(prices) - n, len(prices)):
        p_prev = prices[i - 1]
        p_cur = prices[i]
        if p_prev <= 0 or p_cur <= 0:
            raise ValueError("non-positive price in series")
        total += math.log(p_cur / p_prev)
    mean_return = total / n
    guess = math.exp(math.log(last) + SHRINK * mean_return * HORIZON_MINUTES)
    if not math.isfinite(guess):
        return price5(last)
    return price5(guess)


def main():
    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in in_dir.iterdir() if p.name.endswith(".in"))
    for name in names:
        case_id = name[: -len(".in")]
        with open(in_dir / name, "r", encoding="utf-8") as f:
            case = json.load(f)
        markets = case.get("markets")
        if not isinstance(markets, list) or len(markets) != 1:
            raise ValueError(f"{name} does not hold exactly one market")
        prices = markets[0].get("prices")
        if not isinstance(prices, list) or not prices:
            raise ValueError(f"{name} has no prices")
        guess = forecast(prices)
        out = json.dumps({"forecasts": [{"case": case_id, "price": guess}]}) + "\n"
        with open(out_dir / f"{case_id}.out", "w", encoding="utf-8") as f:
            f.write(out)


if __name__ == "__main__":
    main()
