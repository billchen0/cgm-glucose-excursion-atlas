"""Run the standard protocol for one registered detector ([protocol] in common/configs/cgmacros_eval.toml).

Usage (from replication/):
  python common/run_protocol.py <method>               full run
  python common/run_protocol.py <method> --docs-only   README and comparison only
Outputs: methods/<method>/results/<results_dir>/ and results/method_comparison.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.evaluation import detectors, protocol as PROT  # noqa: E402


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    if len(names) != 1 or names[0] not in detectors.DETECTORS:
        sys.exit(f"usage: run_protocol.py <method> [--docs-only]; registered: {sorted(detectors.DETECTORS)}")
    name = names[0]
    if "--docs-only" in argv:
        cfg = PROT.protocol_config(name)
        PROT.finish(name, cfg, PROT.protocol_dir(name, cfg))
    else:
        print(PROT.run_protocol(name))


if __name__ == "__main__":
    main(sys.argv[1:])
