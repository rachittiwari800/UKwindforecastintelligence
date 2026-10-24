from app.analytics.metrics import calculate_metrics


def test_metrics_match_expected_values():
    forecast = [110, 90]
    actual = [100, 100]
    metrics = calculate_metrics(forecast, actual)
    assert metrics["mae_mw"] == 10.0
    assert metrics["rmse_mw"] == 10.0
    assert metrics["signed_bias_mw"] == 0.0


def test_metrics_return_none_for_empty_matches():
    metrics = calculate_metrics([], [])
    assert metrics["mae_mw"] is None
    assert metrics["rmse_mw"] is None
    assert metrics["signed_bias_mw"] is None
    assert metrics["matched_periods"] == 0
