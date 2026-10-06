"""Synthetic tests of the shared excursion definition.
Run: python common/evaluation/tests/test_excursion.py (from replication/)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import load_config  # noqa: E402
from common.evaluation.excursion import Trace  # noqa: E402

E = load_config()["excursion"]
T0 = pd.Timestamp("2020-01-01 06:00")
A = pd.Timestamp("2020-01-01 08:00")          # anchor = minute 120


def trace(points, n=720, gaps=()):
    """Piecewise-linear glucose through (minute, value) points; gaps = [(start, stop)) NaN."""
    m, v = zip(*points)
    g = np.interp(np.arange(n), m, v)
    for s, e in gaps:
        g[s:e] = np.nan
    return Trace(pd.Series(g, pd.date_range(T0, periods=n, freq="1min")), E)


def at(minute):
    return T0 + pd.Timedelta(minutes=minute)


def check(name, ex, **want):
    for k, v in want.items():
        assert ex[k] == v, (name, k, ex[k], v)
    print(f"ok  {name:30s} end {ex['end']:%H:%M} ({ex['end_min']} min) type {ex['end_type']:18s} "
          f"baseline {ex['baseline']:.0f} peak {ex['peak']:.0f} at +{ex['peak_min']}")


# 1 clean return: 100 -> 200 at 08:40 -> 100 at 09:30; threshold 100 + max(10, 20) = 120
ex = trace([(0, 100), (120, 100), (160, 200), (210, 100), (719, 100)]).excursion(A)
check("clean return", ex, end_type="returned", end=at(200), peak=200.0, peak_min=40, baseline=100.0)

# 2 trough >= 50 %: peak 200, dip to 140 (60 % of 100) at 09:10, then rise to 190
ex = trace([(0, 100), (120, 100), (160, 200), (190, 140), (210, 190), (260, 100), (719, 100)]).excursion(A)
check("trough >= 50 % drop", ex, end_type="trough", end=at(190), peak=200.0)

# 3 double peak, dip < 50 % (200 -> 170 = 30 %), second peak 210 -> one excursion, P updates
ex = trace([(0, 100), (120, 100), (160, 200), (180, 170), (200, 210), (260, 100), (719, 100)]).excursion(A)
check("double peak < 50 % dip", ex, end_type="returned", peak=210.0, peak_min=80)

# 4 trough_interrupted: as case 2, with a new start 10 min after the trough
tr = trace([(0, 100), (120, 100), (160, 200), (190, 140), (210, 190), (260, 100), (719, 100)])
ex = tr.excursion(A, new_starts=[at(200)], start_window=(0, 30))
check("trough_interrupted (det)", ex, end_type="trough_interrupted", end=at(190))
ex = tr.excursion(A, new_starts=[at(170)], start_window=(-30, 30), closed_lo=True)
check("trough_interrupted (ref)", ex, end_type="trough_interrupted")
ex = tr.excursion(A, new_starts=[at(225)], start_window=(0, 30))
check("trough, start too late", ex, end_type="trough")

# 5 censored: plateau at 200 after the rise
ex = trace([(0, 100), (120, 100), (160, 200), (719, 200)]).excursion(A)
check("censored", ex, end_type="censored", end=at(300), end_min=180)

# 6 QC gap where the return would happen: closes at the first valid minute after the gap
ex = trace([(0, 100), (120, 100), (160, 200), (210, 100), (719, 100)], gaps=[(200, 215)]).excursion(A)
check("QC gap over the return", ex, end_type="returned", end=at(215))
# QC gap inside the trough confirmation: trough not confirmed
ex = trace([(0, 100), (120, 100), (160, 200), (190, 140), (210, 190), (260, 100), (719, 100)],
           gaps=[(191, 196)]).excursion(A)   # the +10 rise (min 194) is missing
assert ex["end_type"] != "trough" or ex["end"] != at(190), ex
check("QC gap in trough confirm", ex, end_type="returned")
# 7 no_rise: glucose stays within 10 mg/dL of the baseline for 180 min
ex = trace([(0, 100), (120, 100), (160, 107), (200, 101), (719, 101)]).excursion(A)
check("no_rise", ex, end_type="no_rise", end=at(300), censored=False)

# 8 rise gate: a flat start (within 10 mg/dL) cannot end the excursion before the real rise
ex = trace([(0, 96), (120, 96), (130, 104), (135, 103), (170, 135), (230, 100), (719, 100)]).excursion(A)
assert ex["end_min"] > 50 and ex["peak"] == 135.0, ex
check("rise gate (slow start)", ex, end_type="returned")
# 9 fall requirement: rise of 11 mg/dL (passes the gate), then a 1 mg/dL dip to b + 10.
#   Not an end: the fall (1) is < 0.50 * rise (11). The excursion continues to the real peak.
ex = trace([(0, 96), (120, 96), (130, 107), (135, 106), (170, 135), (230, 100), (719, 100)]).excursion(A)
assert ex["end_min"] > 50 and ex["peak"] == 135.0, ex
check("small rise + 1 mg/dL dip", ex, end_type="returned")
# a small rise that falls back by >= 50 % still ends: 96 -> 108 -> 101 (fall 7 >= 6)
ex = trace([(0, 96), (120, 96), (130, 108), (140, 101), (719, 101)]).excursion(A)
check("small rise, real fall", ex, end_type="returned", peak=108.0)
print("all excursion tests passed")
