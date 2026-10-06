"""Kalman filters for CGM (shared). ``filter_ca``: continuous white-jerk model (Dassau).
``filter_faccioli``: Faccioli 2022 Eq. 11-12 per-sample model (process noise on the second
derivative only). Both use the same recursion (``_run``).

State x = [glucose, rate of change, acceleration] (mg/dL, mg/dL/min, mg/dL/min^2), one
measurement (glucose). Discrete model for sampling period dt:
  x(k+1) = F x(k) + w(k),  F = [[1, dt, dt^2/2], [0, 1, dt], [0, 0, 1]]
  y(k)   = x0(k) + v(k),   v ~ N(0, meas_sd^2)
w is the discretised continuous white-noise jerk with power spectral density ``jerk_psd``.
The filter restarts at the first valid sample after any missing sample: x = [y, 0, 0],
P = diag(meas_sd^2, p0_rate_sd^2, p0_acc_sd^2). Outputs are NaN at missing samples and for
the first ``warmup_min`` minutes of each run of valid samples.
"""
import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov


def matrices(dt, jerk_psd):
    F = np.array([[1.0, dt, dt * dt / 2], [0.0, 1.0, dt], [0.0, 0.0, 1.0]])
    Q = jerk_psd * np.array([[dt ** 5 / 20, dt ** 4 / 8, dt ** 3 / 6],
                             [dt ** 4 / 8, dt ** 3 / 3, dt ** 2 / 2],
                             [dt ** 3 / 6, dt ** 2 / 2, dt]])
    return F, Q


def filter_ca(glucose, dt, meas_sd, jerk_psd, p0_rate_sd, p0_acc_sd, warmup_min=0):
    """Filtered (glucose, rate, acceleration) arrays, same length as ``glucose``."""
    F, Q = matrices(dt, jerk_psd)
    R = meas_sd ** 2
    P0 = np.diag([R, p0_rate_sd ** 2, p0_acc_sd ** 2])
    return _run(glucose, F, Q, R, P0, int(np.ceil(warmup_min / dt)))


def filter_faccioli(glucose, sigma_w2, sigma_v2, p0_rate_sd, p0_acc_sd, warmup_samples=0):
    """Faccioli 2022 Eqs. 9-12: A = [[1, 1, 0], [0, 1, 1], [0, 0, 1]], C = [0, 0, 1]',
    G = [1, 0, 0], Q = sigma_w2, R = sigma_v2. Time unit = one sample, so the rate is in
    mg/dL per sample and the second derivative in mg/dL per sample^2. Returns (glucose,
    rate, second derivative) per sample; initial state as ``filter_ca``."""
    F = np.array([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0]])
    Cn = np.array([[0.0], [0.0], [1.0]])
    Q = Cn @ Cn.T * sigma_w2
    P0 = np.diag([sigma_v2, p0_rate_sd ** 2, p0_acc_sd ** 2])
    return _run(glucose, F, Q, sigma_v2, P0, int(warmup_samples))


def _run(glucose, F, Q, R, P0, warm):
    """Kalman recursion with glucose measured; restart after missing samples."""
    y = np.asarray(glucose, float)
    n = len(y)
    out = np.full((n, 3), np.nan)
    x = P = None
    start = 0
    for k in range(n):
        if np.isnan(y[k]):
            x = None
            continue
        if x is None:                      # (re)start
            x, P, start = np.array([y[k], 0.0, 0.0]), P0.copy(), k
        else:
            x = F @ x
            P = F @ P @ F.T + Q
            S = P[0, 0] + R
            K = P[:, 0] / S
            x = x + K * (y[k] - x[0])
            P = P - np.outer(K, P[0, :])
        if k - start >= warm:
            out[k] = x
    return out[:, 0], out[:, 1], out[:, 2]


def noise_response_sd(dt, meas_sd, jerk_psd):
    """Steady-state SD of the estimates when the input is white measurement noise only."""
    F, Q = matrices(dt, jerk_psd)
    H = np.array([[1.0, 0.0, 0.0]])
    R = np.array([[meas_sd ** 2]])
    P = solve_discrete_are(F.T, H.T, Q, R)          # steady-state prior covariance
    K = P @ H.T / (P[0, 0] + meas_sd ** 2)
    A = (np.eye(3) - K @ H) @ F
    return np.sqrt(np.diag(solve_discrete_lyapunov(A, K @ R @ K.T)))
