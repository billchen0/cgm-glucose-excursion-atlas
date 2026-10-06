"""Registered detector dassau_3of4 (Hochsmann 2026 Supplementary Table 1, Eq. 6: at least three of BD, BDK, KF, ACC,
at every sample of the 5-min window i, ..., i+4). Shared code: dassau.py."""
from methods.dassau.src import dassau as D

NAME, VARIANT = "dassau_3of4", "3of4"
PARAMS = D.PARAMS[VARIANT]


def grid_axes(cfg):
    return D.grid_axes(cfg, NAME, VARIANT)


def param_grid(cfg):
    return D.param_grid(cfg, NAME, VARIANT)


def fixed_params(cfg):
    return D.fixed_params(cfg, NAME)


def detect(times, glucose, params):
    return D.detect(times, glucose, params, VARIANT)


def detect_grid(times, glucose, cfg):
    return D.detect_grid(times, glucose, cfg, NAME, VARIANT)
