export type OverviewPeriod = {
  delivery_time: string;
  selected_forecast_mw: number | null;
  forecast_publication_time: string | null;
  actual_mw: number | null;
  actual_publication_time: string | null;
  signed_error_mw: number | null;
  absolute_error_mw: number | null;
  status: string;
  warning: string | null;
};

export type OverviewResponse = {
  delivery_date: string;
  timezone: string;
  cutoff_local: string;
  cutoff_utc: string;
  forecast_selection_policy: string;
  total_expected_periods: number;
  available_actual_periods: number;
  eligible_forecast_periods: number;
  matched_periods: number;
  missing_forecast_periods: number;
  missing_actual_periods: number;
  missing_periods: number;
  coverage_percentage: number;
  coverage_denominator: number;
  coverage_definition: string;
  mae_mw: number | null;
  rmse_mw: number | null;
  signed_bias_mw: number | null;
  periods: OverviewPeriod[];
  data_quality_warnings: string[];
  data_source_status: string;
  source: string;
};

export type ForecastHistoryRecord = {
  delivery_time: string;
  publish_time: string;
  generation_mw: number;
  eligible_at_cutoff: boolean;
  is_selected: boolean;
};
