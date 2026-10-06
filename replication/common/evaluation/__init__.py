"""Method-agnostic evaluation framework for CGM excursion detectors on CGMacros.

A detector is a callable ``detect(times, glucose, params) -> detection times`` applied to
one participant-day. Everything else (cohort, scoring, tuning, metrics) lives here and is
driven by common/configs/cgmacros_eval.toml plus each method's methods/<name>/configs/*.toml.
"""
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "common" / "configs" / "cgmacros_eval.toml"

# reuse the existing QC pipeline and loader without copying them
for p in (REPO / "common" / "data", REPO / "common" / "qc"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _merge(base, extra, where=""):
    for k, v in extra.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _merge(base[k], v, f"{where}{k}.")
        elif k in base:
            raise KeyError(f"config key {where}{k} defined twice")
        else:
            base[k] = v
    return base


def load_config(*method_configs, path=CONFIG):
    """Shared settings, with each method config merged in (no key may be defined twice)."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    for m in method_configs:
        with open(m, "rb") as f:
            _merge(cfg, tomllib.load(f))
    return cfg
