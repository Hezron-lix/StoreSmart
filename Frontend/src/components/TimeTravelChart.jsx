// components/TimeTravelChart.jsx
// Operational View: a slider lets the user "travel back" through historical
// storage snapshots. Dragging the slider updates which date's breakdown is
// shown, and highlights that point on the usage-over-time line chart.

import React, { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
} from "recharts";
import { getStorageHistory, ApiError } from "../api";
import "./TimeTravelChart.css";

export default function TimeTravelChart() {
  const [history, setHistory] = useState(null);
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [sliderIndex, setSliderIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus("loading");
      try {
        const result = await getStorageHistory();
        if (!cancelled) {
          setHistory(result);
          setSliderIndex(Math.max(result.length - 1, 0)); // start at most recent day
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

  const selectedSnapshot = useMemo(() => {
    if (!history || history.length === 0) return null;
    return history[sliderIndex];
  }, [history, sliderIndex]);

  if (status === "loading") {
    return (
      <div className="time-travel time-travel--loading">
        <p>Loading storage history…</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="time-travel time-travel--error">
        <p>Couldn't load storage history. {errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="time-travel">
      <div className="time-travel__header">
        <span className="time-travel__title">Time-Travel</span>
        <span className="time-travel__date">{formatDate(selectedSnapshot?.date)}</span>
      </div>

      <p className="time-travel__hint hds-text--sm hds-text--muted">
        Drag the slider to scrub through historical storage snapshots. The chart
        highlights the selected date.
      </p>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={history} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-quiet)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--color-text-soft)", fontSize: 11 }}
            tickFormatter={formatDate}
          />
          <YAxis tick={{ fill: "var(--color-text-soft)", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              background: "var(--color-bg-quiet)",
              border: "1px solid var(--color-border-quiet)",
              borderRadius: "var(--radius-md)",
              fontSize: "0.8rem",
            }}
            labelFormatter={formatDate}
          />
          <Line
            type="monotone"
            dataKey="usedGb"
            name="Used GB"
            stroke="var(--color-brand-500)"
            strokeWidth={2}
            dot={false}
          />
          {selectedSnapshot && (
            <ReferenceDot
              x={selectedSnapshot.date}
              y={selectedSnapshot.usedGb}
              r={5}
              fill="#9b6829"
              stroke="var(--color-bg-quiet)"
              strokeWidth={2}
            />
          )}
        </LineChart>
      </ResponsiveContainer>

      <input
        type="range"
        className="time-travel__slider"
        min={0}
        max={Math.max(history.length - 1, 0)}
        value={sliderIndex}
        onChange={(e) => setSliderIndex(Number(e.target.value))}
        aria-label="Scrub through storage history by date"
      />

      {selectedSnapshot && (
        <div className="time-travel__snapshot">
          <span className="time-travel__snapshot-label hds-text--xs hds-text--muted">
            Selected snapshot
          </span>
          <span>
            <strong>{selectedSnapshot.usedGb} GB</strong> used on{" "}
            {formatDate(selectedSnapshot.date)}
          </span>
        </div>
      )}
    </div>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "2-digit" });
}