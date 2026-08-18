import React from 'react';
import {
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
import type { ResultRow } from '../api';
import {
  isMonetaryColumn,
  formatCurrencyFromCents,
  formatChartAxisCurrency,
} from '../utils/formatters';

// Deterministic palette — series are always the same color regardless of LLM output.
const SERIES_COLORS = [
  '#6366f1', // indigo  (accent)
  '#10b981', // emerald
  '#f59e0b', // amber
  '#3b82f6', // blue
  '#ec4899', // pink
  '#8b5cf6', // violet
];

const seriesColor = (index: number): string =>
  SERIES_COLORS[index % SERIES_COLORS.length];

interface ChartRendererProps {
  data: ResultRow[];
}

const isNumeric = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const displayValue = (value: unknown): string => {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
};

const renderTable = (data: ResultRow[]) => {
  const keys = data.length > 0 ? Object.keys(data[0]) : [];

  return (
    <div className="result-table-wrap">
      <table className="result-table">
        <thead>
          <tr>
            {keys.map((key) => <th key={key}>{key}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {keys.map((key) => {
                const val = row[key];
                const isMoney = isMonetaryColumn(key) && isNumeric(val);
                const display = isMoney
                  ? formatCurrencyFromCents(val, row.currency as string)
                  : displayValue(val);
                return <td key={key}>{display}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const ChartRenderer: React.FC<ChartRendererProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return <div className="empty-result">No rows were returned.</div>;
  }

  const keys = Object.keys(data[0]);
  const numericKeys = keys.filter((key) => data.some((row) => isNumeric(row[key])));
  const dimensionKeys = keys.filter((key) => !numericKeys.includes(key));

  // Deterministic rule:
  // 0 dimensions + 1 numeric metric -> KPI.
  // 1 dimension + numeric metrics -> chart (line for time-like dimensions, bar otherwise).
  // 2 dimensions + 1 numeric metric -> grouped chart after deterministic pivoting.
  // Anything else -> table only, because collapsing dimensions would be misleading.
  if (data.length === 1 && dimensionKeys.length === 0 && numericKeys.length === 1) {
    const key = numericKeys[0];
    const rawVal = data[0][key];
    const isMoney = isMonetaryColumn(key) && isNumeric(rawVal);
    const formatted = isMoney
      ? formatCurrencyFromCents(rawVal, data[0]?.currency as string)
      : displayValue(rawVal);

    return (
      <div>
        <div className="single-value">
          <span>{key}</span>
          <strong>{formatted}</strong>
        </div>
        {renderTable(data)}
      </div>
    );
  }

  if (dimensionKeys.length === 1 && numericKeys.length > 0 && data.length > 1) {
    const categoryKey = dimensionKeys[0];
    const isTimeBased = /date|month|year|week|quarter|time/i.test(categoryKey);
    const isMonetary = numericKeys.some(isMonetaryColumn);

    const tooltipFormatter = (value: unknown, name: unknown, item: any) => {
      const nameStr = String(name ?? '');
      const rowCurrency = (item?.payload?.currency ?? data[0]?.currency) as string | undefined;
      if (isMonetaryColumn(nameStr) && typeof value === 'number') {
        return [formatCurrencyFromCents(value, rowCurrency), nameStr];
      }
      return [displayValue(value), nameStr];
    };

    const chart = isTimeBased ? (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
          <XAxis dataKey={categoryKey} stroke="var(--text-secondary)" />
          <YAxis
            stroke="var(--text-secondary)"
            tickFormatter={isMonetary ? (val) => formatChartAxisCurrency(val, data[0]?.currency as string) : undefined}
          />
          <Tooltip formatter={tooltipFormatter} />
          <Legend />
          {numericKeys.map((key, i) => (
            <Line key={key} type="monotone" dataKey={key} stroke={seriesColor(i)} strokeWidth={2} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    ) : (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
          <XAxis dataKey={categoryKey} stroke="var(--text-secondary)" />
          <YAxis
            stroke="var(--text-secondary)"
            tickFormatter={isMonetary ? (val) => formatChartAxisCurrency(val, data[0]?.currency as string) : undefined}
          />
          <Tooltip formatter={tooltipFormatter} />
          <Legend />
          {numericKeys.map((key, i) => (
            <Bar key={key} dataKey={key} fill={seriesColor(i)} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );

    return (
      <div>
        <div className="chart-container">{chart}</div>
        {renderTable(data)}
      </div>
    );
  }

  if (dimensionKeys.length === 2 && numericKeys.length === 1 && data.length > 1) {
    const [categoryKey, seriesKey] = dimensionKeys;
    const valueKey = numericKeys[0];
    const isMonetary = isMonetaryColumn(valueKey);
    const seriesValues = Array.from(new Set(data.map((row) => String(row[seriesKey])))).sort();
    const grouped = new Map<string, ResultRow>();

    for (const row of data) {
      const category = String(row[categoryKey]);
      const existing = grouped.get(category) ?? { [categoryKey]: category };
      existing[String(row[seriesKey])] = isNumeric(row[valueKey]) ? row[valueKey] : null;
      if (row.currency) {
        existing['currency'] = row.currency;
      }
      grouped.set(category, existing);
    }

    const chartData = Array.from(grouped.values());
    const isTimeBased = /date|month|year|week|quarter|time/i.test(categoryKey);

    const groupedTooltipFormatter = (value: unknown, name: unknown, item: any) => {
      const nameStr = String(name ?? '');
      const rowCurrency = (nameStr === 'INR' || nameStr === 'USD' ? nameStr : item?.payload?.currency ?? data[0]?.currency) as string | undefined;
      if (isMonetary && typeof value === 'number') {
        return [formatCurrencyFromCents(value, rowCurrency), nameStr];
      }
      return [displayValue(value), nameStr];
    };

    const chart = isTimeBased ? (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
          <XAxis dataKey={categoryKey} stroke="var(--text-secondary)" />
          <YAxis
            stroke="var(--text-secondary)"
            tickFormatter={isMonetary ? (val) => formatChartAxisCurrency(val, data[0]?.currency as string) : undefined}
          />
          <Tooltip formatter={groupedTooltipFormatter} />
          <Legend />
          {seriesValues.map((series, i) => (
            <Line key={series} type="monotone" dataKey={series} stroke={seriesColor(i)} strokeWidth={2} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    ) : (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
          <XAxis dataKey={categoryKey} stroke="var(--text-secondary)" />
          <YAxis
            stroke="var(--text-secondary)"
            tickFormatter={isMonetary ? (val) => formatChartAxisCurrency(val, data[0]?.currency as string) : undefined}
          />
          <Tooltip formatter={groupedTooltipFormatter} />
          <Legend />
          {seriesValues.map((series, i) => (
            <Bar key={series} dataKey={series} fill={seriesColor(i)} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );

    return (
      <div>
        <div className="chart-container">{chart}</div>
        {renderTable(data)}
      </div>
    );
  }

  return renderTable(data);
};
