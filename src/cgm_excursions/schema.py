"""Canonical names for every column this package reads or writes.

Keeping them in one module means a consumer never has to guess a spelling, and a
rename is a single edit. The ``qc_`` prefix is reserved: nothing else may use it, so
"which columns are quality flags" is a prefix question with a stable answer.
"""

from __future__ import annotations

# --- identity and time -------------------------------------------------------
SUBJECT_ID = "subject_id"
TIMESTAMP = "timestamp_shifted"
ELAPSED_MINUTES = "elapsed_minutes"

# --- the two glucose streams, exactly as observed ----------------------------
DEXCOM_RAW = "dexcom_glucose_raw"
LIBRE_RAW = "libre_glucose_raw"
DEXCOM_FRESH = "dexcom_glucose_is_fresh"
LIBRE_FRESH = "libre_glucose_is_fresh"

SENSORS: tuple[str, ...] = ("dexcom", "libre")
RAW_COLUMN: dict[str, str] = {"dexcom": DEXCOM_RAW, "libre": LIBRE_RAW}
FRESH_COLUMN: dict[str, str] = {"dexcom": DEXCOM_FRESH, "libre": LIBRE_FRESH}

# --- analysis view (derived from the primary stream) -------------------------
ANALYSIS_GLUCOSE = "analysis_glucose"
ANALYSIS_ON_GRID = "analysis_on_grid"
QC_ELIGIBLE = "qc_eligible"
SEGMENT_ID = "segment_id"

# --- quality flags -----------------------------------------------------------
QC_PREFIX = "qc_"
QC_OUT_OF_RANGE = "qc_out_of_documented_range"
QC_COMPRESSION_LOW = "qc_possible_compression_low"
QC_DUPLICATE_TIMESTAMP = "qc_duplicate_timestamp"
QC_RATE_OF_CHANGE = "qc_rate_of_change"
QC_FLATLINE = "qc_flatline"
QC_ISOLATED_SPIKE = "qc_isolated_spike"

QC_FLAGS: tuple[str, ...] = (
    QC_OUT_OF_RANGE,
    QC_COMPRESSION_LOW,
    QC_DUPLICATE_TIMESTAMP,
    QC_RATE_OF_CHANGE,
    QC_FLATLINE,
    QC_ISOLATED_SPIKE,
)

# Flags that by themselves clear eligibility. Deliberately minimal: a flag whose
# threshold is a screening guess must never silently remove physiology.
HARD_QC_FLAGS: tuple[str, ...] = (QC_DUPLICATE_TIMESTAMP,)

# --- meals -------------------------------------------------------------------
MEAL_TIMESTAMP = "meal_timestamp"
MEAL_TYPE = "meal_type_raw"
MEAL_CALORIES = "calories"
MEAL_CARBS = "carbs_g"
MEAL_PROTEIN = "protein_g"
MEAL_FAT = "fat_g"
MEAL_FIBER = "fiber_g"
MEAL_AMOUNT = "amount_consumed"
MEAL_HAS_COMPLETE_MACROS = "has_complete_macros"

MACRO_COLUMNS: tuple[str, ...] = (MEAL_CALORIES, MEAL_CARBS, MEAL_PROTEIN, MEAL_FAT)

# --- participant metadata ----------------------------------------------------
PARTICIPANT_COLUMNS: tuple[str, ...] = (
    SUBJECT_ID,
    "age",
    "gender",
    "bmi",
    "body_weight_kg",
    "height_cm",
    "self_identified_ethnicity",
    "a1c_percent",
    "a1c_band",
    "fasting_glucose_mgdl",
    "insulin",
    "triglycerides",
    "cholesterol",
    "hdl",
    "non_hdl",
    "ldl_cal",
    "vldl_cal",
    "cho_hdl_ratio",
    "collection_time",
    "has_cgm_data",
    "cgm_row_count",
    "cgm_first_ts",
    "cgm_last_ts",
)

A1C_BANDS: tuple[tuple[str, str, float, bool, float, bool], ...] = (
    # (key, label, lower, lower_inclusive, upper, upper_inclusive)
    #
    # The clinical bands are stated inclusively at both interior edges: 5.7 and 6.4 are
    # themselves the prediabetes range, so a reading of exactly 5.7 is prediabetes (not
    # normal) and a reading of exactly 6.4 is prediabetes (not diabetes). Bands are
    # evaluated in order and the first match wins, which is only unambiguous because the
    # interior edges use closed intervals rather than half-open ones.
    #
    # Matching the published CGMacros cohort counts (15 normal / 16 prediabetes /
    # 14 diabetes) depends on this. An exclusive lower bound moves the three
    # participants reading exactly 5.7 into Normal; an exclusive upper bound moves the
    # one participant reading exactly 6.4 into Diabetes; either gives 15 / 15 / 15.
    ("normal", "Normal", float("-inf"), True, 5.7, False),
    ("prediabetes", "Prediabetes", 5.7, True, 6.4, True),
    ("diabetes", "Diabetes", 6.4, False, float("inf"), True),
)


def a1c_band(a1c_percent: float | None) -> str | None:
    """Published CGMacros cohort band: <5.7 normal, 5.7-6.4 prediabetes, >6.4 diabetes."""
    if a1c_percent is None or a1c_percent != a1c_percent:  # None or NaN
        return None
    value = float(a1c_percent)
    for key, _label, lower, lower_inclusive, upper, upper_inclusive in A1C_BANDS:
        above_lower = value >= lower if lower_inclusive else value > lower
        below_upper = value <= upper if upper_inclusive else value < upper
        if above_lower and below_upper:
            return key
    return None


def canonical_cgm_columns() -> list[str]:
    """The exact column order of ``cgm.parquet``.

    The meal columns are carried here rather than only in ``meals.parquet`` so a
    consumer can call ``extract_meals`` on the canonical frame itself and see a meal's
    macronutrients exactly as observed, including their absence.
    """
    return [
        SUBJECT_ID,
        TIMESTAMP,
        ELAPSED_MINUTES,
        DEXCOM_RAW,
        LIBRE_RAW,
        DEXCOM_FRESH,
        LIBRE_FRESH,
        MEAL_TYPE,
        MEAL_CALORIES,
        MEAL_CARBS,
        MEAL_PROTEIN,
        MEAL_FAT,
        MEAL_FIBER,
        MEAL_AMOUNT,
        ANALYSIS_GLUCOSE,
        ANALYSIS_ON_GRID,
        QC_ELIGIBLE,
        SEGMENT_ID,
        *QC_FLAGS,
    ]
