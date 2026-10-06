"""Faccioli first run (2026-10-05): the night gain rule (deviations F5a), Route B.

Reproduces methods/faccioli/results/protocol_v1_nightgain/: gain_rule = "night" and no l_bound
grid axis, otherwise the committed settings. Does not touch results/method_comparison.md.

Usage: python methods/faccioli/src/run_nightgain.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import protocol as PROT  # noqa: E402

RD = "protocol_v1_nightgain"


def config():
    cfg = PROT.protocol_config("faccioli")
    cfg["methods"]["faccioli"]["observer"]["gain_rule"] = "night"
    del cfg["methods"]["faccioli"]["grid"]["l_bound"]
    cfg["protocol"]["results_dir"] = RD
    a = cfg["methods"]["faccioli"]["about"]
    a["title"] = "Faccioli STMD, night gain rule"
    a["description"] = [*a["description"][:2],
                        "This run: L is set each day from that day's night (00:00 to 07:00), as the "
                        "largest disturbance estimate there (Faccioli's first-night rule, per day; "
                        "deviations F5a). Superseded by the grid gain (protocol_v1).",
                        *a["description"][3:]]
    a["grid_source"] = ("Hochsmann 2026 Supplementary Table 1, Equation 7: Th_Res in {1.0, 1.1, ..., 4.0} "
                        "mg/dL, Th_Der in {0.2, 0.3, 0.4, 0.5} mg/dL/min")
    return cfg


def main():
    cfg = config()
    out = PROT.protocol_dir("faccioli", cfg)
    if "--docs-only" in sys.argv:
        PROT.finish("faccioli", cfg, out, compare=False)
    else:
        print(PROT.run_protocol("faccioli", out=out, cfg=cfg, compare=False))


if __name__ == "__main__":
    main()
