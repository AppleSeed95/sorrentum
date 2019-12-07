"""
Import as:

import core.signal_processing as sigp
"""

import functools
import logging
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pywt
import scipy as sp
import statsmodels.api as sm

import helpers.dbg as dbg

_LOG = logging.getLogger(__name__)


# #############################################################################
# Graphical tools for time and frequency analysis
# #############################################################################

# Some use cases include:
#   - Determining whether a predictor exhibits autocorrelation
#   - Determining the characteristic time scale of a signal
#   - Signal filtering
#   - Lag determination
#   - etc.


def plot_autocorrelation(
    signal: Union[pd.DataFrame, pd.Series],
    lags: int = 40,
    scale_mode: str = "auto",
) -> None:
    """
    Plot autocorrelation and partial autocorrelation of series.
    """
    dbg.dassert_lte(1, lags)
    fig = plt.figure(figsize=(12, 8))
    if scale_mode == "auto":
        pass
    elif scale_mode == "fixed":
        plt.ylim(-1, 1)
    else:
        raise ValueError("scale_mode='%s' is not supported" % scale_mode)
    ax1 = fig.add_subplot(211)
    # Exclude lag zero so that the y-axis does not get squashed.
    fig = sm.graphics.tsa.plot_acf(signal, lags=lags, ax=ax1, zero=False)
    ax2 = fig.add_subplot(212)
    fig = sm.graphics.tsa.plot_pacf(signal, lags=lags, ax=ax2, zero=False)


def plot_power_spectral_density(signal: Union[pd.DataFrame, pd.Series]) -> None:
    """
    Estimate the power spectral density using Welch's method.

    Related to autocorrelation via the Fourier transform (Wiener-Khinchin).
    """
    freqs, psd = sp.signal.welch(signal)
    plt.figure(figsize=(5, 4))
    plt.semilogx(freqs, psd)
    plt.title("PSD: power spectral density")
    plt.xlabel("Frequency")
    plt.ylabel("Power")
    plt.tight_layout()


def plot_spectrogram(signal: Union[pd.DataFrame, pd.Series]) -> None:
    """
    Plot spectrogram of signal.

    From the scipy documentation of spectrogram:
        "Spectrograms can be used as a way of visualizing the change of a
         nonstationary signal's frequency content over time."
    """
    _, _, spectrogram = sp.signal.spectrogram(signal)
    plt.figure(figsize=(5, 4))
    plt.imshow(spectrogram, aspect="auto", cmap="hot_r", origin="lower")
    plt.title("Spectrogram")
    plt.ylabel("Frequency band")
    plt.xlabel("Time window")
    plt.tight_layout()


def plot_wavelet_levels(
    signal: Union[pd.DataFrame, pd.Series], wavelet_name: str, levels: int
) -> None:
    """
    Wavelet level decomposition plot. Higher levels are smoother.

    :param signal: Series-like numerical object
    :param wavelet_name: One of the names in pywt.wavelist()
    :param levels: The number of levels to plot
    """
    _, ax = plt.subplots(figsize=(6, 1))
    ax.set_title("Original signal")
    ax.plot(signal)
    plt.show()

    data = signal.copy()
    _, axarr = plt.subplots(nrows=levels, ncols=2, figsize=(6, 6))
    for idx in range(levels):
        (data, coeff_d) = pywt.dwt(data, wavelet_name)
        axarr[idx, 0].plot(data, "r")
        axarr[idx, 1].plot(coeff_d, "g")
        axarr[idx, 0].set_ylabel(
            "Level {}".format(idx + 1), fontsize=14, rotation=90
        )
        axarr[idx, 0].set_yticklabels([])
        if idx == 0:
            axarr[idx, 0].set_title("Approximation coefficients", fontsize=14)
            axarr[idx, 1].set_title("Detail coefficients", fontsize=14)
        axarr[idx, 1].set_yticklabels([])
    plt.tight_layout()
    plt.show()


def low_pass_filter(
    signal: Union[pd.DataFrame, pd.Series], wavelet_name: str, threshold: float
) -> pd.Series:
    """
    Wavelet low-pass filtering using a threshold.

    Currently configured to use 'periodic' mode.
    See https://pywavelets.readthedocs.io/en/latest/regression/modes.html.
    Uses soft thresholding.

    :param signal: Signal as pd.Series
    :param wavelet_name: One of the names in pywt.wavelist()
    :param threshold: Coefficient threshold (>= passes)

    :return: Smoothed signal as pd.Series, indexed like signal.index
    """
    threshold = threshold * np.nanmax(signal)
    coeff = pywt.wavedec(signal, wavelet_name, mode="per")
    coeff[1:] = (
        pywt.threshold(i, value=threshold, mode="soft") for i in coeff[1:]
    )
    rec = pywt.waverec(coeff, wavelet_name, mode="per")
    if rec.size > signal.size:
        rec = rec[1:]
    reconstructed_signal = pd.Series(rec, index=signal.index)
    return reconstructed_signal


