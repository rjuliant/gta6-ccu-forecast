"""gta6-twitch-ccu-forecast-01: hour-by-hour Twitch CCU quantiles for GTA VI's release day.

Task
----
A case describes one launch's release day in UTC. Hour 1's print is known (``known``); hours
2..24 must each be forecast as five quantiles, at the levels 0.05, 0.25, 0.5, 0.75 and 0.95.
Scoring is pinball loss on the log scale, averaged over every hour and every level, so both the
median's accuracy and an honest spread are paid for: too narrow loses at the tails, too wide
loses at every hour.

Method
------
The quantity that transfers between launches is the *shape* of the release day relative to its
own first hour, not the absolute count. Each comparable launch in the case is therefore reduced
to a curve of log ratios

    r_h = ln(viewers_h / viewers_1),   h = 2..24

built only from the comparable's ``hourly`` rows whose ``from`` timestamp falls on its own
``day_start`` date, with the hour-of-day mapped to h = hour + 1 (the 00:00 row is hour 1). A
comparable is used only if it has hour 1 and at least 18 of the hours 2..24 with viewers > 0;
its own hour-1 count is kept as its scale tag.

The case's p1 is hour 1's print, floored at 1. The pool is then narrowed to the K = 8
comparables nearest this launch in log scale -- smallest |ln(comparable_p1) - ln(case_p1)| --
and each hour is the empirical quantile of the r_h of the comparables in that window:

    q_tau(h) = p1 * exp(quantile_tau({r_h}))

with the quantile taken by linear interpolation between order statistics (pos = tau * (n - 1)).

Why the scale window matters
----------------------------
A record launch does not decay like a niche one. Across the kit's 16 launches that opened above
100k viewers, every later hour of the release day stays inside 0.31x to 2.7x of hour 1: the
opening hour is already near the day's peak, and the shape is a gentle slide through the small
hours with an evening recovery (Elden Ring: 1.00 at hour 1, 0.53 at hour 9, 0.95 at hour 19,
0.72 at hour 24). Across the 21 launches that opened below 100k, hour 1 is instead a tiny
sample of a category nobody has found yet, and the day's peak runs up to three orders of
magnitude above it (Hollow Knight: Silksong 164 at hour 1, 347,773 at hour 16; Battlefield 6
2,470 to 563,617). Pooled together, those two populations give a bimodal r_h whose median
belongs to neither and whose spread has to cover a factor of 2,000 -- which the pinball loss
charges for at every level of every hour. Keeping only launches that began their day at a
comparable magnitude makes the pooled r_h a like-for-like shape and the spread an honest one,
which is exactly what a proper scoring rule rewards.

Leave-one-out over the kit's 37 usable comparable launches (each in turn a pseudo-case, forecast
from the other 36, scored against its own hours 2..24) measures the effect. Over all 37 launches
K = 8 is the best of the grid tried, at 0.4181 against the house persistence baseline's 0.9296;
on the 16 launches that began above 100k viewers -- the regime a GTA VI release is in -- it
scores 0.2270 against 0.2611, with 90% coverage 0.810 against 0.837. The window's width is what
does the work: K = 36 (the whole pool) costs 0.3825 in the high band and 0.7139 overall, because
it mixes shapes that disagree, and K = 3 costs 0.3233 there with coverage collapsing to 0.459,
because three launches cannot describe a spread. In the high band K = 10 and K = 12 come in at
0.2229 and 0.2196, within 0.008 of K = 8; K = 8 is kept as the brief fixes it, and it is the
value that also minimises the all-launches loss. K = 8 also beats the baseline on 28 of the 37
launches individually; its worst regressions are mid-size launches whose own day ran against
their window's shape (Monster Hunter Wilds 0.5178 against 0.4273), which is the price of a
narrow window and is far smaller than the 0.5-wide gains it makes on the small ones.

Robustness
----------
- Deterministic: no randomness, no wall clock, no network, no third-party imports. The same case
  always yields the same bytes.
- When fewer than three comparables in the window cover an hour, that hour falls back to the
  house baseline row, q_tau = p1 * exp(z_tau * 0.15 * sqrt(h - 1)); a case with no usable
  comparable at all falls back for every hour. A case therefore always yields 23 valid rows.
- Every value is clamped into (0, 1e9], each row sorted ascending and rounded to 4 decimals, so
  the output satisfies the shape rules whatever the input holds.
- Reads every ``*.in`` in MAKEFUN_INPUT_DIR (default /input) and writes ``<id>.out`` to
  MAKEFUN_OUTPUT_DIR (default /output).
"""
import json
import math
import os
import sys
from pathlib import Path

