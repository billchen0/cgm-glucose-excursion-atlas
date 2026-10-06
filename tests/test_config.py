"""Reading and validating the preprocessing configuration.

The configuration is the only place a threshold lives, so loading it must fill in safe
defaults and validation must reject the specific configurations the pipeline is not
allowed to execute: sensor averaging, silent interpolation, implicit gap bridging, and
incoherent gap/range thresholds.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from cgm_excursions.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULTS,
    ConfigError,
    config_hash,
    load_config,
    validate_config,
)


@pytest.fixture
def base_config() -> dict:
    """A known-valid config to mutate, so each test fails for exactly one reason."""
    return copy.deepcopy(DEFAULTS)


# --------------------------------------------------------------------- 1. load default
def test_default_config_loads_and_validates():
    config = load_config()

    assert validate_config(config) is None
    assert config["streams"]["primary"] == "dexcom"
    assert config["streams"]["replication"] == "libre"
    assert config["grid"]["interpolate"] is False
    assert DEFAULT_CONFIG_PATH.exists()


def test_defaults_validate_on_their_own(base_config):
    """The mutation tests below assume DEFAULTS itself is a valid configuration."""
    validate_config(base_config)


# ------------------------------------------------ 2. primary must not be replication
def test_primary_and_replication_must_be_different_streams(base_config):
    base_config["streams"]["primary"] = base_config["streams"]["replication"]

    with pytest.raises(ConfigError) as excinfo:
        validate_config(base_config)

    assert "different streams" in str(excinfo.value)


# --------------------------------------------------------- 3. no grid interpolation
def test_grid_interpolate_must_be_false(base_config):
    base_config["grid"]["interpolate"] = True

    with pytest.raises(ConfigError) as excinfo:
        validate_config(base_config)

    assert "interpolate" in str(excinfo.value)


# ------------------------------------- 4. detector view needs an explicit max gap
def test_detector_view_enabled_requires_explicit_max_gap(base_config):
    base_config["detector_view"] = {"enabled": True, "max_gap_seconds": None}

    with pytest.raises(ConfigError) as excinfo:
        validate_config(base_config)

    assert "max_gap_seconds" in str(excinfo.value)


def test_detector_view_enabled_with_a_stated_gap_is_allowed(base_config):
    base_config["detector_view"] = {"enabled": True, "max_gap_seconds": 120}

    validate_config(base_config)  # must not raise


# --------------------------------- 5. segment break may not precede the min gap
def test_segment_break_cannot_be_shorter_than_min_gap(base_config):
    base_config["gaps"]["segment_break_seconds"] = (
        base_config["gaps"]["min_gap_seconds"] - 1
    )

    with pytest.raises(ConfigError) as excinfo:
        validate_config(base_config)

    assert "segment_break_seconds" in str(excinfo.value)


def test_segment_break_equal_to_min_gap_is_allowed(base_config):
    base_config["gaps"]["segment_break_seconds"] = base_config["gaps"]["min_gap_seconds"]

    validate_config(base_config)  # must not raise


# -------------------------------------------------- 6. documented ranges are sane
@pytest.mark.parametrize(
    "bad_range",
    [
        [40],              # too short
        [40, 400, 500],    # too long
        40,                # not a sequence
        "40-400",          # not a sequence
        None,              # absent
    ],
)
def test_documented_range_must_be_a_two_element_pair(base_config, bad_range):
    base_config["streams"]["documented_range_mgdl"]["dexcom"] = bad_range

    with pytest.raises(ConfigError):
        validate_config(base_config)


@pytest.mark.parametrize("bad_range", [[500, 40], [40, 40]])
def test_documented_range_low_must_be_below_high(base_config, bad_range):
    base_config["streams"]["documented_range_mgdl"]["libre"] = bad_range

    with pytest.raises(ConfigError) as excinfo:
        validate_config(base_config)

    assert "low must be below high" in str(excinfo.value)


# --------------------------------------------------------------- 7. config_hash()
def test_config_hash_is_stable_and_sensitive_to_thresholds(base_config):
    same = copy.deepcopy(base_config)
    assert config_hash(base_config) == config_hash(same)

    # Key insertion order must not change the digest.
    reordered = {key: base_config[key] for key in reversed(list(base_config))}
    assert config_hash(base_config) == config_hash(reordered)

    changed = copy.deepcopy(base_config)
    changed["qc"]["flatline"]["min_run_minutes"] += 1
    assert config_hash(base_config) != config_hash(changed)

    changed_again = copy.deepcopy(base_config)
    changed_again["streams"]["documented_range_mgdl"]["dexcom"] = [30, 400]
    assert config_hash(base_config) != config_hash(changed_again)


# ------------------------------------------------------- 8. missing file is an error
def test_load_config_missing_path_raises(tmp_path):
    missing = tmp_path / "not-here.yaml"

    with pytest.raises(ConfigError) as excinfo:
        load_config(missing)

    assert "not found" in str(excinfo.value).lower()
    assert str(missing) in str(excinfo.value)


def test_load_config_fills_defaults_for_absent_keys(tmp_path):
    path = tmp_path / "minimal.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "streams": {
                    "primary": "dexcom",
                    "replication": "libre",
                    "documented_range_mgdl": {"dexcom": [40, 400], "libre": [40, 500]},
                },
                "qc": {},
                "grid": {},
                "gaps": {},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config["qc"]["flatline"]["min_run_minutes"] == (
        DEFAULTS["qc"]["flatline"]["min_run_minutes"]
    )
    assert config["grid"]["interpolate"] is False
    assert config["detector_view"]["enabled"] is False


# ------------------------------------------- 9. range bounds must be real numbers
def test_quoted_number_range_bounds_are_rejected(base_config):
    """The realistic silent case: numbers quoted in YAML. Both the length check and the
    `low >= high` ORDER check pass for ['40', '400'] because the strings sort that way,
    so the bad config used to be accepted silently and only failed later, at the moment a
    glucose reading was compared against a string."""
    base_config["streams"]["documented_range_mgdl"]["dexcom"] = ["40", "400"]

    with pytest.raises(ConfigError, match="must be numbers"):
        validate_config(base_config)


def test_non_numeric_range_bounds_are_rejected(base_config):
    base_config["streams"]["documented_range_mgdl"]["dexcom"] = ["a", "z"]

    with pytest.raises(ConfigError, match="must be numbers"):
        validate_config(base_config)


def test_boolean_range_bounds_are_rejected(base_config):
    """bool is a subclass of int in Python, so True/False would otherwise pass as numbers."""
    base_config["streams"]["documented_range_mgdl"]["dexcom"] = [False, True]

    with pytest.raises(ConfigError, match="must be numbers"):
        validate_config(base_config)


def test_numeric_range_bounds_are_still_accepted(base_config):
    """The tightening must not reject the legitimate integer and float forms."""
    base_config["streams"]["documented_range_mgdl"]["dexcom"] = [40.5, 400.0]
    validate_config(base_config)

    base_config["streams"]["documented_range_mgdl"]["libre"] = (40, 500)
    validate_config(base_config)
