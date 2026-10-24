import type { ForecastHistoryRecord, OverviewResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export async function fetchOverview(date: string, cutoff: string): Promise<OverviewResponse> {
  const url = `${API_BASE_URL}/api/overview?date=${encodeURIComponent(date)}&cutoff=${encodeURIComponent(cutoff)}`;
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error: ${response.status} ${errorText}`);
  }
  return response.json();
}

export async function fetchForecastHistory(date: string, cutoff: string): Promise<ForecastHistoryRecord[]> {
  const url = `${API_BASE_URL}/api/forecast-history?date=${encodeURIComponent(date)}&cutoff=${encodeURIComponent(cutoff)}`;
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Forecast history API error: ${response.status} ${errorText}`);
  }
  const payload = await response.json();
  return payload.records as ForecastHistoryRecord[];
}

export function exportCsv(date: string, cutoff: string): void {
  const url = `${API_BASE_URL}/api/export?date=${encodeURIComponent(date)}&cutoff=${encodeURIComponent(cutoff)}`;
  const link = document.createElement('a');
  link.href = url;
  link.download = `wind-forecast-${date}.csv`;
  link.click();
}