def plot_low_pass(
    signal: Union[pd.DataFrame, pd.Series], wavelet_name: str, threshold: float
) -> None:
    """
    Overlay signal with result of low_pass_filter().
    """
    _, ax = plt.subplots(figsize=(12, 8))
    ax.plot(signal, color="b", alpha=0.5, label="original signal")
    rec = low_pass_filter(signal, wavelet_name, threshold)
    ax.plot(rec, "k", label="DWT smoothing}", linewidth=2)
    ax.legend()
    ax.set_title("Removing High Frequency Noise with DWT", fontsize=18)
    ax.set_ylabel("Signal Amplitude", fontsize=16)
    ax.set_xlabel("Sample", fontsize=16)
    plt.show()


def plot_scaleogram(
    signal: Union[pd.DataFrame, pd.Series],
    scales: np.array,
    wavelet_name: str,
    cmap: plt.cm = plt.cm.seismic,
    title: str = "Wavelet Spectrogram of signal",
    ylabel: str = "Period",
    xlabel: str = "Time",
) -> None:
    r"""
    Plot wavelet-based spectrogram (aka scaleogram).

    A nice reference and utility for plotting can be found at
    https://github.com/alsauve/scaleogram.

    Also see:
    https://github.com/PyWavelets/pywt/blob/master/demo/wp_scalogram.py.

    :param signal: signal to transform
    :param scales: numpy array, e.g., np.arange(1, 128)
    :param wavelet_name: continuous wavelet, e.g., 'cmor' or 'morl'
    """
    time = np.arange(0, signal.size)
    dt = time[1] - time[0]
    [coeffs, freqs] = pywt.cwt(signal, scales, wavelet_name, dt)
    power = np.abs(coeffs) ** 2
    periods = 1.0 / freqs
    levels = [0.0625, 0.125, 0.25, 0.5, 1, 2, 4, 8]
    contour_levels = np.log2(levels)

    fig, ax = plt.subplots(figsize=(15, 10))
    im = ax.contourf(
        time,
        np.log2(periods),
        np.log2(power),
        contour_levels,
        extend="both",
        cmap=cmap,
    )

    ax.set_title(title, fontsize=20)
    ax.set_ylabel(ylabel, fontsize=18)
    ax.set_xlabel(xlabel, fontsize=18)

    yticks = 2 ** np.arange(
        np.ceil(np.log2(periods.min())), np.ceil(np.log2(periods.max()))
    )
    ax.set_yticks(np.log2(yticks))
    ax.set_yticklabels(yticks)
    ax.invert_yaxis()
    ylim = ax.get_ylim()
    ax.set_ylim(ylim[0], -1)

    cbar_ax = fig.add_axes([0.95, 0.5, 0.03, 0.25])
    fig.colorbar(im, cax=cbar_ax, orientation="vertical")
    plt.show()


# #############################################################################
# Basic modeling
# #############################################################################


def fit_random_walk_plus_noise(
    signal: Union[pd.DataFrame, pd.Series]
) -> Tuple[sm.tsa.UnobservedComponents, sm.tsa.statespace.MLEResults]:
    """
    Fit a random walk + Gaussian noise model using state space methods.

    After convergence the resulting model is equivalent to exponential
    smoothing. Using the state space approach we can
      - Calculate the signal-to-noise ratio
      - Determine an optimal (under model assumptions) ewma com
      - Analyze residuals

    :return: SSM model and fitted result
    """
    model = sm.tsa.UnobservedComponents(
        signal, level="local level", initialization="diffuse"
    )
    result = model.fit(method="powell", disp=True)
    # Signal-to-noise ratio.
    q = result.params[1] / result.params[0]
    _LOG.info("Signal-to-noise ratio q = %f", q)
    p = 0.5 * (q + np.sqrt(q ** 2 + 4 * q))
    kalman_gain = p / (p + 1)
    _LOG.info("Steady-state Kalman gain = %f", kalman_gain)
    # EWMA com.
    com = 1 / kalman_gain - 1
    _LOG.info("EWMA com = %f", com)
    print(result.summary())
    result.plot_diagnostics()
    result.plot_components(legend_loc="lower right", figsize=(15, 9))
    return model, result


# #############################################################################
# Multisignal or predictor/response functions
# #############################################################################


def plot_crosscorrelation(
    x: Union[pd.DataFrame, pd.Series], y: Union[pd.DataFrame, pd.Series]
) -> None:
    r"""
    Assume x, y have been approximately demeaned and normalized (e.g.,
    z-scored with ewma).

    At index `k` in the result, the value is given by
        (1 / n) * \sum_{l = 0}^{n - 1} x_l * y_{l + k}
    """
    joint_idx = x.index.intersection(y.index)
    corr = sp.signal.correlate(x.loc[joint_idx], y.loc[joint_idx])
    # Normalize by number of points in series (e.g., take expectations)
    n = joint_idx.size
    corr /= n
    step_idx = pd.RangeIndex(-1 * n + 1, n)
    pd.Series(data=corr, index=step_idx).plot()


# TODO(Paul): Add coherence plotting function.


# #############################################################################
# Metrics
# #############################################################################


