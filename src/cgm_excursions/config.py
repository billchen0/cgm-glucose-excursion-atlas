"""Reading and validating the preprocessing configuration.

The configuration is the *only* place a threshold lives. Every value the pipeline uses
to judge data comes from here, and every one of them is recorded in the run manifest so
a result can be traced to the exact settings that produced it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "preprocessing.yaml"

REQUIRED_SECTIONS = ("streams", "qc", "grid", "gaps")

# Values the code needs to exist. Anything else may be absent and simply means its rule
# is not applied, which is the safe direction: absence never silently widens a rule.
DEFAULTS: dict[str, Any] = {
    "streams": {
        "primary": "dexcom",
        "replication": "libre",
        "documented_range_mgdl": {"dexcom": [40, 400], "libre": [40, 500]},
    },
    "qc": {
        "duplicate_timestamp": {"enabled": True},
        "rate_of_change": {"enabled": True, "max_mgdl_per_min": 4.0},
        "flatline": {"enabled": True, "min_run_minutes": 20},
        "isolated_spike": {
            "enabled": True,
            "min_delta_mgdl": 50,
            "neighbour_max_delta_mgdl": 25,
        },
        "possible_compression_low": {"enabled": True, "value_mgdl": 40},
        "advanced": {"enabled": False},
    },
    "grid": {"cadence_seconds": 60, "interpolate": False},
    "gaps": {"min_gap_seconds": 900, "segment_break_seconds": 3600},
    "detector_view": {"enabled": False, "max_gap_seconds": None},
}


class ConfigError(ValueError):
    """The configuration is unusable as written."""


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load the preprocessing config, filling in defaults for absent keys."""
    resolved = Path(path) if path else DEFAULT_CONFIG_PATH
    if not resolved.exists():
        raise ConfigError(f"configuration file not found: {resolved}")

    loaded = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"{resolved} must contain a YAML mapping")

    config = _merge(DEFAULTS, loaded)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    """Reject a config the pipeline cannot honestly execute."""
    for section in REQUIRED_SECTIONS:
        if section not in config:
            raise ConfigError(f"configuration is missing the '{section}' section")

    streams = config["streams"]
    primary, replication = streams.get("primary"), streams.get("replication")
    if primary == replication:
        raise ConfigError(
            f"primary and replication must be different streams; both are {primary!r}. "
            "The two sensors are never averaged or filled from one another."
        )
    for name in (primary, replication):
        if name not in streams.get("documented_range_mgdl", {}):
            raise ConfigError(f"no documented range configured for stream {name!r}")
        bounds = streams["documented_range_mgdl"][name]
        if not (isinstance(bounds, (list, tuple)) and len(bounds) == 2):
            raise ConfigError(f"documented_range_mgdl[{name}] must be [low, high]")
        low, high = bounds
        # bool is a subclass of int, so it must be excluded explicitly rather than passing
        # as a number. Without this check a range of strings validates cleanly: the length
        # and order checks both pass whenever the two values happen to sort after one
        # another, as in ['40', '400'] (numbers quoted in YAML) or ['a', 'z']. The bad
        # config is then accepted silently and only fails much later, when a glucose value
        # is compared against a string.
        numeric = (int, float)
        if any(isinstance(bound, bool) or not isinstance(bound, numeric) for bound in (low, high)):
            raise ConfigError(
                f"documented_range_mgdl[{name}] bounds must be numbers; got {bounds!r}"
            )
        if low >= high:
            raise ConfigError(f"documented_range_mgdl[{name}] low must be below high")

    gaps = config["gaps"]
    if float(gaps["min_gap_seconds"]) <= 0:
        raise ConfigError("gaps.min_gap_seconds must be positive")
    if float(gaps["segment_break_seconds"]) < float(gaps["min_gap_seconds"]):
        raise ConfigError(
            "gaps.segment_break_seconds must be at least gaps.min_gap_seconds, "
            "otherwise a segment can break on a gap that is never reported"
        )

    if config["grid"].get("interpolate"):
        raise ConfigError(
            "grid.interpolate must stay false. The canonical outputs never interpolate; "
            "use detector_view for an explicitly-bounded interpolated view."
        )

    detector = config.get("detector_view", {})
    if detector.get("enabled") and detector.get("max_gap_seconds") is None:
        raise ConfigError(
            "detector_view.enabled requires an explicit max_gap_seconds. There is no "
            "default gap-bridging distance; the caller must state it."
        )


def config_hash(config: dict[str, Any]) -> str:
    """Stable digest of the effective configuration, for the run manifest."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge; ``override`` wins, nested mappings merge key by key."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged
