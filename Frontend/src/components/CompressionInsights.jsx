import { useEffect, useState } from "react";

import {
  getCompressionInsights,
} from "../api";

import "./CompressionInsights.css";


export default function CompressionInsights() {
  const [data, setData] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError("");

        const result =
          await getCompressionInsights();

        setData(result);
      } catch (err) {
        setError(
          err?.message ||
          "Unable to load compression insights."
        );
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);


  if (loading) {
    return (
      <div className="compression-card">
        <div className="compression-loading">
          Loading Linear Regression...
        </div>
      </div>
    );
  }


  if (error) {
    return (
      <div className="compression-card">
        <div className="compression-error">
          {error}
        </div>
      </div>
    );
  }


  const predictions =
    data?.topPredictions || [];


  return (
    <div className="compression-card">

      <div className="compression-header">
        <div>
          <h2>
            Compression AI
          </h2>

          <p>
            Linear Regression
          </p>
        </div>

        <div className="model-badge">
          MODEL 2
        </div>
      </div>


      <div className="compression-metrics">

        <div className="metric-box">
          <span>
            Predicted Assets
          </span>

          <strong>
            {data?.predictionCount ?? 0}
          </strong>
        </div>


        <div className="metric-box">
          <span>
            Avg. Savings
          </span>

          <strong>
            {Number(
              data?.averageSavingsPercent || 0
            ).toFixed(2)}
            %
          </strong>
        </div>


        <div className="metric-box">
          <span>
            Potential Savings
          </span>

          <strong>
            {Number(
              data?.potentialSavingsGb || 0
            ).toLocaleString(
              undefined,
              {
                maximumFractionDigits: 2,
              }
            )}
            {" GB"}
          </strong>
        </div>

      </div>


      <div className="compression-table-title">
        Top Compression Opportunities
      </div>


      <div className="compression-table">

        <div className="compression-row compression-table-head">
          <span>
            Asset
          </span>

          <span>
            Source
          </span>

          <span>
            Saves
          </span>

          <span>
            GB
          </span>

          <span>
            Score
          </span>
        </div>


        {predictions
          .slice(0, 5)
          .map((item) => (

            <div
              className="compression-row"
              key={item.asset_id}
            >

              <span className="asset-id">
                {item.asset_id}
              </span>

              <span>
                {String(
                  item.source_type || "-"
                ).toUpperCase()}
              </span>

              <span className="saving-percent">
                {Number(
                  item.savings_percent || 0
                ).toFixed(1)}
                %
              </span>

              <span>
                {Number(
                  item.savings_gb || 0
                ).toFixed(1)}
              </span>

              <span>
                {Number(
                  item.priority_score || 0
                ).toFixed(1)}
              </span>

            </div>

          ))}

      </div>


      <div className="compression-note">
        Prediction inputs:
        entropy score,
        file extension,
        and file size.
      </div>

    </div>
  );
}