def compute_forecastability(signal: pd.Series, mode: str = "welch") -> float:
    r"""
    Compute frequency-domain-based "forecastability" of signal.

    Reference: https://arxiv.org/abs/1205.4591

    `signal` is assumed to be second-order stationary.

    Denote the forecastability estimator by \Omega(\cdot).
    Let x_t, y_t be time series. Properties of \Omega include:
    a) \Omega(y_t) = 0 iff y_t is white noise
    b) scale and shift-invariant:
         \Omega(a y_t + b) = \Omega(y_t) for real a, b, a \neq 0.
    c) max sub-additivity for uncorrelated processes:
         \Omega(\alpha x_t + \sqrt{1 - \alpha^2} y_t) \leq
         \max\{\Omega(x_t), \Omega(y_t)\},
       if \E(x_t y_s) = 0 for all s, t \in \Z;
       equality iff alpha \in \{0, 1\}.
    """
    dbg.dassert_isinstance(signal, pd.Series)
    dbg.dassert_isinstance(mode, str)
    if mode == "welch":
        _, psd = sp.signal.welch(signal)
    elif mode == "periodogram":
        # TODO(Paul): Maybe log a warning about inconsistency of periodogram
        #     for estimating power spectral density.
        _, psd = sp.signal.periodogram(signal)
    else:
        raise ValueError("Unsupported mode=`%s`" % mode)
    forecastability = 1 - sp.stats.entropy(psd, base=psd.size)
    return forecastability


# #############################################################################
# Signal transformations
# #############################################################################


def squash(
    signal: Union[pd.DataFrame, pd.Series], scale: int = 1
) -> Union[pd.DataFrame, pd.Series]:
    """
    Apply squashing function to data.

    :param signal: data
    :param scale: Divide data by scale and multiply squashed output by scale.
        Rescaling approximately preserves behavior in a neighborhood of the
        origin where the squashing function is approximately linear.
    :return: squashed data
    """
    dbg.dassert_lt(0, scale)
    return scale * np.tanh(signal / scale)


def get_symmetric_equisized_bins(
    signal: pd.Series, bin_size: float, zero_in_bin_interior: bool = False
) -> np.array:
    """
    Get bins of equal size, symmetric about zero, adapted to `signal`.

    :param bin_size: width of bin
    :param zero_in_bin_interior: Determines whether `0` is a bin edge or not.
        If in interior, it is placed in the center of the bin.
    :return: array of bin boundaries
    """
    # Remove +/- inf for the purpose of calculating max/min.
    finite_signal = signal.replace([-np.inf, np.inf], np.nan).dropna()
    # Determine minimum and maximum bin boundaries based on values of `signal`.
    # Make them symmetric for simplicity.
    left = np.floor(finite_signal.min() / bin_size).astype(int) - 1
    right = np.ceil(finite_signal.max() / bin_size).astype(int) + 1
    bin_boundary = bin_size * np.maximum(np.abs(left), np.abs(right))
    if zero_in_bin_interior:
        right_start = bin_size / 2
    else:
        right_start = 0
    right_bins = np.arange(right_start, bin_boundary, bin_size)
    # Reflect `right_bins` to get `left_bins`.
    if zero_in_bin_interior:
        left_bins = -np.flip(right_bins)
    else:
        left_bins = -np.flip(right_bins[1:])
    # Combine `left_bins` and `right_bin` into one bin.
    return np.append(left_bins, right_bins)


def digitize(signal: pd.Series, bins: np.array, right: bool = False) -> pd.Series:
    """
    Digitize (i.e., discretize) `signal` into `bins`.

    - In the output, bins are referenced with integers and are such that `0`
      always belongs to bin `0`
    - The bin-referencing convention is optimized for studying signals centered
      at zero (e.g., returns, z-scored features, etc.)
    - For bins of equal size, the bin-referencing convention makes it easy to
      map back from the digitized signal to numerical ranges given
        - the bin number
        - the bin size

    :param bins: array-like bin boundaries. Must include max and min `signal`
        values.
    :param right: same as in `np.digitize`
    :return: digitized signal
    """
    # From https://docs.scipy.org/doc/numpy/reference/generated/numpy.digitize.html
    # (v 1.17):
    # > If values in x are beyond the bounds of bins, 0 or len(bins) is
    # > returned as appropriate.
    digitized = np.digitize(signal, bins, right)
    # Center so that `0` belongs to bin "0"
    bin_containing_zero = np.digitize([0], bins, right)
    digitized -= bin_containing_zero
    # Convert to pd.Series, since `np.digitize` only returns an np.array.
    digitized_srs = pd.Series(
        data=digitized, index=signal.index, name=signal.name
    )
    return digitized_srs


