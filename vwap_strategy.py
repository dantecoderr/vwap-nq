"""
VWAP trend strategy on NQ futures (1-minute bars) — backtest.

Two rule sets:
  paper  : Zarattini & Aziz, "VWAP: The Holy Grail for Day Trading Systems" — from 09:31, every minute,
           long if close > VWAP, short if close < VWAP, flip on every cross, flat at the close.
  buffer : our version — from 10:00, every 5 minutes, long only if close > VWAP*(1+buf),
           short only if close < VWAP*(1-buf), otherwise hold; buf = 0.15 x std of the previous
           14 daily returns; no trading on FOMC decision days; flat at the close.

P&L is in NQ points per contract (1 NQ = $20/pt, 1 MNQ = $2/pt), net of COST points per round trip.

Usage:
  python vwap_strategy.py --data path/to/csv_folder --rules buffer --cost 1.0
Data: Databento NQ continuous front month (e.g. NQ.v.0) 1-min OHLCV CSVs with columns
      ts_event, open, high, low, close, volume.
"""
import argparse
import glob

import numpy as np
import pandas as pd

from fomc_dates import FOMC_DATES

FOMC = set(pd.to_datetime(FOMC_DATES).date)
OPEN, CLOSE = 9 * 60 + 30, 16 * 60
RULES = {
    "paper":  dict(buffer_k=0.0,  start=9 * 60 + 31, step=1, skip_fomc=False),
    "buffer": dict(buffer_k=0.15, start=10 * 60,     step=5, skip_fomc=True),
}


def load_data(folder):
    """Regular-session 1-min bars from every CSV in `folder`, indexed by New York time."""
    parts = []
    for f in sorted(glob.glob(f"{folder}/*.csv")):
        df = pd.read_csv(f, usecols=["ts_event", "open", "high", "low", "close", "volume"])
        df.index = pd.to_datetime(df.pop("ts_event"), utc=True).dt.tz_convert("America/New_York")
        parts.append(df)
    df = pd.concat(parts).sort_index()
    df = df[~df.index.duplicated()]
    minute = df.index.hour * 60 + df.index.minute
    df = df[(minute >= OPEN) & (minute < CLOSE)].copy()
    df["date"] = df.index.date
    df["minute"] = df.index.hour * 60 + df.index.minute
    return add_indicators(df)


def add_indicators(df):
    """Session VWAP (anchored 09:30) and the previous 14 days' volatility of daily returns."""
    typical = (df.high + df.low + df.close) / 3
    df["vwap"] = (typical * df.volume).groupby(df.date).cumsum() / df.volume.groupby(df.date).cumsum()
    daily_close = df.groupby("date").close.last()
    df["vol14"] = df.date.map(daily_close.pct_change().shift(1).rolling(14).std())   # shift(1): no look-ahead
    return df


def backtest(df, rules="buffer", cost=1.0, min_bars=350):
    """Return one row per trade."""
    p = RULES[rules]
    trades = []
    for date, day in df.groupby("date"):
        if len(day) < min_bars or (p["skip_fomc"] and date in FOMC):
            continue
        vol = day.vol14.iloc[0]
        if p["buffer_k"] > 0 and np.isnan(vol):
            continue
        buf = p["buffer_k"] * vol if p["buffer_k"] > 0 else 0.0
        c, v, m, t = day.close.values, day.vwap.values, day.minute.values, day.index

        pos, entry_px, entry_t = 0, 0.0, None
        for i in range(len(c)):
            new = pos
            if i == len(c) - 1:
                new = 0                                                   # flat at the close
            elif m[i] >= p["start"] and (m[i] - OPEN) % p["step"] == 0:
                if c[i] > v[i] * (1 + buf):
                    new = 1
                elif c[i] < v[i] * (1 - buf):
                    new = -1
            if new != pos:
                if pos != 0:
                    trades.append(dict(date=date, year=date.year, side="long" if pos == 1 else "short",
                                       entry_time=entry_t, exit_time=t[i], entry=entry_px, exit=c[i],
                                       pnl=pos * (c[i] - entry_px) - cost))
                if new != 0:
                    entry_px, entry_t = c[i], t[i]
                pos = new
    return pd.DataFrame(trades)


def summary(trades, point_value=20):
    daily = trades.groupby("date").pnl.sum()
    eq = daily.cumsum()
    by_year = trades.groupby("year").agg(trades=("pnl", "size"),
                                         win_rate=("pnl", lambda x: round(100 * (x > 0).mean(), 1)),
                                         avg_pts=("pnl", lambda x: round(x.mean(), 2)),
                                         total_pts=("pnl", lambda x: round(x.sum())))
    by_year["total_$"] = by_year.total_pts * point_value
    return by_year, dict(total_pts=trades.pnl.sum(), sharpe=daily.mean() / daily.std() * np.sqrt(252),
                         max_dd_pts=(eq - eq.cummax()).min(), trades=len(trades))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--rules", choices=RULES, default="buffer")
    ap.add_argument("--cost", type=float, default=1.0, help="points per round trip")
    a = ap.parse_args()
    tr = backtest(load_data(a.data), a.rules, a.cost)
    by_year, s = summary(tr)
    print(by_year.to_string())
    print(f"\nTotal {s['total_pts']:,.0f} pts (${20 * s['total_pts']:,.0f} per NQ) | Sharpe {s['sharpe']:.2f} | "
          f"max DD {s['max_dd_pts']:,.0f} pts | {s['trades']} trades")
    tr.to_csv(f"trades_{a.rules}.csv", index=False)
