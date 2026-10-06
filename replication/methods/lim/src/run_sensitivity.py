"""Lim sensitivity runs (Lim 2026 sensitivity analysis): minimum PPGR height 20 and 30 mg/dL.

Same detector and protocol as the main run (protocol_v1, 10 mg/dL), with min_height fixed at 20 or
30. Outputs: methods/lim/results/protocol_v1_h20/ and protocol_v1_h30/. Does not touch
results/method_comparison.md.

Usage: python methods/lim/src/run_sensitivity.py [--docs-only]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import protocol as PROT  # noqa: E402

HEIGHTS = [20, 30]


def config(h):
    cfg = PROT.protocol_config("lim")
    cfg["methods"]["lim"]["grid"]["min_height"] = {"values": [h]}
    cfg["protocol"]["results_dir"] = f"protocol_v1_h{h}"
    a = cfg["methods"]["lim"]["about"]
    a["title"] = f"Lim wavelet PPGR, {h} mg/dL"
    a["grid_source"] = f"Sensitivity run (Lim 2026 sensitivity analysis): minimum height {h} mg/dL, fixed"
    a.pop("comparison_note", None)
    return cfg


def main():
    for h in HEIGHTS:
        cfg = config(h)
        out = PROT.protocol_dir("lim", cfg)
        if "--docs-only" in sys.argv:
            PROT.finish("lim", cfg, out, compare=False)
        else:
            print(PROT.run_protocol("lim", out=out, cfg=cfg, compare=False))


if __name__ == "__main__":
    main()