def _wrap(signal: pd.Series, num_cols: int) -> pd.DataFrame:
    """
    Convert a 1-d series into a 2-d dataframe left-to-right top-to-bottom.

    :param num_cols: number of columns to use for wrapping
    """
    dbg.dassert_isinstance(signal, pd.Series)
    dbg.dassert_lte(1, num_cols)
    values = signal.values
    _LOG.debug("num values=%d", values.size)
    # Calculate number of rows that wrapped pd.DataFrame should have.
    num_rows = np.ceil(values.size / num_cols).astype(int)
    _LOG.debug("num_rows=%d", num_rows)
    # Add padding, since numpy's `reshape` requires element counts to match
    # exactly.
    pad_size = num_rows * num_cols - values.size
    _LOG.debug("pad_size=%d", pad_size)
    padding = np.full(pad_size, np.nan)
    padded_values = np.append(values, padding)
    #
    wrapped = padded_values.reshape(num_rows, num_cols)
    return pd.DataFrame(wrapped)


def _unwrap(df: pd.DataFrame, idx: pd.Index, name: Optional[Any] = None):
    """
    Undo `_wrap`.

    We allow `index.size` to be less than nrows * ncols of `df`, in which case
    values are truncated from the end of the unwrapped dataframe.

    :param idx: index of series provided to `_wrap` call
    """
    _LOG.debug("df.shape=%s", df.shape)
    values = df.values.flatten()
    pad_size = values.size - idx.size
    _LOG.debug("pad_size=%d", pad_size)
    if pad_size > 0:
        data = values[:-pad_size]
    else:
        data = values
    unwrapped = pd.Series(data=data, index=idx, name=name)
    return unwrapped


def skip_apply_func(
    signal: pd.DataFrame,
    skip_size: int,
    func: Callable[[pd.Series], pd.DataFrame],
    **kwargs
) -> pd.DataFrame:
    """
    Apply `func` to each col of `signal` after a wrap, then unwrap and merge.

    :param skip_size: num_cols used for wrapping each col of `signal`
    :param kwargs: forwarded to `func`
    """
    cols = {}
    for col in signal.columns:
        wrapped = _wrap(signal[col], skip_size)
        funced = func(wrapped, **kwargs)
        unwrapped = _unwrap(funced, signal.index, col)
        cols[col] = unwrapped
    df = pd.DataFrame.from_dict(cols)
    return df


# #############################################################################
# EMAs and derived kernels
# #############################################################################


def _com_to_tau(com: float) -> float:
    """
    Transform center-of-mass (com) into tau parameter.

    This is the function inverse of `_tau_to_com`.
    """
    dbg.dassert_lt(0, com)
    return 1.0 / np.log(1 + 1.0 / com)


def _tau_to_com(tau: float) -> float:
    """
    Transform tau parameter into center-of-mass (com).

    We use the tau parameter for kernels (as in Dacorogna, et al), but for the
    ema operator want to take advantage of pandas' implementation, which uses
    different parameterizations. We adopt `com` because
        - It is almost equal to `tau`
        - We have used it historically

    :param tau: parameter used in (continuous) ema and ema-derived kernels. For
        typical ranges it is approximately but not exactly equal to the
        center-of-mass (com) associated with an ema kernel.
    :return: com
    """
    dbg.dassert_lt(0, tau)
    return 1.0 / (np.exp(1.0 / tau) - 1)


def ema(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int,
    depth: int = 1,
) -> Union[pd.DataFrame, pd.Series]:
    r"""
    Implement iterated EMA operator (e.g., see 3.3.6 of Dacorogna, et al).

    depth=1 corresponds to a single application of exponential smoothing.

    Greater depth tempers impulse response, introducing a phase lag.

    Dacorogna use the convention $\text{ema}(t) = \exp(-t / \tau) / \tau$.

    If $s_n = \lambda x_n + (1 - \lambda) s_{n - 1}$, where $s_n$ is the ema
    output, then $1 - \lambda = \exp(-1 / \tau)$. Now
    $\lambda = 1 / (1 + \text{com})$, and rearranging gives
    $\log(1 + 1 / \text{com}) = 1 / \tau$. Expanding in a Taylor series
    leads to $\tau \approx \text{com}$.

    The kernel for an ema of depth $n$ is
    $(1 / (n - 1)!) (t / \tau)^{n - 1} \exp^{-t / \tau} / \tau$.

    Arbitrary kernels can be approximated by a combination of iterated emas.

    For an iterated ema with given tau and depth n, we have
      - range = n \tau
      - <t^2> = n(n + 1) \tau^2
      - width = \sqrt{n} \tau
      - aspect ratio = \sqrt{1 + 1 / n}
    """
    dbg.dassert_isinstance(depth, int)
    dbg.dassert_lte(1, depth)
    dbg.dassert_lt(0, tau)
    _LOG.debug("Calculating iterated ema of depth %i", depth)
    _LOG.debug("range = %0.2f", depth * tau)
    _LOG.debug("<t^2>^{1/2} = %0.2f", np.sqrt(depth * (depth + 1)) * tau)
    _LOG.debug("width = %0.2f", np.sqrt(depth) * tau)
    _LOG.debug("aspect ratio = %0.2f", np.sqrt(1 + 1.0 / depth))
    _LOG.debug("tau = %0.2f", tau)
    com = _tau_to_com(tau)
    _LOG.debug("com = %0.2f", com)
    signal_hat = signal.copy()
    for i in range(0, depth):
        signal_hat = signal_hat.ewm(
            com=com, min_periods=min_periods, adjust=True, ignore_na=False, axis=0
        ).mean()
    return signal_hat


