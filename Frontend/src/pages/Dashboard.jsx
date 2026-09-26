import React, { useEffect, useRef, useState } from "react";
import ExecutiveHero from "../components/ExecutiveHero";
import ForecastChart from "../components/ForecastChart";
import TimeTravelChart from "../components/TimeTravelChart";
import ActionCenter from "../components/ActionCenter";
import CompressionInsights from "../components/CompressionInsights";
import AuditLog from "../components/AuditLog";
import { UPLOAD_ACCEPT, uploadFiles, runCompressionAI } from "../api";
import "./Dashboard.css";

const TABS = {
  EXECUTIVE: "executive",
  DATA: "data",
  OPERATIONAL: "operational",
  ACTION_CENTER: "action-center",
  AUDIT_LOG: "audit-log",
};

const TAB_CONTEXT = {
  [TABS.EXECUTIVE]: "Overall storage health at a glance.",
  [TABS.DATA]: "Upload new storage records into the canonical schema.",
  [TABS.OPERATIONAL]: "Forecast, compression, and historical usage.",
  [TABS.ACTION_CENTER]: "Prioritized files to compress or remove.",
  [TABS.AUDIT_LOG]: "Every action attempted on the platform.",
};

const ALL_FORMATS = ["json", "csv", "txt", "yaml"];
const PREDICTION_LIMIT = 500;

function getSourceType(fileName) {
  const name = String(fileName || "").toLowerCase();

  if (name.endsWith(".json") || name.endsWith(".jsonl")) {
    return "json";
  }

  if (name.endsWith(".csv")) {
    return "csv";
  }

  if (name.endsWith(".txt")) {
    return "txt";
  }

  if (name.endsWith(".yaml") || name.endsWith(".yml")) {
    return "yaml";
  }

  return null;
}

