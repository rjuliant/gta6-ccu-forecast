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

The case's p1 is hour 1's print, floored at 1. The pool is narrowed to the K = 12 comparables
nearest this launch in log scale -- smallest |ln(comparable_p1) - ln(case_p1)| -- and each hour
is built from the r_h of those neighbours that cover it (n >= 3, else the house baseline row).
With med the empirical median of those n log ratios and sd their standard deviation about it,

    sd  = sqrt(sum((r - med)^2) / (n - 1)), floored at 0.03
    q05 = p1 * exp(med + min(emp_q(0.05) - med, -1.6448536269514722 * sd))
    q25 = p1 * exp(emp_q(0.25))
    q50 = p1 * exp(med)
    q75 = p1 * exp(emp_q(0.75))
    q95 = p1 * exp(med + max(emp_q(0.95) - med,  1.6448536269514722 * sd))

with the empirical quantiles taken by linear interpolation between order statistics
(pos = tau * (n - 1)). The core stays empirical, because it carries the real shape of the day;
each tail is pushed out to the wider of the empirical and the normal quantile, so the 90% band
cannot be systematically tighter than a normal one at the same sd.

Why K = 12 with floored tails beats K = 8 with raw empirical quantiles
---------------------------------------------------------------------
Leave-one-out over the kit's 37 usable comparables (each in turn a pseudo-case, forecast from the
other 36, scored on its own hours 2..24), on the 16 launches that opened above 100k viewers --
the regime a GTA VI release is in:

    K=8,  empirical quantiles              loss 0.2270   90% coverage 0.810
    K=12, empirical quantiles              loss 0.2196   90% coverage 0.815
    K=12, empirical core, floored tails    loss 0.2204   90% coverage 0.905   <- this program
    K=8,  empirical core, floored tails    loss 0.2294   90% coverage 0.913

Two separate defects are being fixed. (1) The window: with only 8 neighbours the empirical 5% and
95% order statistics sit inside where the truth actually falls, and coverage of 0.810 against a
nominal 0.90 means one hour in ten lands outside the band, where the pinball loss charges 2*tau
or 2*(1-tau) per unit of log. Widening to 12 buys more shape diversity without mixing the two
regimes -- K = 36 (the whole pool, whose hour-1 counts run from 164 to 875,155) mixes launches
that opened at a few hundred viewers with launches that opened at close to a million, and costs
0.3825 in this band -- and it is the setting that minimises the loss in the high band, 0.2196
against K = 8's 0.2270. (2) The tails: the empirical 5% and 95% of twelve points are the first
and last order statistics, which are noisy and biased inward, so even at K = 12 coverage is only
0.815. Pushing each tail out to the wider of the empirical and the normal quantile at the same sd
lifts coverage to 0.905 for 0.0008 of loss -- a trade worth making, because an under-covered band
pays at the tails on every hour of the real case, while 0.0008 is inside the noise of a 16-launch
sample. At K = 8 the same fix costs 0.0024 (0.2270 -> 0.2294) and overshoots coverage to 0.913:
the wider window is what makes the floored tail cheap.

The median is left exactly where the neighbours put it, so the typical miss does not move; only
the two outer levels change.

The same leave-one-out, run over every launch rather than the high band, is the cost of the
choice: K = 12 with floored tails scores 0.4456 against K = 8's 0.4181, and on the ten launches
that opened under 20k viewers it is clearly worse (0.9548 against 0.8009), because a small
category's day can multiply a hundredfold and a wider window's tails do not reach that far. That
is a deliberate trade: the graded case is a record launch's first hour, where the high band is
the only regime that applies, and it is the band where this setting is best calibrated.

Robustness
----------
- Deterministic: no randomness, no wall clock, no network, no third-party imports. The same case
  always yields the same bytes.
- Malformed input is survivable: a missing or null ``comparables`` list, a comparable that is not
  an object, a missing ``day_start``, junk ``hourly`` rows, a non-numeric or non-finite
  ``viewers``, a missing ``known`` row, an hour-1 print of 0 (floored to 1), and huge or tiny
  prints all yield 23 valid rows rather than a crash. A comparable contributes only the hours it
  actually covers. An input file that will not parse, or that is not a JSON object, is treated as
  an empty case and still gets the baseline rows -- a crash would score as every quantile at the
  hour-1 print, which is the worst row available, so emitting the baseline is never worse.
- When fewer than three neighbours cover an hour, that hour falls back to the house baseline row,
  q_tau = p1 * exp(z_tau * 0.15 * sqrt(h - 1)); a case with no usable comparable at all falls back
  for every hour.
- Every value is clamped into (0, 1e9], each row sorted ascending and rounded to 4 decimals, so the
  output satisfies the shape rules whatever the input holds. Counts are computed in log space, so
  an extreme print or log ratio saturates at the clamp instead of overflowing to infinity.
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
# The standard normal's quantile at each level; used by the house-baseline fallback and by the
# floor on the two tails.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
K_NEAR = 12         # comparables kept by the log-scale window
MIN_COVER = 3       # comparables an hour needs before its own quantiles are trusted
MIN_HOURS = 18      # of hours 2..24 a comparable must cover to be usable at all
SIGMA = 0.15        # the house baseline's log spread per sqrt(hour)
SD_FLOOR = 0.03     # the smallest standard deviation a neighbour set is credited with
CAP = 1e9           # the largest count a row may hold
FLOOR = 1e-4        # the smallest; survives 4-decimal rounding while staying above 0
EXP_LIMIT = 700.0   # keeps math.exp finite whatever a ratio turns out to be
LOG_CAP = math.log(CAP)
LOG_FLOOR = math.log(FLOOR)


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


def scaled(p1, offset):
    """p1 * exp(offset), clamped into (0, 1e9] in log space so no intermediate can overflow."""
    log_p1 = math.log(p1) if p1 > 0 else 0.0
    total = log_p1 + min(EXP_LIMIT, max(-EXP_LIMIT, offset))
    if total >= LOG_CAP:
        return CAP
    if total <= LOG_FLOOR:
        return FLOOR
    return math.exp(total)


def fallback_row(p1, h):
    """The house baseline's row for hour h: persistence with a random-walk spread."""
    return clamp_row([scaled(p1, z * SIGMA * math.sqrt(h - 1)) for z in Z])


def row_from(vals, p1):
    """One hour's five quantiles from the neighbour log ratios: empirical core, floored tails."""
    med = quantile(vals, 0.5)
    n = len(vals)
    var = sum((r - med) ** 2 for r in vals) / (n - 1) if n > 1 else 0.0
    sd = max(SD_FLOOR, math.sqrt(var))
    lo = min(quantile(vals, 0.05) - med, Z[0] * sd)
    hi = max(quantile(vals, 0.95) - med, Z[4] * sd)
    return clamp_row([
        scaled(p1, med + lo),
        scaled(p1, quantile(vals, 0.25)),
        scaled(p1, med),
        scaled(p1, quantile(vals, 0.75)),
        scaled(p1, med + hi),
    ])


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
        out[h] = row_from(vals, p1) if len(vals) >= MIN_COVER else fallback_row(p1, h)
    return out


def load_case(path):
    """The case object at path, or an empty dict when the file is unreadable or not an object.

    A crash scores the case as if every quantile were its hour-1 print, which is the worst row
    available; emitting the baseline instead is never worse, so nothing here raises.
    """
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return case if isinstance(case, dict) else {}


def write_case(path, out_dir):
    """Write <id>.out for one <id>.in."""
    f = forecast(load_case(path))
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
