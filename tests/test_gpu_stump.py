import numpy as np

try:
    import cupy as cp
except ModuleNotFoundError:
    import numpy as cp

    cp.asnumpy = np.asarray
import numpy.testing as npt
import pandas as pd
from stumpy import gpu_stump, _gpu_calculate_squared_distance_profile, core
from stumpy import _calculate_squared_distance_profile
import pytest


def naive_mass(Q, T, m, trivial_idx=None, excl_zone=0, ignore_trivial=False):
    D = np.linalg.norm(
        core.z_norm(core.rolling_window(T, m), 1) - core.z_norm(Q), axis=1
    )
    if ignore_trivial:
        start = max(0, trivial_idx - excl_zone)
        stop = min(T.shape[0] - Q.shape[0] + 1, trivial_idx + excl_zone)
        D[start:stop] = np.inf
    I = np.argmin(D)
    P = D[I]

    # Get left and right matrix profiles for self-joins
    if ignore_trivial and trivial_idx > 0:
        PL = np.inf
        IL = -1
        for i in range(trivial_idx):
            if D[i] < PL:
                IL = i
                PL = D[i]
        if start <= IL < stop:
            IL = -1
    else:
        IL = -1

    if ignore_trivial and trivial_idx + 1 < D.shape[0]:
        PR = np.inf
        IR = -1
        for i in range(trivial_idx + 1, D.shape[0]):
            if D[i] < PR:
                IR = i
                PR = D[i]
        if start <= IR < stop:
            IR = -1
    else:
        IR = -1

    return P, I, IL, IR


def replace_inf(x, value=0):
    x[x == np.inf] = value
    x[x == -np.inf] = value
    return


test_data = [
    (
        np.array([9, 8100, -60, 7], dtype=np.float64),
        np.array([584, -11, 23, 79, 1001, 0, -19], dtype=np.float64),
    ),
    (
        np.random.uniform(-1000, 1000, [8]).astype(np.float64),
        np.random.uniform(-1000, 1000, [64]).astype(np.float64),
    ),
]


@pytest.mark.parametrize("Q, T", test_data)
def test_gpu_calculate_squared_distance_profile(Q, T):
    m = Q.shape[0]
    left = np.linalg.norm(
        core.z_norm(core.rolling_window(T, m), 1) - core.z_norm(Q), axis=1
    )
    left = np.square(left)
    M_T, Σ_T = core.compute_mean_std(T, m)
    QT = core.sliding_dot_product(Q, T)
    μ_Q, σ_Q = core.compute_mean_std(Q, m)
    QT = cp.asarray(QT)
    μ_Q = cp.asarray(μ_Q)
    σ_Q = cp.asarray(σ_Q)
    M_T = cp.asarray(M_T)
    Σ_T = cp.asarray(Σ_T)
    right = _gpu_calculate_squared_distance_profile(m, QT, μ_Q[0], σ_Q[0], M_T, Σ_T)
    right = cp.asnumpy(right)
    npt.assert_almost_equal(left, right)


@pytest.mark.parametrize("T_A, T_B", test_data)
def test_stump_self_join(T_A, T_B):
    m = 3
    zone = int(np.ceil(m / 4))
    left = np.array(
        [
            naive_mass(Q, T_B, m, i, zone, True)
            for i, Q in enumerate(core.rolling_window(T_B, m))
        ],
        dtype=object,
    )
    right = gpu_stump(T_B, m, ignore_trivial=True)
    replace_inf(left)
    replace_inf(right)
    npt.assert_almost_equal(left, right)

    right = gpu_stump(pd.Series(T_B), m, ignore_trivial=True)
    replace_inf(right)
    npt.assert_almost_equal(left, right)


@pytest.mark.parametrize("T_A, T_B", test_data)
def test_stump_A_B_join(T_A, T_B):
    m = 3
    left = np.array(
        [naive_mass(Q, T_A, m) for Q in core.rolling_window(T_B, m)], dtype=object
    )
    right = gpu_stump(T_A, m, T_B, ignore_trivial=False)
    replace_inf(left)
    replace_inf(right)
    npt.assert_almost_equal(left, right)

    right = gpu_stump(pd.Series(T_A), m, pd.Series(T_B), ignore_trivial=False)
    replace_inf(right)
    npt.assert_almost_equal(left, right)