def smooth_derivative(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int,
    scaling: int = 0,
    order: int = 1,
) -> Union[pd.DataFrame, pd.Series]:
    r"""
    'Low-noise' differential operator as in 3.3.9 of Dacorogna, et al.

    Compute difference of around time "now" over a time interval \tau_1
    and an average around time "now - \tau" over a time interval \tau_2.
    Here, \tau_1, \tau_2 are taken to be approximately \tau / 2.

    The normalization factors are chosen so that the differential of a constant
    is zero and so that the differential of 't' is approximately \tau (for
    order = 0).

    The `scaling` parameter refers to the exponential weighting of inverse
    tau.

    The `order` parameter refers to the number of times the smooth_derivative operator
    is applied to the original signal.
    """
    dbg.dassert_isinstance(order, int)
    dbg.dassert_lte(0, order)
    gamma = 1.22208
    beta = 0.65
    alpha = 1.0 / (gamma * (8 * beta - 3))
    _LOG.debug("alpha = %0.2f", alpha)
    tau1 = alpha * tau
    _LOG.debug("tau1 = %0.2f", tau1)
    tau2 = alpha * beta * tau
    _LOG.debug("tau2 = %0.2f", tau2)

    def order_one(
        signal: Union[pd.DataFrame, pd.Series]
    ) -> Union[pd.DataFrame, pd.Series]:
        s1 = ema(signal, tau1, min_periods, 1)
        s2 = ema(signal, tau1, min_periods, 2)
        s3 = -2.0 * ema(signal, tau2, min_periods, 4)
        differential = gamma * (s1 + s2 + s3)
        if scaling == 0:
            return differential
        return differential / (tau ** scaling)

    signal_diff = signal.copy()
    for _ in range(0, order):
        signal_diff = order_one(signal_diff)
    return signal_diff


