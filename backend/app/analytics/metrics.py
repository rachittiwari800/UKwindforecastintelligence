from __future__ import annotations

import math
from typing import Iterable, Optional


def calculate_metrics(forecast_values: Iterable[float], actual_values: Iterable[float]) -> dict:
    forecasts = list(forecast_values)
    actuals = list(actual_values)
    if len(forecasts) != len(actuals):
        raise ValueError("Forecast and actual series must have the same length.")
    if not forecasts:
        return {
            "mae_mw": None,
            "rmse_mw": None,
            "signed_bias_mw": None,
            "matched_periods": 0,
        }

    errors = [float(f) - float(a) for f, a in zip(forecasts, actuals)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    bias = sum(errors) / len(errors)
    return {
        "mae_mw": mae,
        "rmse_mw": rmse,
        "signed_bias_mw": bias,
        "matched_periods": len(errors),
    }
