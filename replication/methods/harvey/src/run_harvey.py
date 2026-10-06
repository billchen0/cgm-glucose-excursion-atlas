"""Harvey (GRID) on CGMacros: Route A and Route B tuning, our rule and the review rule.

Usage: python methods/harvey/src/run_harvey.py
Outputs: methods/harvey/results/reference_tp_lockout/ (see its README.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import REPO, load_config  # noqa: E402
from common.evaluation import detectors, protocol as PROT  # noqa: E402

HARVEY = REPO / "methods" / "harvey"
HARVEY_CONFIG = HARVEY / "configs" / "harvey.toml"
OUT = HARVEY / "results" / "reference_tp_lockout"
METHOD = "harvey"
TITLE = "Harvey GRID"
RULES = ["ours", "review"]
HARVEY_2014 = dict(tau_F=6.0, G_min=130.0, Gp_min_3=1.5, Gp_min_2=1.6)   # Harvey 2014 p. 312


def run(cfg, out=OUT, rules=RULES, tag_extra=None, reference_fixed=True):
    """Tune and evaluate Harvey for the given matching rules; write outputs to ``out``.

    Thin wrapper around the shared ``protocol.run_method``.
    """
    return PROT.run_method(cfg, METHOD, out, rules=rules, tag_extra=tag_extra,
                           fixed=detectors.fixed_params(METHOD, cfg),
                           fixed_refs={"Harvey2014_fixed": HARVEY_2014} if reference_fixed else None,
                           title=TITLE)


def main():
    run(load_config(HARVEY_CONFIG))


if __name__ == "__main__":
    main()
