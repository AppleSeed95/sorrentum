import logging
from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import core.signal_processing as sigp
import helpers.dbg as dbg

_LOG = logging.getLogger(__name__)


def plot_event_response(local_ts: pd.DataFrame, response_col: str) -> None:
    """
    Plot lineplot of event response curve.

    :param local_ts: output of `core.event_study.core.build_local_timeseries`
    :param response_col: name of response column
    """
    local_ts = local_ts.copy()
    local_ts.index.names = ["grid_index", "event_timestamp"]
    local_ts = local_ts.reset_index()
    sns.lineplot(x="grid_index", y=response_col, data=local_ts)
    _ = plt.xticks(local_ts["grid_index"].unique())


def plot_interevent_intervals(
    timestamps: pd.Series,
    time_unit: str,
    window: int,
    min_periods: Optional[int],
    mode: Optional[str] = "set_to_nan",
    lower_quantile: float = 0.01,
    **kwargs: Any,
) -> None:
    """
    Plot inter-event intervals.

    :param timestamps: datetime pd.Series
    :param time_unit: time units in which to plot the data. A parameter
        for timedelta64[]
    :param window: as in sigp.process_outliers
    :param min_periods: as in sigp.process_outliers
    :param mode: as in sigp.process_outliers
    :param lower_quantile: as in sigp.process_outliers
    :param kwargs: passed into sigp.process_outliers
    """
    dbg.dassert(not timestamps.empty, "The time series is empty")
    dbg.dassert_in(
        timestamps.dtype,
        [
            np.dtype("datetime64[ns]"),
            np.dtype("datetime64[s]"),
            np.dtype("datetime64[m]"),
            np.dtype("datetime64[h]"),
            np.dtype("datetime64[D]"),
        ],
        "The data should be datetime",
    )
    intervals = timestamps.diff()
    intervals_without_outliers = sigp.process_outliers(
        intervals.astype(f"timedelta64[{time_unit}]"),
        window,
        min_periods,
        mode,
        lower_quantile,
        **kwargs,
    ).dropna()
    sns.distplot(intervals_without_outliers)
    plt.xlabel(time_unit)
    plt.title("Distribution of inter-event time intervals without outliers")
