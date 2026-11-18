"""Build the README figures. Usage: python make_figures.py path/to/csv_folder"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import vwap_strategy as V

BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 10, "axes.titleweight": "bold",
                     "axes.titlesize": 12, "text.parse_math": False, "legend.frameon": False})
PV = 20  # $ per point, 1 NQ
LAB = {"paper": "Original rules (paper)", "buffer": "Buffer rules (ours)"}
COL = {"paper": ORANGE, "buffer": BLUE}

def dollars(x, _=None):
    return f"-${abs(x)/1000:,.0f}k" if x < 0 else f"${x/1000:,.0f}k"

def run(df):
    return {(r, c): V.backtest(df, r, c) for r in ("paper", "buffer") for c in (0, 0.25, 0.5, 1.0)}

def fig_equity(R):
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for r in ("paper", "buffer"):
        d = R[(r, 1.0)].groupby("date").pnl.sum().cumsum() * PV
        ax.plot(pd.to_datetime(d.index), d.values, color=COL[r], lw=2, label=LAB[r])
        ax.annotate(dollars(d.iloc[-1]), (pd.to_datetime(d.index[-1]), d.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", color=INK, fontsize=10)
    ax.axvspan(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"), color=GRID, alpha=0.6, lw=0)
    lo_, hi_ = ax.get_ylim(); ax.text(pd.Timestamp("2025-07-01"), lo_ + 0.03 * (hi_ - lo_), "2025\nout of sample", ha="center", va="bottom", color=INK2, fontsize=9)
    ax.yaxis.set_major_formatter(dollars); ax.set_ylabel("Cumulative P&L, 1 NQ")
    ax.set_title("Cumulative P&L after 1 pt cost per round trip (1 NQ contract)", loc="left")
    ax.legend(loc="upper left"); fig.tight_layout(); fig.savefig("figures/equity_curve.png", dpi=160); plt.close(fig)

def fig_yearly(R):
    fig, ax = plt.subplots(figsize=(10, 4.4))
    yrs = sorted(R[("buffer", 1.0)].year.unique()); x = np.arange(len(yrs)); w = 0.38
    for k, r in enumerate(("paper", "buffer")):
        y = R[(r, 1.0)].groupby("year").pnl.sum().reindex(yrs).fillna(0) * PV
        bars = ax.bar(x + (k - 0.5) * w, y.values, w - 0.04, color=COL[r], label=LAB[r], edgecolor=SURF, linewidth=1)
        for b, v in zip(bars, y.values):
            ax.annotate(dollars(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, 3 if v >= 0 else -11),
                        textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.axhline(0, color=INK2, lw=0.8); ax.set_xticks(x, [str(y) + ("*" if y == 2025 else "") for y in yrs])
    ax.yaxis.set_major_formatter(dollars); ax.set_ylabel("Net P&L, 1 NQ")
    ax.set_title("Net P&L by year after 1 pt cost (1 NQ)   * 2025 = out of sample", loc="left")
    ax.legend(loc="upper left"); fig.tight_layout(); fig.savefig("figures/yearly.png", dpi=160); plt.close(fig)

def fig_costs(R):
    fig, ax = plt.subplots(figsize=(8, 4.2)); costs = [0, 0.25, 0.5, 1.0]
    for r in ("paper", "buffer"):
        y = [R[(r, c)].pnl.sum() * PV for c in costs]
        ax.plot(costs, y, "-o", color=COL[r], lw=2, ms=8, label=LAB[r], markeredgecolor=SURF, markeredgewidth=2)
        ax.annotate(dollars(y[-1]), (costs[-1], y[-1]), xytext=(8, 0), textcoords="offset points", va="center", fontsize=9)
    ax.set_xticks(costs, ["0", "0.25", "0.5", "1.0"]); ax.set_xlabel("Cost per round trip (NQ points)")
    ax.yaxis.set_major_formatter(dollars); ax.set_ylabel("Total net P&L 2019–2025, 1 NQ")
    ax.set_title("Sensitivity to trading costs", loc="left"); ax.legend(loc="lower left")
    ax.set_xlim(-0.05, 1.18); fig.tight_layout(); fig.savefig("figures/cost_sensitivity.png", dpi=160); plt.close(fig)

def fig_example(df, R):
    """One day, both rule sets: price, VWAP, buffer band, entries/exits."""
    pb, pp = R[("buffer", 1.0)], R[("paper", 1.0)]
    nb, np_ = pb.groupby("date").size(), pp.groupby("date").size()
    cand = [d for d in nb.index if d.year == 2024 and nb[d] == 2 and np_.get(d, 0) >= 15]
    day = max(cand, key=lambda d: pb[pb.date == d].pnl.sum())
    x = df[df.date == day]; buf = 0.15 * x.vol14.iloc[0]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.2), sharex=True)
    for ax, r in zip(axes, ("paper", "buffer")):
        ax.plot(x.index, x.close, color=INK2, lw=1.1, label="NQ price (1-min close)")
        ax.plot(x.index, x.vwap, color=BLUE, lw=2, label="Session VWAP")
        if r == "buffer":
            ax.fill_between(x.index, x.vwap * (1 - buf), x.vwap * (1 + buf), color=BLUE, alpha=0.12, lw=0, label=f"Buffer ±{buf*100:.2f}%")
            ax.axvline(x.index[x.minute == 600][0], color=INK2, ls=":", lw=1); ax.text(x.index[x.minute == 600][0], x.low.min(), " 10:00 first check", color=INK2, fontsize=8, va="bottom")
        t = R[(r, 1.0)]; t = t[t.date == day]
        for _, tr in t.iterrows():
            colr = AQUA if tr.side == "long" else RED; mk = "^" if tr.side == "long" else "v"
            ax.scatter(tr.entry_time, tr.entry, marker=mk, s=70, color=colr, edgecolor=SURF, linewidth=1.5, zorder=5)
        ax.scatter([], [], marker="^", color=AQUA, s=60, label="Go long"); ax.scatter([], [], marker="v", color=RED, s=60, label="Go short")
        ax.set_title(f"{LAB[r]}: {len(t)} trades, net {t.pnl.sum():+,.0f} pts (${t.pnl.sum()*PV:+,.0f})", loc="left")
        ax.legend(loc="upper left", ncol=3, fontsize=8)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=x.index.tz))
    fig.suptitle(f"Example day: {day:%A %d %B %Y}", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(); fig.savefig("figures/example_day.png", dpi=160); plt.close(fig)
    return day

def fig_moves(df, R):
    """Buffer strategy return by size of the day's NQ move — the 'long volatility' profile."""
    p = R[("buffer", 1.0)].groupby("date").pnl.sum()
    g = df.groupby("date"); px = g.open.first(); ret = g.close.last().pct_change()
    d = pd.DataFrame({"s": p / px.reindex(p.index) * 100, "m": ret.reindex(p.index).abs()}).dropna()
    d["q"] = pd.qcut(d.m, 5, labels=["Calmest 20%", "2nd", "3rd", "4th", "Biggest 20%"])
    y = d.groupby("q", observed=True).s.mean()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.bar(y.index.astype(str), y.values, color=[BLUE] * 5, edgecolor=SURF, width=0.6)
    for b, v in zip(bars, y.values):
        ax.annotate(f"{v:+.2f}%", (b.get_x() + b.get_width() / 2, v), xytext=(0, 3 if v >= 0 else -12), textcoords="offset points", ha="center", fontsize=9)
    ax.axhline(0, color=INK2, lw=0.8); ax.set_ylim(min(y.min() * 1.25, 0), y.max() * 1.15); ax.set_ylabel("Avg strategy return per day (% of notional)")
    ax.set_xlabel("Days grouped by size of NQ's daily move")
    ax.set_title("It earns on big-move days in either direction", loc="left")
    fig.tight_layout(); fig.savefig("figures/return_by_move_size.png", dpi=160); plt.close(fig)

if __name__ == "__main__":
    df = V.load_data(sys.argv[1] if len(sys.argv) > 1 else "data")
    R = run(df)
    fig_equity(R); fig_yearly(R); fig_costs(R); print("example day:", fig_example(df, R)); fig_moves(df, R)
    for r in ("paper", "buffer"):
        by, s = V.summary(R[(r, 1.0)]); print(r); print(by.to_string()); print(s)