export default function Dashboard({ user }) {
  const [activeTab, setActiveTab] = useState(TABS.EXECUTIVE);
  const [dataVersion, setDataVersion] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadState, setUploadState] = useState({
    status: "idle",
    message: "",
  });

  const fileInputRef = useRef(null);
  const predictionsBootstrapped = useRef(false);

  useEffect(() => {
    if (predictionsBootstrapped.current) {
      return;
    }

    predictionsBootstrapped.current = true;

    async function bootstrapPredictions() {
      console.log("StoreSmart: bootstrapping AI predictions...");

      let successfulRuns = 0;

      for (const sourceType of ALL_FORMATS) {
        try {
          const result = await runCompressionAI(
            PREDICTION_LIMIT,
            sourceType
          );

          console.log(
            `${sourceType.toUpperCase()} AI processed:`,
            result?.processed
          );

          successfulRuns += 1;
        } catch (error) {
          console.error(
            `Unable to run AI for ${sourceType}:`,
            error
          );
        }
      }

      if (successfulRuns > 0) {
        setDataVersion((current) => current + 1);
      }

      console.log("StoreSmart: prediction bootstrap finished.");
    }

    bootstrapPredictions();
  }, []);

  function handleFileSelection(event) {
    const files = Array.from(event.target.files || []);

    setSelectedFiles(files);

    setUploadState({
      status: "idle",
      message: "",
    });
  }

  async function handleUpload() {
    if (selectedFiles.length === 0) {
      setUploadState({
        status: "error",
        message: "Select at least one supported file.",
      });

      return;
    }

    const uploadedFormats = [
      ...new Set(
        selectedFiles
          .map((file) => getSourceType(file.name))
          .filter(Boolean)
      ),
    ];

    setUploadState({
      status: "uploading",
      message: "Uploading and normalizing storage records...",
    });

    try {
      const result = await uploadFiles(selectedFiles);

      setUploadState({
        status: "uploading",
        message: "Storage updated. Running AI predictions...",
      });

      const refreshedFormats = [];

      for (const sourceType of uploadedFormats) {
        try {
          await runCompressionAI(PREDICTION_LIMIT, sourceType);
          refreshedFormats.push(sourceType);
        } catch (modelError) {
          console.error(
            `Prediction refresh failed for ${sourceType}:`,
            modelError
          );
        }
      }

      const imported = result?.database_import?.imported;
      const canonicalCount = result?.summary?.stats?.canonical_records;
      const duplicates = result?.summary?.stats?.duplicates;
      const invalid = result?.summary?.stats?.invalid;

      let successMessage = "Upload completed successfully.";

      if (imported !== undefined && imported !== null) {
        successMessage = `${Number(imported).toLocaleString()} records stored/refreshed in MySQL.`;
      } else if (canonicalCount !== undefined && canonicalCount !== null) {
        successMessage = `${Number(canonicalCount).toLocaleString()} canonical records processed.`;
      }

      if (duplicates !== undefined && Number(duplicates) > 0) {
        successMessage += ` ${Number(duplicates).toLocaleString()} duplicates detected.`;
      }

      if (invalid !== undefined && Number(invalid) > 0) {
        successMessage += ` ${Number(invalid).toLocaleString()} invalid records.`;
      }

      if (refreshedFormats.length > 0) {
        successMessage += ` AI refreshed for ${refreshedFormats
          .map((format) => format.toUpperCase())
          .join(", ")}.`;
      }

      setDataVersion((current) => current + 1);

      setUploadState({
        status: "success",
        message: successMessage,
      });

      setSelectedFiles([]);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      console.error("Upload failed:", error);

      setUploadState({
        status: "error",
        message: error?.message || "Upload failed.",
      });
    }
  }

  function removeSelectedFile(fileName) {
    setSelectedFiles((current) =>
      current.filter((file) => file.name !== fileName)
    );

    setUploadState({
      status: "idle",
      message: "",
    });
  }

  return (
    <div className="dashboard">
      <div className="dashboard__inner">

        {/* ---------- Tabs (pill switch) ---------- */}
        <nav
          className="dashboard__tabs"
          role="tablist"
          aria-label="Dashboard views"
        >
          <TabButton
            label="Executive"
            isActive={activeTab === TABS.EXECUTIVE}
            onClick={() => setActiveTab(TABS.EXECUTIVE)}
          />
          <TabButton
            label="Data"
            isActive={activeTab === TABS.DATA}
            onClick={() => setActiveTab(TABS.DATA)}
          />
          <TabButton
            label="Operational"
            isActive={activeTab === TABS.OPERATIONAL}
            onClick={() => setActiveTab(TABS.OPERATIONAL)}
          />
          <TabButton
            label="Action Center"
            isActive={activeTab === TABS.ACTION_CENTER}
            onClick={() => setActiveTab(TABS.ACTION_CENTER)}
          />
          <TabButton
            label="Audit Log"
            isActive={activeTab === TABS.AUDIT_LOG}
            onClick={() => setActiveTab(TABS.AUDIT_LOG)}
          />
        </nav>

        <p className="dashboard__context">{TAB_CONTEXT[activeTab]}</p>

        {/* ---------- Content ---------- */}
        <section className="dashboard__content">

          {activeTab === TABS.EXECUTIVE && (
            <div className="dashboard__panel" role="tabpanel">
              <ExecutiveHero key={`health-${dataVersion}`} />
            </div>
          )}

          {activeTab === TABS.DATA && (
            <div className="dashboard__panel" role="tabpanel">
              <div className="dashboard__section-heading">
                <span className="section__eyebrow">Data ingestion</span>
                <h2 className="hds-heading--md">Upload storage records</h2>
                <p className="hds-text--sm hds-text--muted">
                  Files are parsed into a unified schema, deduplicated by SHA-256 hash,
                  and stored in MySQL. Supported formats: JSON, CSV, TXT, YAML.
                </p>
              </div>

              {/* --- Upload card --- */}
              <div className="hds-card hds-card--accent dashboard__upload">
                <div className="dashboard__upload-header">
                  <div>
                    <span className="section__eyebrow">Data ingestion</span>
                    <h2 className="hds-heading--md">Upload storage data</h2>
                    <p className="hds-text--sm hds-text--muted">
                      Import JSON, CSV, TXT or YAML storage records into the unified canonical schema.
                    </p>
                  </div>
                  <span className="hds-tag hds-tag--success">
                    <span className="dashboard__status-dot" aria-hidden="true" />
                    FastAPI connected
                  </span>
                </div>

                <div className="dashboard__formats">
                  <FormatBadge label="JSON" description="Telemetry" active={selectedFiles.some((f) => getSourceType(f.name) === "json")} />
                  <FormatBadge label="CSV" description="Cloud metadata" active={selectedFiles.some((f) => getSourceType(f.name) === "csv")} />
                  <FormatBadge label="TXT" description="Mainframe" active={selectedFiles.some((f) => getSourceType(f.name) === "txt")} />
                  <FormatBadge label="YAML" description="VM configs" active={selectedFiles.some((f) => getSourceType(f.name) === "yaml")} />
                </div>

                <div className="dashboard__upload-box">
                  <input
                    ref={fileInputRef}
                    type="file"
                    id="storesmart-upload"
                    className="dashboard__file-input"
                    accept={UPLOAD_ACCEPT}
                    multiple
                    onChange={handleFileSelection}
                  />
                  <label htmlFor="storesmart-upload" className="dashboard__file-label">
                    <span className="dashboard__file-icon" aria-hidden="true">↑</span>
                    <span className="dashboard__file-text">
                      <strong>Choose storage files</strong>
                      <span className="hds-text--sm hds-text--muted">JSON, JSONL, CSV, TXT, YAML or YML</span>
                    </span>
                  </label>
                  <button
                    type="button"
                    className="hds-button hds-button--primary dashboard__upload-button"
                    disabled={selectedFiles.length === 0 || uploadState.status === "uploading"}
                    onClick={handleUpload}
                  >
                    {uploadState.status === "uploading" ? "Processing…" : "Upload & process"}
                  </button>
                </div>

                {selectedFiles.length > 0 && (
                  <div className="dashboard__selected">
                    <div className="dashboard__selected-title">
                      <span className="hds-text--sm hds-text--muted">Selected files</span>
                      <span className="hds-tag">{selectedFiles.length}</span>
                    </div>
                    <ul className="dashboard__selected-list">
                      {selectedFiles.map((file) => (
                        <li
                          key={`${file.name}-${file.size}-${file.lastModified}`}
                          className="dashboard__selected-file"
                        >
                          <div>
                            <strong className="hds-text--sm hds-text--solid">{file.name}</strong>
                            <span className="hds-text--sm hds-text--muted">
                              {getSourceType(file.name)?.toUpperCase()}
                              {" · "}
                              {formatFileSize(file.size)}
                            </span>
                          </div>
                          <button
                            type="button"
                            className="dashboard__selected-remove"
                            aria-label={`Remove ${file.name}`}
                            onClick={() => removeSelectedFile(file.name)}
                          >
                            ×
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {uploadState.message && (
                  <div
                    className={`dashboard__upload-message dashboard__upload-message--${uploadState.status}`}
                  >
                    {uploadState.message}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === TABS.OPERATIONAL && (
            <div className="dashboard__panel" role="tabpanel">

              <div className="dashboard__feature">
                <span className="section__eyebrow">Prophet forecast</span>
                <ForecastChart key={`forecast-${dataVersion}`} />
              </div>

              <div className="dashboard__panel-grid dashboard__panel-grid--operational">
                <div className="dashboard__panel-col">
                  <span className="section__eyebrow">Linear regression</span>
                  <CompressionInsights key={`compression-${dataVersion}`} />
                </div>
                <div className="dashboard__panel-col">
                  <span className="section__eyebrow">Time travel</span>
                  <TimeTravelChart key={`history-${dataVersion}`} />
                </div>
              </div>

            </div>
          )}

          {activeTab === TABS.ACTION_CENTER && (
            <div className="dashboard__panel" role="tabpanel">
              <ActionCenter user={user} refreshKey={dataVersion} />
            </div>
          )}

          {activeTab === TABS.AUDIT_LOG && (
            <div className="dashboard__panel" role="tabpanel">
              <AuditLog />
            </div>
          )}

        </section>
      </div>
    </div>
  );
}

function TabButton({ label, isActive, onClick }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      className={
        "dashboard__tab" + (isActive ? " dashboard__tab--active" : "")
      }
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function FormatBadge({ label, description, active = false }) {
  return (
    <div
      className={
        "dashboard__format-badge" +
        (active ? " dashboard__format-badge--active" : "")
      }
    >
      <strong>{label}</strong>
      <span>{description}</span>
    </div>
  );
}

function formatFileSize(bytes) {
  const value = Number(bytes) || 0;

  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(2)} MB`;
  }

  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}