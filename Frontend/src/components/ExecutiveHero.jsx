import React, { useEffect, useState } from "react";
import { getHealthScore, ApiError } from "../api";
import "./ExecutiveHero.css";

function interpret(data) {
  if (!data) return "";
  if (data.grade === "A" || data.grade === "B") return "Storage is healthy";
  if (data.grade === "C") return "Storage is fair";
  return "Storage is critical";
}

export default function ExecutiveHero() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
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
          setErrorMessage(
            err instanceof ApiError ? err.message : "Something went wrong."
          );
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
      <div className="exec-hero exec-hero--loading">
        <p className="hds-text--sm hds-text--muted">Loading storage health…</p>
      </div>
    );
  }

  if (status === "error" || !data) {
    return (
      <div className="exec-hero exec-hero--error">
        <p className="hds-text--sm">{errorMessage || "Something went wrong."}</p>
      </div>
    );
  }

  return (
    <div className="exec-hero">
      <div className="exec-hero__top">
        <div className="exec-hero__copy">
          <span className="exec-hero__eyebrow">Storage health</span>
          <h1 className="exec-hero__grade-line">
            <span className={"exec-hero__grade exec-hero__grade--" + data.grade}>
              {data.grade}
            </span>
            <span className="exec-hero__grade-label">{interpret(data)}</span>
          </h1>
          <p className="exec-hero__caption">
            Weighted score across capacity (0.4), compression efficiency (0.3),
            and runway stability (0.3). Grades A and B are healthy.
          </p>
        </div>

        <div className="exec-hero__ring" aria-hidden="true">
          <svg viewBox="0 0 200 200" className="exec-hero__ring-svg">
            <circle
              cx="100" cy="100" r="88"
              className="exec-hero__ring-track"
              fill="none"
              strokeWidth="12"
            />
            <circle
              cx="100" cy="100" r="88"
              className={"exec-hero__ring-fill exec-hero__ring-fill--" + data.grade}
              fill="none"
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={String(2 * Math.PI * 88)}
              strokeDashoffset={String(2 * Math.PI * 88 * (1 - data.score))}
              transform="rotate(-90 100 100)"
            />
          </svg>
          <span className="exec-hero__ring-percent">{Math.round(data.score * 100)}%</span>
        </div>
      </div>

      <div className="exec-hero__kpis">
        <div className="exec-hero__kpi">
          <span className="exec-hero__kpi-label">Capacity</span>
          <span className="exec-hero__kpi-value">
            {Math.round(data.capacity.value * 100)}%
          </span>
          <span className="exec-hero__kpi-detail">
            free · {data.capacity.usedGb.toFixed(0)} / {data.capacity.totalGb.toFixed(0)} GB used
          </span>
        </div>
        <div className="exec-hero__kpi">
          <span className="exec-hero__kpi-label">Efficiency</span>
          <span className="exec-hero__kpi-value">
            {Math.round(data.efficiency.value * 100)}%
          </span>
          <span className="exec-hero__kpi-detail">
            saveable · {data.efficiency.savingsPercent.toFixed(1)}% avg per file
          </span>
        </div>
        <div className="exec-hero__kpi">
          <span className="exec-hero__kpi-label">Stability</span>
          <span className="exec-hero__kpi-value">
            {data.stability.daysToFull}
          </span>
          <span className="exec-hero__kpi-detail">
            days until storage is full
          </span>
        </div>
      </div>
    </div>
  );
}
