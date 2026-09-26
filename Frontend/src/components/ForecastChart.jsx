// components/ForecastChart.jsx
// Operational View: shows historical + Prophet-predicted storage usage
// against total capacity, with a reference line marking the
// "Runway-to-Zero" date (when storage is predicted to hit 100%).

import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { getForecast, ApiError } from "../api";
import "./ForecastChart.css";

export default function ForecastChart() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus("loading");
      try {
        const result = await getForecast();
        if (!cancelled) {
          setData(result);
          setStatus("ready");
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong.");
          setStatus("error");
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "loading") {
    return (
      <div className="forecast-chart forecast-chart--loading">
        <p>Loading forecast…</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="forecast-chart forecast-chart--error">
        <p>Couldn't load the forecast. {errorMessage}</p>
      </div>
    );
  }

  // Merge history (actuals) and forecast (predicted) into one chart timeline.
  const lastIndex = data.history.length - 1;
  const chartData = [
    ...data.history.map((point, index) => ({
      date: point.date,
      actualGb: point.usedGb,
      predictedGb: index === lastIndex ? point.usedGb : undefined,
    })),
    ...data.forecast.map((point) => ({
      date: point.date,
      actualGb: undefined,
      predictedGb: Number(point.predictedGb ?? point.usedGb),
    })),
  ];

  return (
    <div className="forecast-chart">
      <div className="forecast-chart__header">
        <span className="forecast-chart__title">Spike Forecast</span>
        {data.runwayToZeroDate && (
          <span
            className="forecast-chart__runway"
            title="The predicted date when storage usage will hit 100% of capacity."
          >
            Runway-to-Zero: <strong>{formatDate(data.runwayToZeroDate)}</strong>
          </span>
        )}
      </div>

      <div className="forecast-chart__meta">
        <p className="hds-text--sm hds-text--muted">
          Prophet-predicted storage trajectory. Runway-to-Zero is the forecast
          date when usage reaches 100% of capacity.
        </p>
        <ul className="forecast-chart__legend">
          <li><span className="forecast-chart__legend-swatch forecast-chart__legend-swatch--actual" /> Actual usage</li>
          <li><span className="forecast-chart__legend-swatch forecast-chart__legend-swatch--predicted" /> Predicted usage</li>
          <li><span className="forecast-chart__legend-swatch forecast-chart__legend-swatch--capacity" /> Capacity ({data.capacityGb} GB)</li>
        </ul>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-quiet)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--color-text-soft)", fontSize: 11 }}
            tickFormatter={formatDate}
          />
          <YAxis
            tick={{ fill: "var(--color-text-soft)", fontSize: 11 }}
            label={{
              value: "GB",
              angle: -90,
              position: "insideLeft",
              fill: "var(--color-text-soft)",
              fontSize: 11,
            }}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-bg-quiet)",
              border: "1px solid var(--color-border-quiet)",
              borderRadius: "var(--radius-md)",
              fontSize: "0.8rem",
            }}
            labelFormatter={formatDate}
            formatter={(value, name) => [`${value} GB`, name]}
          />

          {data.capacityGb && (
            <ReferenceLine
              y={data.capacityGb}
              stroke="#dc2626"
              strokeWidth={1.5}
              label={{
                value: `Capacity (${data.capacityGb} GB)`,
                position: "insideTopRight",
                fill: "#dc2626",
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          )}

          <Line
            type="monotone"
            dataKey="actualGb"
            name="Actual usage"
            stroke="var(--color-brand-500)"
            strokeWidth={2.5}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="predictedGb"
            name="Predicted usage"
            stroke="#ff6118"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}