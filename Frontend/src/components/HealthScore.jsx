// components/HealthScore.jsx
// Executive View: fetches the current health score, shows the A–F grade,
// the three weighted sub-metrics, and a 30-day trend indicator.

import React, { useEffect, useState } from "react";
import { getHealthScore, ApiError } from "../api";
import "./HealthScore.css";

const GRADE_COLOR = {
  A: "#006f3a",
  B: "#006f3a",
  C: "#9b6829",
  D: "#9b6829",
  F: "#a01400",
};

function interpret(data) {
  if (!data) return "";
  const pct = Math.round(data.score * 100);
  if (data.grade === "A" || data.grade === "B") {
    return "Storage is healthy. Continue monitoring.";
  }
  if (data.grade === "C") {
    return "Storage is fair. Consider compressing or removing stale files.";
  }
  return `Storage is critical (${pct}% of capacity usable). Compress or remove files soon.`;
}

export default function HealthScore() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading"); // "loading" | "ready" | "error"
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus("loading");
      try {
        const result = await getHealthScore();
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
      <div className="health-score health-score--loading">
        <p>Loading health score…</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="health-score health-score--error">
        <p>Couldn't load the health score. {errorMessage}</p>
      </div>
    );
  }

  const gradeColor = GRADE_COLOR[data.grade] || "var(--color-text-soft)";
  const trendDirection = getTrendDirection(data.trend);

  return (
    <div className="health-score">
      <div className="health-score__header">
        <span className="health-score__label">Storage Health</span>
        <span className="health-score__grade" style={{ color: gradeColor }}>
          {data.grade}
        </span>
      </div>

      <p className="health-score__hint hds-text--sm hds-text--muted">
        Graded A–F on capacity, compression efficiency, and runway stability.
      </p>

      <div className="health-score__bar-track">
        <div
          className="health-score__bar-fill"
          style={{ width: `${Math.round(data.score * 100)}%`, background: gradeColor }}
        />
      </div>
      <span className="health-score__percent">{Math.round(data.score * 100)}%</span>

      <div className="health-score__metrics">
        <Metric
          label="Capacity (% free)"
          value={`${Math.round(data.capacity.value * 100)}% free`}
          detail={`${data.capacity.usedGb} GB / ${data.capacity.totalGb} GB used`}
        />
        <Metric
          label="Efficiency (savings %)"
          value={`${Math.round(data.efficiency.value * 100)}% saveable`}
        />
        <Metric
          label="Stability (days to full)"
          value={`${data.stability.daysToFull} days to full`}
        />
      </div>

      <p className="health-score__interpret hds-text--sm hds-text--solid">
        {interpret(data)}
      </p>

      <div className="health-score__trend">
        <span>30-Day Trend:</span>
        <span className={`health-score__trend-value health-score__trend-value--${trendDirection}`}>
          {trendDirection === "up" && "▲ improving"}
          {trendDirection === "down" && "▼ declining"}
          {trendDirection === "flat" && "— steady"}
        </span>
      </div>
    </div>
  );
}

function Metric({ label, value, detail }) {
  return (
    <div className="health-score__metric">
      <span className="health-score__metric-label">{label}</span>
      <span className="health-score__metric-value">{value}</span>
      {detail && <span className="health-score__metric-detail">{detail}</span>}
    </div>
  );
}

/** Compares the first and last points in the trend array to decide direction. */
function getTrendDirection(trend) {
  if (!trend || trend.length < 2) return "flat";
  const first = trend[0].score;
  const last = trend[trend.length - 1].score;
  const delta = last - first;
  if (Math.abs(delta) < 0.02) return "flat";
  return delta > 0 ? "up" : "down";
}