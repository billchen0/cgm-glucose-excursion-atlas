"""Detector registry.

A detector module provides
* ``detect(times, glucose, params) -> DatetimeIndex`` of detection (onset) times for one
  participant-day series (NaN = missing);
* ``param_grid(cfg) -> list[dict]`` (tuning grid, in tie-break order);
* ``grid_axes(cfg) -> {param: np.ndarray}`` (grid values per parameter, for edge flags);
* optionally ``detect_grid(times, glucose, grid, cfg) -> list[np.ndarray]`` giving, for every
  grid point, the sample indices of the detections (a fast path that must equal ``detect``);
* optionally ``fixed_params(cfg) -> dict`` (settings passed to ``detect`` but not tuned).

Method settings live in ``methods/<name>/configs/*.toml`` under ``[methods.<name>]``
(``sampling_min``, ``grid``, and ``about`` for the protocol README). A method folder may hold
several detectors (``methods/dassau``: dassau_2of3 and dassau_3of4).
"""
from importlib import import_module

from . import REPO

DETECTORS = {"harvey": "methods.harvey.src.harvey",   # module paths from the repo root
             "dassau_2of3": "methods.dassau.src.dassau_2of3",
             "dassau_3of4": "methods.dassau.src.dassau_3of4",
             "samadi": "methods.samadi.src.samadi",
             "faccioli": "methods.faccioli.src.faccioli",
             "turksoy": "methods.turksoy.src.turksoy",
             "popp": "methods.popp.src.popp",
             "lim": "methods.lim.src.lim"}


def get(name):
    return import_module(DETECTORS[name])


def folder(name):
    """Method folder under methods/ (several detectors may share one, e.g. dassau)."""
    return DETECTORS[name].split(".")[1]


def config_paths(name):
    """Method config files, merged over the shared config by ``load_config``."""
    return sorted((REPO / "methods" / folder(name) / "configs").glob("*.toml"))


def fixed_params(name, cfg):
    mod = get(name)
    return mod.fixed_params(cfg) if hasattr(mod, "fixed_params") else {}