def smooth_moving_average(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Implement moving average operator defined in terms of iterated ema's.
    Choosing min_depth > 1 results in a lagged operator.
    Choosing min_depth = max_depth = 1 reduces to a single ema.

    Abrupt impulse response that tapers off smoothly like a sigmoid
    (hence smoother than an equally-weighted moving average).

    For min_depth = 1 and large max_depth, the series is approximately
    constant for t << 2 * range_. In particular, when max_depth >= 5,
    the kernels are more rectangular than ema-like.
    """
    dbg.dassert_isinstance(min_depth, int)
    dbg.dassert_isinstance(max_depth, int)
    dbg.dassert_lte(1, min_depth)
    dbg.dassert_lte(min_depth, max_depth)
    range_ = tau * (min_depth + max_depth) / 2.0
    _LOG.debug("Range = %0.2f", range_)
    ema_eval = functools.partial(ema, signal, tau, min_periods)
    denom = float(max_depth - min_depth + 1)
    # Not the most efficient implementation, but follows 3.56 of Dacorogna
    # directly.
    return sum(map(ema_eval, range(min_depth, max_depth + 1))) / denom


# #############################################################################
# Rolling moments, norms, z-scoring, demeaning, etc.
# #############################################################################


def rolling_moment(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    return smooth_moving_average(
        np.abs(signal) ** p_moment, tau, min_periods, min_depth, max_depth
    )


def rolling_norm(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Implement smooth moving average norm (when p_moment >= 1).

    Moving average corresponds to ema when min_depth = max_depth = 1.
    """
    signal_p = rolling_moment(
        signal, tau, min_periods, min_depth, max_depth, p_moment
    )
    return signal_p ** (1.0 / p_moment)


def rolling_var(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Implement smooth moving average central moment.

    Moving average corresponds to ema when min_depth = max_depth = 1.
    """
    signal_ma = smooth_moving_average(
        signal, tau, min_periods, min_depth, max_depth
    )
    return rolling_moment(
        signal - signal_ma, tau, min_periods, min_depth, max_depth, p_moment
    )


def rolling_std(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Implement normalized smooth moving average central moment.

    Moving average corresponds to ema when min_depth = max_depth = 1.
    """
    signal_tmp = rolling_var(
        signal, tau, min_periods, min_depth, max_depth, p_moment
    )
    return signal_tmp ** (1.0 / p_moment)


def rolling_demean(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Demean signal on a rolling basis with smooth_moving_average.
    """
    signal_ma = smooth_moving_average(
        signal, tau, min_periods, min_depth, max_depth
    )
    return signal - signal_ma


def rolling_zscore(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
    demean: bool = True,
    delay: int = 0,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Z-score using smooth_moving_average and rolling_std.

    If delay > 0, then pay special attention to 0 and NaN handling to avoid
    extreme values.

    Moving average corresponds to ema when min_depth = max_depth = 1.

    TODO(Paul): determine whether signal == signal.shift(0) always.
    """
    if demean:
        # Equivalent to invoking rolling_demean and rolling_std, but this way
        # we avoid calculating signal_ma twice.
        signal_ma = smooth_moving_average(
            signal, tau, min_periods, min_depth, max_depth
        )
        signal_std = rolling_norm(
            signal - signal_ma, tau, min_periods, min_depth, max_depth, p_moment
        )
        ret = (signal - signal_ma.shift(delay)) / signal_std.shift(delay)

    else:
        signal_std = rolling_norm(
            signal, tau, min_periods, min_depth, max_depth, p_moment
        )
        ret = signal / signal_std.shift(delay)
    return ret


def rolling_skew(
    signal: Union[pd.DataFrame, pd.Series],
    tau_z: float,
    tau_s: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Smooth moving average skew of z-scored signal.
    """
    z_signal = rolling_zscore(
        signal, tau_z, min_periods, min_depth, max_depth, p_moment
    )
    skew = smooth_moving_average(
        z_signal ** 3, tau_s, min_periods, min_depth, max_depth
    )
    return skew


def rolling_kurtosis(
    signal: Union[pd.DataFrame, pd.Series],
    tau_z: float,
    tau_s: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Smooth moving average kurtosis of z-scored signal.
    """
    z_signal = rolling_zscore(
        signal, tau_z, min_periods, min_depth, max_depth, p_moment
    )
    kurt = smooth_moving_average(
        z_signal ** 4, tau_s, min_periods, min_depth, max_depth
    )
    return kurt


# #############################################################################
# Rolling Sharpe ratio
# #############################################################################


def rolling_sharpe_ratio(
    signal: Union[pd.DataFrame, pd.Series],
    tau: float,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Sharpe ratio using smooth_moving_average and rolling_std.
    """
    signal_ma = smooth_moving_average(
        signal, tau, min_periods, min_depth, max_depth
    )
    signal_std = rolling_norm(
        signal - signal_ma, tau, min_periods, min_depth, max_depth, p_moment
    )
    # TODO(Paul): Annualize appropriately.
    return signal_ma / signal_std


# #############################################################################
# Rolling correlation functions
# #############################################################################


def rolling_corr(
    srs1: Union[pd.DataFrame, pd.Series],
    srs2: Union[pd.DataFrame, pd.Series],
    tau: float,
    demean: bool = True,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Smooth moving correlation.

    """
    if demean:
        srs1_adj = srs1 - smooth_moving_average(
            srs1, tau, min_periods, min_depth, max_depth
        )
        srs2_adj = srs2 - smooth_moving_average(
            srs2, tau, min_periods, min_depth, max_depth
        )
    else:
        srs1_adj = srs1
        srs2_adj = srs2

    smooth_prod = smooth_moving_average(
        srs1_adj.multiply(srs2_adj), tau, min_periods, max_depth
    )
    srs1_std = rolling_norm(
        srs1_adj, tau, min_periods, min_depth, max_depth, p_moment
    )
    srs2_std = rolling_norm(
        srs2_adj, tau, min_periods, min_depth, max_depth, p_moment
    )
    return smooth_prod / (srs1_std * srs2_std)


def rolling_zcorr(
    srs1: Union[pd.DataFrame, pd.Series],
    srs2: Union[pd.DataFrame, pd.Series],
    tau: float,
    demean: bool = True,
    min_periods: int = 0,
    min_depth: int = 1,
    max_depth: int = 1,
    p_moment: float = 2,
) -> Union[pd.DataFrame, pd.Series]:
    """
    Z-score srs1, srs2 then calculate moving average of product.

    Not guaranteed to lie in [-1, 1], but bilinear in the z-scored variables.
    """
    if demean:
        z_srs1 = rolling_zscore(
            srs1, tau, min_periods, min_depth, max_depth, p_moment
        )
        z_srs2 = rolling_zscore(
            srs2, tau, min_periods, min_depth, max_depth, p_moment
        )
    else:
        z_srs1 = srs1 / rolling_norm(
            srs1, tau, min_periods, min_depth, max_depth, p_moment
        )
        z_srs2 = srs2 / rolling_norm(
            srs2, tau, min_periods, min_depth, max_depth, p_moment
        )
    return smooth_moving_average(
        z_srs1.multiply(z_srs2), tau, min_depth, max_depth
    )


# #############################################################################
# Outlier handling.
# #############################################################################


def process_outliers(
    srs: pd.Series,
    mode: str,
    lower_quantile: float,
    upper_quantile: Optional[float] = None,
    info: Optional[dict] = None,
) -> pd.Series:
    """
    Process outliers in different ways given lower / upper quantiles.

    :param srs: pd.Series to process
    :param lower_quantile: lower quantile (in range [0, 1]) of the values to keep
        The interval of data kept without any changes is [lower, upper]. In other
        terms the outliers with quantiles strictly smaller and larger than the
        respective bounds are processed.
    :param upper_quantile: upper quantile with the same semantic as
        lower_quantile. If `None`, the quantile symmetric of the lower quantile
        with respect to 0.5 is taken. E.g., an upper quantile equal to 0.7 is
        taken for a lower_quantile = 0.3
    :param mode: it can be "winsorize", "set_to_nan", "set_to_zero"
    :param info: empty dict-like object that this function will populate with
        statistics about the performed operation

    :return: transformed series with the same number of elements as the input
        series. The operation is not in place.
    """
    # Check parameters.
    dbg.dassert_isinstance(srs, pd.Series)
    dbg.dassert_lte(0.0, lower_quantile)
    if upper_quantile is None:
        upper_quantile = 1.0 - lower_quantile
    dbg.dassert_lte(lower_quantile, upper_quantile)
    dbg.dassert_lte(upper_quantile, 1.0)
    # Compute bounds.
    bounds = np.quantile(srs, [lower_quantile, upper_quantile])
    _LOG.debug(
        "Removing outliers in [%s, %s] -> %s with mode=%s",
        lower_quantile,
        upper_quantile,
        bounds,
        mode,
    )
    # Compute stats.
    if info is not None:
        dbg.dassert_isinstance(info, dict)
        # Dictionary should be empty.
        dbg.dassert(not info)
        info["series_name"] = srs.name
        info["num_elems_before"] = len(srs)
        info["num_nans_before"] = np.isnan(srs).sum()
        info["num_infs_before"] = np.isinf(srs).sum()
        info["quantiles"] = (lower_quantile, upper_quantile)
        info["mode"] = mode
    #
    srs = srs.copy()
    # Here we implement the functions instead of using library functions (e.g,
    # `scipy.stats.mstats.winsorize`) since we want to compute some statistics
    # that are not readily available from the library function.
    l_mask = srs < bounds[0]
    u_mask = bounds[1] < srs
    if mode == "winsorize":
        # Assign the outliers to the value of the bounds.
        srs[l_mask] = bounds[0]
        srs[u_mask] = bounds[1]
    else:
        mask = u_mask | l_mask
        if mode == "set_to_nan":
            srs[mask] = np.nan
        elif mode == "set_to_zero":
            srs[mask] = 0.0
        else:
            dbg.dfatal("Invalid mode='%s'" % mode)
    # Append more the stats.
    if info is not None:
        info["bounds"] = bounds
        num_removed = np.sum(l_mask) + np.sum(u_mask)
        info["num_elems_removed"] = num_removed
        info["num_elems_after"] = (
            info["num_elems_before"] - info["num_elems_removed"]
        )
        info["percentage_removed"] = (
            100.0 * info["num_elems_removed"] / info["num_elems_before"]
        )
        info["num_nans_after"] = np.isnan(srs).sum()
        info["num_infs_after"] = np.isinf(srs).sum()
    return srs


def process_outlier_df(
    df: pd.DataFrame,
    mode: str,
    lower_quantile: float,
    upper_quantile: Optional[float] = None,
    info: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Extend `process_outliers` to dataframes.

    TODO(*): Revisit this with a decorator approach:
    https://github.com/ParticleDev/commodity_research/issues/568
    """
    if info is not None:
        dbg.dassert_isinstance(info, dict)
        # Dictionary should be empty.
        dbg.dassert(not info)
    cols = {}
    for col in df.columns:
        if info is not None:
            maybe_stats = {}
        else:
            maybe_stats = None
        srs = process_outliers(
            df[col], mode, lower_quantile, upper_quantile, maybe_stats
        )
        cols[col] = srs
        if info is not None:
            info[col] = maybe_stats
    ret = pd.DataFrame.from_dict(cols)
    # Check that the columns are the same. We don't use dassert_eq because of
    # #665.
    dbg.dassert(
        all(df.columns == ret.columns),
        "Columns are different:\ndf.columns=%s\nret.columns=%s",
        str(df.columns),
        str(ret.columns),
    )
    return ret


# #############################################################################
# Incremental PCA
# #############################################################################


def ipca_step(
    u: pd.Series, v: pd.Series, alpha: float
) -> Tuple[pd.Series, pd.Series]:
    """
    Single step of incremental PCA.

    At each point, the norm of v is the eigenvalue estimate (for the component
    to which u and v refer).

    :param u: residualized observation for step n, component i
    :param v: unnormalized eigenvector estimate for step n - 1, component i
    :param alpha: ema-type weight (choose in [0, 1] and typically < 0.5)

    :return: (u_next, v_next), where
      * u_next is residualized observation for step n, component i + 1
      * v_next is unnormalized eigenvector estimate for step n, component i
    """
    v_next = (1 - alpha) * v + alpha * u * np.dot(u, v) / np.linalg.norm(v)
    u_next = u - np.dot(u, v) * v / (np.linalg.norm(v) ** 2)
    return u_next, v_next


def ipca(
    df: pd.DataFrame, num_pc: int, alpha: float
) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:
    """
    Incremental PCA.

    df should already be centered.

    https://ieeexplore.ieee.org/document/1217609
    https://www.cse.msu.edu/~weng/research/CCIPCApami.pdf

    :return: df of eigenvalue series (col 0 correspond to max eigenvalue, etc.).
        list of dfs of unit eigenvectors (0 indexes df eigenvectors
        corresponding to max eigenvalue, etc.).
    """
    dbg.dassert_isinstance(
        num_pc, int, msg="Specify an integral number of principal components."
    )
    dbg.dassert_lt(
        num_pc,
        df.shape[0],
        msg="Number of time steps should exceed number of principal components.",
    )
    dbg.dassert_lte(
        num_pc,
        df.shape[1],
        msg="Dimension should be greater than or equal to the number of principal components.",
    )
    dbg.dassert_lte(0, alpha, msg="alpha should belong to [0, 1].")
    dbg.dassert_lte(alpha, 1, msg="alpha should belong to [0, 1].")
    _LOG.info("com = %0.2f", 1.0 / alpha - 1)
    lambdas = []
    # V's are eigenvectors with norm equal to corresponding eigenvalue
    # vsl = [[v1], [v2], ...].
    vsl = []
    unit_eigenvecs = []
    step = 0
    for n in df.index:
        step += 1
        # Initialize u1(n).
        # Handle NaN's by replacing with 0.
        ul = [df.loc[n].fillna(value=0)]
        for i in range(1, min(num_pc, step) + 1):
            # Initialize ith eigenvector.
            if i == step:
                _LOG.info("Initializing eigenvector %i...", i)
                v = ul[-1]
                # Bookkeeping.
                vsl.append([v])
                norm = np.linalg.norm(v)
                lambdas.append([norm])
                unit_eigenvecs.append([v / norm])
            else:
                # Main update step for eigenvector i.
                u, v = ipca_step(ul[-1], vsl[i - 1][-1], alpha)
                # Bookkeeping.
                u.name = n
                v.name = n
                ul.append(u)
                vsl[i - 1].append(v)
                norm = np.linalg.norm(v)
                lambdas[i - 1].append(norm)
                unit_eigenvecs[i - 1].append(v / norm)
    _LOG.info("Completed %i steps of incremental PCA.", step)
    # Convert lambda list of lists to list of series.
    # Convert unit_eigenvecs list of lists to list of dataframes.
    lambdas_srs = []
    unit_eigenvec_dfs = []
    for i in range(0, num_pc):
        lambdas_srs.append(pd.Series(index=df.index[i:], data=lambdas[i]))
        unit_eigenvec_dfs.append(pd.concat(unit_eigenvecs[i], axis=1).transpose())
    lambda_df = pd.concat(lambdas_srs, axis=1)
    return lambda_df, unit_eigenvec_dfs


def unit_vector_angular_distance(df: pd.DataFrame) -> pd.Series:
    """
    Accept a df of unit eigenvectors (rows) and returns a series with angular
    distance from index i to index i + 1.

    The angular distance lies in [0, 1].
    """
    vecs = df.values
    # If all of the vectors are unit vectors, then
    # np.diag(vecs.dot(vecs.T)) should return an array of all 1.'s.
    cos_sim = np.diag(vecs[:-1, :].dot(vecs[1:, :].T))
    ang_dist = np.arccos(cos_sim) / np.pi
    srs = pd.Series(index=df.index[1:], data=ang_dist, name="angular change")
    return srs


def eigenvector_diffs(eigenvecs: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Take a list of eigenvectors and returns a df of angular distances.
    """
    ang_chg = []
    for i, vec in enumerate(eigenvecs):
        srs = unit_vector_angular_distance(vec)
        srs.name = i
        ang_chg.append(srs)
    df = pd.concat(ang_chg, axis=1)
    return df


# #############################################################################
# Test signals
# #############################################################################


def get_heaviside(a: int, b: int, zero_val: int, tick: int) -> pd.Series:
    """
    Generate Heaviside pd.Series.
    """
    dbg.dassert_lte(a, zero_val)
    dbg.dassert_lte(zero_val, b)
    array = np.arange(a, b, tick)
    srs = pd.Series(
        data=np.heaviside(array, zero_val), index=array, name="Heaviside"
    )
    return srs


def get_impulse(a: int, b: int, tick: int) -> pd.Series:
    """
    Generate unit impulse pd.Series.
    """
    heavi = get_heaviside(a, b, 1, tick)
    impulse = (heavi - heavi.shift(1)).shift(-1).fillna(0)
    impulse.name = "impulse"
    return impulse


def get_binomial_tree(
    p: Union[float, Iterable[float]],
    vol: float,
    size: Union[int, Tuple[int, ...], None],
    seed: Optional[int] = None,
) -> pd.Series:
    # binomial_tree(0.5, 0.1, 252, seed=0).plot()
    np.random.seed(seed=seed)
    pos = np.random.binomial(1, p, size)
    neg = np.full(size, 1) - pos
    delta = float(vol) * (pos - neg)
    return pd.Series(np.exp(delta.cumsum()), name="binomial_walk")


def get_gaussian_walk(
    drift: Union[float, Iterable[float]],
    vol: Union[float, Iterable[float]],
    size: Union[int, Tuple[int, ...], None],
    seed: Optional[int] = None,
) -> pd.Series:
    # get_gaussian_walk(0, .2, 252, seed=10)
    np.random.seed(seed=seed)
    gauss = np.random.normal(drift, vol, size)
    return pd.Series(np.exp(gauss.cumsum()), name="gaussian_walk")
