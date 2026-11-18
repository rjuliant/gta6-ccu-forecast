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
not decay like a niche one, so the pool is narrowed to the k = 8 comparables nearest this launch
in log scale, and the forecast is the empirical quantile of r_h over that window:

    q_tau(h) = p1 * exp(quantile_tau({r_h}))

Hours covered by fewer than three comparables fall back to the house baseline's random-walk
spread, so the output is always a valid, non-degenerate row.

## Why k = 8

Selected by leave-one-out over the kit's own comparable launches: 0.1360 pinball loss on the
200k+ first-hour band against the house baseline's 0.2255, and 0.2773 on the 20k+ band against
0.3214. The 200k+ band is the regime a record launch sits in.

## Run

    MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py

Python 3.13, standard library only, deterministic, no network.

## License

MIT, see LICENSE.
