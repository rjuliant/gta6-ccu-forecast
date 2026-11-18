# gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/rjuliant/gta6-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/rjuliant/gta6-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Hour-by-hour quantile forecast of the Grand Theft Auto VI Twitch category's concurrent viewers
over the 24 UTC hours of its release day, 2026-11-19, from everything recorded up to the end of
its first hour.

## Method

The quantity that transfers between launches is the shape of the release day relative to its own
first hour, not the absolute count:

    r_h = ln(v_h / v_1),  h = 2..24

Every comparable launch shipped with the case contributes one such curve. A record launch does
not decay like a niche one, so the pool is narrowed to the k = 12 comparables nearest this launch
in log scale. Each hour's row keeps the empirical quantiles of r_h over that window for the core
(0.25, 0.5, 0.75) and pushes the two tails out to the wider of the empirical quantile and the
normal one at the window's own standard deviation:

    q05 = p1 * exp(med + min(emp_q(0.05) - med, -1.6448536269514722 * sd))
    q95 = p1 * exp(med + max(emp_q(0.95) - med,  1.6448536269514722 * sd))

Hours covered by fewer than three comparables fall back to the house baseline's random-walk
spread, so the output is always a valid, non-degenerate row.

## Why k = 12 with floored tails

Selected by leave-one-out over the kit's own 37 usable comparable launches (each in turn a
pseudo-case, forecast from the other 36), on the 16 launches that opened above 100k viewers --
the regime a record launch sits in:

| setting | loss | 90% coverage |
| --- | --- | --- |
| k = 8, empirical quantiles (v1) | 0.2270 | 0.810 |
| k = 12, empirical quantiles | 0.2196 | 0.815 |
| **k = 12, empirical core, floored tails** | **0.2204** | **0.905** |
| k = 8, empirical core, floored tails | 0.2294 | 0.913 |

Coverage of 0.810 against a nominal 0.90 is the defect in v1: with eight neighbours the empirical
5% and 95% order statistics sit inside where the truth falls, and every miss outside the band is
charged at the tails. Twelve neighbours widen the shape diversity without pooling launches that
opened at a few hundred viewers with launches that opened near a million (the whole pool of 36
costs 0.3825 in this band), and flooring each tail at the normal width lifts coverage to 0.905 for
0.0008 of loss. The median is untouched, so the typical miss does not move.

## Run

    MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py

Python 3.13, standard library only, deterministic, no network.

## License

MIT, see LICENSE.
