import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, Download, Gauge, RefreshCw, Wind } from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { exportCsv, fetchForecastHistory, fetchOverview } from './services/api';
import type { ForecastHistoryRecord, OverviewResponse } from './types';

const janDates = Array.from({ length: 31 }, (_, index) => {
  const day = index + 1;
  return `2026-01-${String(day).padStart(2, '0')}`;
});

function formatValue(value: number | null, digits = 1): string {
  if (value === null || Number.isNaN(value)) return '—';
  return `${value.toFixed(digits)} MW`;
}

function formatTimestamp(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/London',
  }).format(date);
}

function App() {
  const [selectedDate, setSelectedDate] = useState('2026-01-15');
  const [cutoff, setCutoff] = useState('11:00');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [history, setHistory] = useState<ForecastHistoryRecord[]>([]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const overviewData = await fetchOverview(selectedDate, cutoff);
      const historyData = await fetchForecastHistory(selectedDate, cutoff);
      setOverview(overviewData);
      setHistory(historyData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load data';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [selectedDate, cutoff]);

  const chartData = useMemo(() => {
    if (!overview) return [] as any[];
    return overview.periods
      .filter((period) => period.selected_forecast_mw !== null || period.actual_mw !== null)
      .map((period) => ({
        time: period.delivery_time,
        forecast: period.selected_forecast_mw,
        actual: period.actual_mw,
        error: period.signed_error_mw,
        label: new Intl.DateTimeFormat('en-GB', {
          hour: '2-digit',
          minute: '2-digit',
          timeZone: 'Europe/London',
        }).format(new Date(period.delivery_time)),
      }));
  }, [overview]);

  const matchedPeriods = overview?.matched_periods ?? 0;
  const hasJanuary2026Data =
    (overview?.available_actual_periods ?? 0) > 0 ||
    (overview?.eligible_forecast_periods ?? 0) > 0 ||
    history.length > 0;
  const latestForecastPeriod = overview?.periods.filter((period) => period.selected_forecast_mw !== null).slice(-1)[0];
  const latestActualPeriod = overview?.periods.filter((period) => period.actual_mw !== null).slice(-1)[0];

  const errorBreakdown = useMemo(() => {
    if (!overview) return [] as any[];
    return overview.periods
      .filter((period) => period.absolute_error_mw !== null)
      .map((period) => ({
        hour: Number(new Intl.DateTimeFormat('en-GB', {
          hour: '2-digit',
          hourCycle: 'h23',
          timeZone: 'Europe/London',
        }).format(new Date(period.delivery_time))),
        error: period.absolute_error_mw,
      }));
  }, [overview]);

  const aggregateByHour = useMemo(() => {
    const map = new Map<number, number[]>();
    errorBreakdown.forEach((row) => {
      const key = row.hour;
      const values = map.get(key) ?? [];
      values.push(row.error);
      map.set(key, values);
    });
    return Array.from(map.entries())
      .sort(([left], [right]) => left - right)
      .map(([hour, values]) => ({
        hour: `${String(hour).padStart(2, '0')}:00`,
        value: values.reduce((sum, current) => sum + current, 0) / values.length,
      }));
  }, [errorBreakdown]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">UK Electricity Procurement</div>
          <h1>UK Wind Forecast Intelligence</h1>
        </div>
        <div className="header-actions">
          <div className="controls-inline">
            <label>
              Delivery date
              <select value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)}>
                {janDates.map((date) => (
                  <option value={date} key={date}>{date}</option>
                ))}
              </select>
            </label>
            <label>
              Cutoff (UK local)
              <input type="time" value={cutoff} onChange={(event) => setCutoff(event.target.value)} />
            </label>
          </div>
          <button className="primary-button" onClick={() => void loadData()} disabled={loading}>
            <RefreshCw size={16} /> {loading ? 'Loading…' : 'Refresh'}
          </button>
          <button className="secondary-button" onClick={() => exportCsv(selectedDate, cutoff)}>
            <Download size={16} /> Export CSV
          </button>
        </div>
      </header>

      <div className="meta-row">
        <span>Data source: Elexon WINDFOR / FUELHH streams</span>
        <span>Timezone: {overview?.timezone ?? 'Europe/London'}</span>
        <span>Cutoff policy: configurable analytical assumption</span>
        <span>
          {loading
            ? 'Loading forecast data…'
            : error
              ? 'Elexon data request failed'
              : overview?.data_source_status === 'error'
                ? 'Elexon request failed'
                : hasJanuary2026Data
                ? 'Live Elexon records loaded'
                : 'No matching January 2026 records'}
        </span>
      </div>

      {error ? (
        <div className="error-banner">
          <AlertTriangle size={16} /> {error}
        </div>
      ) : null}

      {!loading && overview && overview.data_source_status !== 'error' && !hasJanuary2026Data ? (
        <div className="data-unavailable-banner">
          <AlertTriangle size={18} /> No January 2026 Elexon data available for this date.
        </div>
      ) : null}

      <section className="kpis">
        <div className="kpi-card">
          <div className="kpi-label">Latest selected eligible forecast</div>
          <div className="kpi-value">{formatValue(latestForecastPeriod?.selected_forecast_mw ?? null)}</div>
          <div className="kpi-muted">Delivery period {latestForecastPeriod ? formatTimestamp(latestForecastPeriod.delivery_time) : '—'}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Selected forecast publication</div>
          <div className="kpi-value">{formatTimestamp(latestForecastPeriod?.forecast_publication_time ?? null)}</div>
          <div className="kpi-muted">Publication for latest selected period</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Latest actual wind generation</div>
          <div className="kpi-value">{formatValue(latestActualPeriod?.actual_mw ?? null)}</div>
          <div className="kpi-muted">Delivery period {latestActualPeriod ? formatTimestamp(latestActualPeriod.delivery_time) : '—'}</div>
        </div>
        <div className="kpi-card accent">
          <div className="kpi-label">MAE</div>
          <div className="kpi-value">{formatValue(overview?.mae_mw ?? null, 1)}</div>
          <div className="kpi-muted">Mean absolute error · sample {matchedPeriods}</div>
        </div>
        <div className="kpi-card accent-2">
          <div className="kpi-label">RMSE</div>
          <div className="kpi-value">{formatValue(overview?.rmse_mw ?? null, 1)}</div>
          <div className="kpi-muted">Root mean square error · sample {matchedPeriods}</div>
        </div>
        <div className="kpi-card accent-3">
          <div className="kpi-label">Signed bias</div>
          <div className="kpi-value">{formatValue(overview?.signed_bias_mw ?? null, 1)}</div>
          <div className="kpi-muted">Forecast minus actual · sample {matchedPeriods}</div>
        </div>
      </section>

      <section className="panel-grid">
        <div className="panel">
          <div className="panel-title"><Gauge size={18} /> Forecast vs actual</div>
          {chartData.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#2a3947" strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fill: '#a7b8c8', fontSize: 11 }} />
                  <YAxis unit=" MW" tick={{ fill: '#a7b8c8', fontSize: 11 }} />
                  <Tooltip formatter={(value) => [`${value} MW`]} />
                  <Legend />
                  <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#42d7c5" dot={false} />
                  <Line type="monotone" dataKey="actual" name="Actual" stroke="#f2b75b" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">No chart data available for the selected delivery date. Historical Elexon records are missing.</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-title"><BarChart3 size={18} /> Forecast revisions</div>
          {history.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={history}>
                  <defs>
                    <linearGradient id="revFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#42d7c5" stopOpacity={0.8} />
                      <stop offset="100%" stopColor="#42d7c5" stopOpacity={0.15} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#2a3947" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="publish_time"
                    tick={{ fill: '#a7b8c8', fontSize: 11 }}
                    tickFormatter={(value: string) => formatTimestamp(value)}
                    label={{ value: 'Forecast publication time (Europe/London)', position: 'insideBottom', offset: -8, fill: '#a7b8c8', fontSize: 11 }}
                  />
                  <YAxis unit=" MW" tick={{ fill: '#a7b8c8', fontSize: 11 }} />
                  <Tooltip
                    labelFormatter={(value) => formatTimestamp(String(value))}
                    formatter={(value, _name, item) => [
                      `${value} MW`,
                      `${item.payload.eligible_at_cutoff ? 'At/before cutoff' : 'After cutoff'} · delivery ${formatTimestamp(String(item.payload.delivery_time))}`,
                    ]}
                  />
                  <Area dataKey="generation_mw" stroke="#42d7c5" fill="url(#revFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">Forecast history is unavailable for the selected delivery date from the live Elexon stream. No January 2026 revisions are available.</div>
          )}
        </div>
      </section>

      <section className="panel-grid lower-grid">
        <div className="panel">
          <div className="panel-title"><Wind size={18} /> Error analysis</div>
          {aggregateByHour.length ? (
            <div className="chart-wrap small">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={aggregateByHour}>
                  <CartesianGrid stroke="#2a3947" strokeDasharray="3 3" />
                  <XAxis dataKey="hour" tick={{ fill: '#a7b8c8', fontSize: 11 }} />
                  <YAxis unit=" MW" tick={{ fill: '#a7b8c8', fontSize: 11 }} />
                  <Tooltip formatter={(value) => [`${value} MW`, 'Mean absolute error']} />
                  <Bar dataKey="value" name="Mean absolute error" fill="#42d7c5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">No absolute-error series is available.</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-title"><AlertTriangle size={18} /> Data quality</div>
          <div className="quality-box">
            <p>Coverage: {overview?.coverage_percentage ?? 0}%</p>
            <p>Matched periods: {overview?.matched_periods ?? 0}</p>
            <p>Missing forecasts: {overview?.missing_forecast_periods ?? 0}</p>
            <p>Missing actuals: {overview?.missing_actual_periods ?? 0}</p>
            <p>Missing periods: {overview?.missing_periods ?? 0}</p>
            <p>Eligible forecasts: {overview?.eligible_forecast_periods ?? 0}</p>
            <p>Expected periods: {overview?.total_expected_periods ?? 0}</p>
            <p>Coverage denominator: {overview?.coverage_denominator ?? 0} periods · matched ÷ expected</p>
            {overview?.data_quality_warnings?.length ? (
              <ul>
                {overview.data_quality_warnings.map((warning, index) => (
                  <li key={`${warning}-${index}`}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p>No data-quality warnings detected.</p>
            )}
          </div>
        </div>
      </section>

      <section className="panel table-panel">
        <div className="panel-title">Period records</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Delivery time</th>
                <th>Selected forecast</th>
                <th>Publication time</th>
                <th>Actual</th>
                <th>Signed error</th>
                <th>Absolute error</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {overview?.periods.map((period) => (
                <tr key={period.delivery_time}>
                  <td>{formatTimestamp(period.delivery_time)}</td>
                  <td>{formatValue(period.selected_forecast_mw, 1)}</td>
                  <td>{formatTimestamp(period.forecast_publication_time)}</td>
                  <td>{formatValue(period.actual_mw, 1)}</td>
                  <td>{formatValue(period.signed_error_mw, 1)}</td>
                  <td>{formatValue(period.absolute_error_mw, 1)}</td>
                  <td>{period.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default App;
