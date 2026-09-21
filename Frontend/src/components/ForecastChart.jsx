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
  Legend,
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
  const chartData = [
    ...data.history.map((point) => ({ date: point.date, actualGb: point.usedGb })),
    ...data.forecast.map((point) => ({ date: point.date, predictedGb: point.predictedGb })),
  ];

  return (
    <div className="forecast-chart">
      <div className="forecast-chart__header">
        <span className="forecast-chart__title">Spike Forecast</span>
        {data.runwayToZeroDate && (
          <span className="forecast-chart__runway">
            Runway-to-Zero: <strong>{formatDate(data.runwayToZeroDate)}</strong>
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--swa-border)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--swa-text-secondary)", fontSize: 11 }}
            tickFormatter={formatDate}
          />
          <YAxis
            tick={{ fill: "var(--swa-text-secondary)", fontSize: 11 }}
            label={{
              value: "GB",
              angle: -90,
              position: "insideLeft",
              fill: "var(--swa-text-secondary)",
              fontSize: 11,
            }}
          />
          <Tooltip
            contentStyle={{
              background: "var(--swa-surface-raised)",
              border: "1px solid var(--swa-border)",
              borderRadius: "var(--swa-radius)",
              fontSize: "0.8rem",
            }}
            labelFormatter={formatDate}
          />
          <Legend wrapperStyle={{ fontSize: "0.8rem" }} />

          {data.capacityGb && (
            <ReferenceLine
              y={data.capacityGb}
              stroke="var(--swa-signal-critical)"
              strokeDasharray="4 4"
              label={{
                value: "Capacity",
                position: "insideTopRight",
                fill: "var(--swa-signal-critical)",
                fontSize: 11,
              }}
            />
          )}

          <Line
            type="monotone"
            dataKey="actualGb"
            name="Actual usage"
            stroke="var(--swa-signal-neutral)"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="predictedGb"
            name="Predicted usage"
            stroke="var(--swa-signal-warning)"
            strokeWidth={2}
            strokeDasharray="5 3"
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