# The grader runs `python3 -P -s`, which keeps this file's directory off sys.path: put it back
# first, so a module shipped beside main.py would still import.
sys.path.insert(0, str(Path(__file__).resolve().parent))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level; used only by the house-baseline fallback.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
K_NEAR = 8          # comparables kept by the log-scale window
MIN_COVER = 3       # comparables an hour needs before its own quantiles are trusted
MIN_HOURS = 18      # of hours 2..24 a comparable must cover to be usable at all
SIGMA = 0.15        # the house baseline's log spread per sqrt(hour)
CAP = 1e9           # the largest count a row may hold
FLOOR = 1e-4        # the smallest; survives 4-decimal rounding while staying above 0
EXP_LIMIT = 700.0   # keeps math.exp finite whatever a ratio turns out to be


def quantile(values, tau):
    """Empirical quantile: linear interpolation between order statistics."""
    v = sorted(values)
    n = len(v)
    if n == 1:
        return v[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(n - 1, lo + 1)
    w = pos - lo
    return v[lo] * (1.0 - w) + v[hi] * w


def number(value):
    """A finite float from a JSON value, or None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def hour_of(timestamp):
    """The hour-of-day of an ISO timestamp as h = hour + 1, or None."""
    at = str(timestamp or "")
    if len(at) < 13:
        return None
    try:
        h = int(at[11:13]) + 1
    except ValueError:
        return None
    return h if 1 <= h <= 24 else None


def day_curve(comp):
    """(p1, {h: ln(v_h / v_1)}) for a comparable's own release day, or None if unusable."""
    if not isinstance(comp, dict):
        return None
    day = str(comp.get("day_start") or "")[:10]
    if len(day) != 10:
        return None
    hours = {}
    for row in comp.get("hourly") or []:
        if not isinstance(row, dict):
            continue
        at = str(row.get("from") or "")
        if at[:10] != day:
            continue
        h = hour_of(at)
        if h is None:
            continue
        v = number(row.get("viewers"))
        if v is None or v <= 0:
            continue
        hours[h] = v
    base = hours.get(1)
    if base is None:
        return None
    covered = [h for h in range(2, 25) if h in hours]
    if len(covered) < MIN_HOURS:
        return None
    return base, {h: math.log(hours[h] / base) for h in covered}


def build_pool(case):
    """Every usable comparable, tagged with its own hour-1 scale."""
    pool = []
    for comp in case.get("comparables") or []:
        got = day_curve(comp)
        if got is not None:
            pool.append({"p1": got[0], "curve": got[1]})
    return pool


def case_p1(case):
    """Hour 1's print, floored at 1."""
    known = [r for r in (case.get("known") or []) if isinstance(r, dict)]
    first = None
    for row in known:
        if number(row.get("hour")) == 1:
            v = number(row.get("viewers"))
            if v is not None and (first is None or v > first):
                first = v
    if first is None:
        # No hour-1 row: the day's scale is the largest print the case knows.
        for row in known:
            v = number(row.get("viewers"))
            if v is not None and (first is None or v > first):
                first = v
    return max(1.0, first if first is not None else 1.0)


def clamp_row(row):
    """Clamp into (0, 1e9], sort ascending, round to 4 decimals."""
    out = []
    for x in row:
        v = number(x)
        out.append(min(CAP, max(FLOOR, 1.0 if v is None else v)))
    out.sort()
    return [round(x, 4) for x in out]


def fallback_row(p1, h):
    """The house baseline's row for hour h: persistence with a random-walk spread."""
    row = []
    for z in Z:
        offset = min(EXP_LIMIT, max(-EXP_LIMIT, z * SIGMA * math.sqrt(h - 1)))
        row.append(p1 * math.exp(offset))
    return clamp_row(row)


def forecast(case):
    """{h: [q05, q25, q50, q75, q95]} for h = 2..24."""
    p1 = case_p1(case)
    pool = build_pool(case)
    if not pool:
        return {h: fallback_row(p1, h) for h in range(2, 25)}

    lp = math.log(p1)
    near = sorted(pool, key=lambda r: abs(math.log(r["p1"]) - lp))[:K_NEAR]

    out = {}
    for h in range(2, 25):
        vals = [r["curve"][h] for r in near if h in r["curve"]]
        if len(vals) < MIN_COVER:
            out[h] = fallback_row(p1, h)
            continue
        row = []
        for tau in LEVELS:
            offset = min(EXP_LIMIT, max(-EXP_LIMIT, quantile(vals, tau)))
            row.append(p1 * math.exp(offset))
        out[h] = clamp_row(row)
    return out


def write_case(path, out_dir):
    """Write <id>.out for one <id>.in."""
    case = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(case, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    f = forecast(case)
    rows = [{"hour": h, "q": f[h]} for h in range(2, 25)]
    payload = json.dumps({"hours": rows}, separators=(",", ":"))
    (out_dir / (path.stem + ".out")).write_text(payload, encoding="utf-8")


def main():
    in_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR") or "/input")
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(in_dir.glob("*.in")):
        write_case(path, out_dir)


if __name__ == "__main__":
    main()
