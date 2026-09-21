import React, {
  useEffect,
  useRef,
  useState,
} from "react";

import HealthScore from "../components/HealthScore";
import ForecastChart from "../components/ForecastChart";
import TimeTravelChart from "../components/TimeTravelChart";
import ActionCenter from "../components/ActionCenter";
import CompressionInsights from "../components/CompressionInsights";

import {
  UPLOAD_ACCEPT,
  uploadFiles,
  runCompressionAI,
} from "../api";

import "./Dashboard.css";


const TABS = {
  EXECUTIVE: "executive",
  OPERATIONAL: "operational",
  ACTION_CENTER: "action-center",
};


const ALL_FORMATS = [
  "json",
  "csv",
  "txt",
  "yaml",
];


const PREDICTION_LIMIT = 500;


// ============================================================
// DETECT SOURCE TYPE
// ============================================================

function getSourceType(fileName) {
  const name =
    String(
      fileName || ""
    ).toLowerCase();


  if (
    name.endsWith(".json") ||
    name.endsWith(".jsonl")
  ) {
    return "json";
  }


  if (
    name.endsWith(".csv")
  ) {
    return "csv";
  }


  if (
    name.endsWith(".txt")
  ) {
    return "txt";
  }


  if (
    name.endsWith(".yaml") ||
    name.endsWith(".yml")
  ) {
    return "yaml";
  }


  return null;
}


// ============================================================
// DASHBOARD
// ============================================================

export default function Dashboard({
  user,
}) {
  const [
    activeTab,
    setActiveTab,
  ] = useState(
    TABS.EXECUTIVE
  );


  const [
    dataVersion,
    setDataVersion,
  ] = useState(0);


  const [
    selectedFiles,
    setSelectedFiles,
  ] = useState([]);


  const [
    uploadState,
    setUploadState,
  ] = useState({
    status: "idle",
    message: "",
  });


  const fileInputRef =
    useRef(null);


  const predictionsBootstrapped =
    useRef(false);


  // ==========================================================
  // AUTOMATIC AI BOOTSTRAP
  //
  // Runs once when dashboard opens.
  //
  // This fixes:
  // CSV  → Score/Saves/Recommended = —
  // TXT  → Score/Saves/Recommended = —
  // YAML → missing predictions
  // ==========================================================

  useEffect(() => {

    if (
      predictionsBootstrapped.current
    ) {
      return;
    }


    predictionsBootstrapped.current =
      true;


    async function bootstrapPredictions() {

      console.log(
        "StorageWise: bootstrapping AI predictions..."
      );


      let successfulRuns =
        0;


      for (
        const sourceType
        of ALL_FORMATS
      ) {

        try {

          const result =
            await runCompressionAI(
              PREDICTION_LIMIT,
              sourceType
            );


          console.log(
            `${sourceType.toUpperCase()} AI processed:`,
            result?.processed
          );


          successfulRuns +=
            1;

        }

        catch (error) {

          console.error(
            `Unable to run AI for ${sourceType}:`,
            error
          );

        }

      }


      if (
        successfulRuns >
        0
      ) {

        setDataVersion(
          (current) =>
            current + 1
        );

      }


      console.log(
        "StorageWise: prediction bootstrap finished."
      );
    }


    bootstrapPredictions();

  }, []);


  // ==========================================================
  // FILE SELECTION
  // ==========================================================

  function handleFileSelection(
    event
  ) {
    const files =
      Array.from(
        event.target.files ||
        []
      );


    setSelectedFiles(
      files
    );


    setUploadState({
      status: "idle",
      message: "",
    });
  }


  // ==========================================================
  // UPLOAD
  // ==========================================================

  async function handleUpload() {

    if (
      selectedFiles.length ===
      0
    ) {

      setUploadState({
        status:
          "error",

        message:
          "Select at least one supported file.",
      });

      return;
    }


    const uploadedFormats =
      [
        ...new Set(
          selectedFiles
            .map(
              (file) =>
                getSourceType(
                  file.name
                )
            )
            .filter(
              Boolean
            )
        ),
      ];


    setUploadState({
      status:
        "uploading",

      message:
        "Uploading and normalizing storage records...",
    });


    try {

      // ======================================================
      // 1. INGEST DATA
      // ======================================================

      const result =
        await uploadFiles(
          selectedFiles
        );


      // ======================================================
      // 2. RUN AI FOR UPLOADED FORMATS
      // ======================================================

      setUploadState({
        status:
          "uploading",

        message:
          "Storage updated. Running AI predictions...",
      });


      const refreshedFormats =
        [];


      for (
        const sourceType
        of uploadedFormats
      ) {

        try {

          await runCompressionAI(
            PREDICTION_LIMIT,
            sourceType
          );


          refreshedFormats.push(
            sourceType
          );

        }

        catch (modelError) {

          console.error(
            `Prediction refresh failed for ${sourceType}:`,
            modelError
          );

        }

      }


      // ======================================================
      // 3. RESPONSE INFORMATION
      // ======================================================

      const imported =
        result
          ?.database_import
          ?.imported;


      const canonicalCount =
        result
          ?.summary
          ?.stats
          ?.canonical_records;


      const duplicates =
        result
          ?.summary
          ?.stats
          ?.duplicates;


      const invalid =
        result
          ?.summary
          ?.stats
          ?.invalid;


      let successMessage =
        "Upload completed successfully.";


      if (
        imported !== undefined &&
        imported !== null
      ) {

        successMessage =
          `${Number(
            imported
          ).toLocaleString()} records stored/refreshed in MySQL.`;

      }

      else if (
        canonicalCount !== undefined &&
        canonicalCount !== null
      ) {

        successMessage =
          `${Number(
            canonicalCount
          ).toLocaleString()} canonical records processed.`;

      }


      if (
        duplicates !== undefined &&
        Number(
          duplicates
        ) > 0
      ) {

        successMessage +=
          ` ${Number(
            duplicates
          ).toLocaleString()} duplicates detected.`;

      }


      if (
        invalid !== undefined &&
        Number(
          invalid
        ) > 0
      ) {

        successMessage +=
          ` ${Number(
            invalid
          ).toLocaleString()} invalid records.`;

      }


      if (
        refreshedFormats.length >
        0
      ) {

        successMessage +=
          ` AI refreshed for ${refreshedFormats
            .map(
              (format) =>
                format.toUpperCase()
            )
            .join(", ")}.`;

      }


      // ======================================================
      // 4. REFRESH DASHBOARD
      // ======================================================

      setDataVersion(
        (current) =>
          current + 1
      );


      setUploadState({
        status:
          "success",

        message:
          successMessage,
      });


      // ======================================================
      // 5. CLEAR FILE PICKER
      // ======================================================

      setSelectedFiles(
        []
      );


      if (
        fileInputRef.current
      ) {

        fileInputRef.current.value =
          "";

      }

    }

    catch (error) {

      console.error(
        "Upload failed:",
        error
      );


      setUploadState({
        status:
          "error",

        message:
          error?.message ||
          "Upload failed.",
      });

    }
  }


  // ==========================================================
  // REMOVE FILE
  // ==========================================================

  function removeSelectedFile(
    fileName
  ) {

    setSelectedFiles(
      (current) =>
        current.filter(
          (file) =>
            file.name !==
            fileName
        )
    );


    setUploadState({
      status:
        "idle",

      message:
        "",
    });
  }


  return (

    <div className="dashboard">

      {/* =====================================================
          HEADER
      ===================================================== */}

      <div className="dashboard__header">

        <div>

          <h1 className="dashboard__title">
            StorageWise AI
          </h1>

          <p className="dashboard__subtitle">
            Enterprise Storage Intelligence
          </p>

        </div>


        {user && (

          <div className="dashboard__user">

            <span className="dashboard__username">
              {user.username}
            </span>

            <span className="dashboard__role">
              {user.role}
            </span>

          </div>

        )}

      </div>


      {/* =====================================================
          TABS
      ===================================================== */}

      <nav
        className="dashboard__tabs"
        role="tablist"
        aria-label="Dashboard views"
      >

        <TabButton
          label="Executive View"
          isActive={
            activeTab ===
            TABS.EXECUTIVE
          }
          onClick={() =>
            setActiveTab(
              TABS.EXECUTIVE
            )
          }
        />


        <TabButton
          label="Operational View"
          isActive={
            activeTab ===
            TABS.OPERATIONAL
          }
          onClick={() =>
            setActiveTab(
              TABS.OPERATIONAL
            )
          }
        />


        <TabButton
          label="Action Center"
          isActive={
            activeTab ===
            TABS.ACTION_CENTER
          }
          onClick={() =>
            setActiveTab(
              TABS.ACTION_CENTER
            )
          }
        />

      </nav>


      {/* =====================================================
          CONTENT
      ===================================================== */}

      <section className="dashboard__content">

        {/* ===================================================
            EXECUTIVE VIEW
        =================================================== */}

        {activeTab ===
          TABS.EXECUTIVE && (

          <div
            className="dashboard__executive"
            role="tabpanel"
          >

            <div className="dashboard__panel">

              <HealthScore
                key={
                  `health-${dataVersion}`
                }
              />

            </div>


            {/* =================================================
                DATA INGESTION
            ================================================= */}

            <div className="dashboard__upload">

              <div className="dashboard__upload-header">

                <div>

                  <span className="dashboard__eyebrow">
                    DATA INGESTION
                  </span>

                  <h2 className="dashboard__upload-title">
                    Upload Storage Data
                  </h2>

                  <p className="dashboard__upload-subtitle">
                    Import JSON, CSV, TXT or YAML storage records into the unified canonical schema.
                  </p>

                </div>


                <div className="dashboard__upload-status">

                  <span className="dashboard__upload-status-dot" />

                  FastAPI connected

                </div>

              </div>


              {/* =================================================
                  FORMAT CARDS
              ================================================= */}

              <div className="dashboard__formats">

                <FormatBadge
                  label="JSON"
                  description="Telemetry"
                  active={
                    selectedFiles.some(
                      (file) =>
                        getSourceType(
                          file.name
                        ) ===
                        "json"
                    )
                  }
                />


                <FormatBadge
                  label="CSV"
                  description="Cloud metadata"
                  active={
                    selectedFiles.some(
                      (file) =>
                        getSourceType(
                          file.name
                        ) ===
                        "csv"
                    )
                  }
                />


                <FormatBadge
                  label="TXT"
                  description="Mainframe"
                  active={
                    selectedFiles.some(
                      (file) =>
                        getSourceType(
                          file.name
                        ) ===
                        "txt"
                    )
                  }
                />


                <FormatBadge
                  label="YAML"
                  description="VM configs"
                  active={
                    selectedFiles.some(
                      (file) =>
                        getSourceType(
                          file.name
                        ) ===
                        "yaml"
                    )
                  }
                />

              </div>


              {/* =================================================
                  FILE PICKER
              ================================================= */}

              <div className="dashboard__upload-box">

                <input
                  ref={
                    fileInputRef
                  }
                  type="file"
                  id="storagewise-upload"
                  className="dashboard__file-input"
                  accept={
                    UPLOAD_ACCEPT
                  }
                  multiple
                  onChange={
                    handleFileSelection
                  }
                />


                <label
                  htmlFor="storagewise-upload"
                  className="dashboard__file-label"
                >

                  <div className="dashboard__file-icon">
                    ↑
                  </div>


                  <div>

                    <strong>
                      Choose storage files
                    </strong>

                    <span>
                      JSON, JSONL, CSV, TXT, YAML or YML
                    </span>

                  </div>

                </label>


                <button
                  type="button"
                  className="dashboard__upload-button"
                  disabled={
                    selectedFiles.length ===
                      0 ||
                    uploadState.status ===
                      "uploading"
                  }
                  onClick={
                    handleUpload
                  }
                >

                  {
                    uploadState.status ===
                    "uploading"

                      ? "Processing..."

                      : "Upload & Process"
                  }

                </button>

              </div>


              {/* =================================================
                  SELECTED FILES
              ================================================= */}

              {selectedFiles.length >
                0 && (

                <div className="dashboard__selected-files">

                  <div className="dashboard__selected-title">

                    Selected files

                    <span>
                      {
                        selectedFiles.length
                      }
                    </span>

                  </div>


                  <div className="dashboard__selected-list">

                    {
                      selectedFiles.map(
                        (file) => (

                          <div
                            key={
                              `${file.name}-${file.size}-${file.lastModified}`
                            }
                            className="dashboard__selected-file"
                          >

                            <div>

                              <strong>
                                {file.name}
                              </strong>

                              <span>

                                {
                                  getSourceType(
                                    file.name
                                  )?.toUpperCase()
                                }

                                {" · "}

                                {
                                  formatFileSize(
                                    file.size
                                  )
                                }

                              </span>

                            </div>


                            <button
                              type="button"
                              aria-label={`Remove ${file.name}`}
                              onClick={() =>
                                removeSelectedFile(
                                  file.name
                                )
                              }
                            >
                              ×
                            </button>

                          </div>

                        )
                      )
                    }

                  </div>

                </div>

              )}


              {/* =================================================
                  STATUS MESSAGE
              ================================================= */}

              {
                uploadState.message &&
                (

                  <div
                    className={
                      `dashboard__upload-message dashboard__upload-message--${uploadState.status}`
                    }
                  >
                    {
                      uploadState.message
                    }
                  </div>

                )
              }

            </div>

          </div>

        )}


        {/* ===================================================
            OPERATIONAL VIEW
        =================================================== */}

        {activeTab ===
          TABS.OPERATIONAL && (

          <div
            className="dashboard__operational"
            role="tabpanel"
          >

            <div className="dashboard__model-grid">

              <div className="dashboard__model">

                <div className="dashboard__model-label">

                  <span>
                    MODEL 1
                  </span>

                  <strong>
                    Prophet Forecast
                  </strong>

                </div>


                <ForecastChart
                  key={
                    `forecast-${dataVersion}`
                  }
                />

              </div>


              <div className="dashboard__model">

                <div className="dashboard__model-label">

                  <span>
                    MODEL 2
                  </span>

                  <strong>
                    Linear Regression
                  </strong>

                </div>


                <CompressionInsights
                  key={
                    `compression-${dataVersion}`
                  }
                />

              </div>

            </div>


            <div className="dashboard__history">

              <div className="dashboard__section-heading">

                <div>

                  <h2>
                    Historical Storage
                  </h2>

                  <p>
                    Time-travel through historical storage usage.
                  </p>

                </div>

              </div>


              <TimeTravelChart
                key={
                  `history-${dataVersion}`
                }
              />

            </div>

          </div>

        )}


        {/* ===================================================
            ACTION CENTER
        =================================================== */}

        {activeTab ===
          TABS.ACTION_CENTER && (

          <div
            className="dashboard__panel"
            role="tabpanel"
          >

            <ActionCenter
              user={
                user
              }
              refreshKey={
                dataVersion
              }
            />

          </div>

        )}

      </section>

    </div>
  );
}


// ============================================================
// TAB BUTTON
// ============================================================

function TabButton({
  label,
  isActive,
  onClick,
}) {

  return (

    <button
      type="button"
      role="tab"
      aria-selected={
        isActive
      }
      className={
        `dashboard__tab ${
          isActive
            ? "dashboard__tab--active"
            : ""
        }`
      }
      onClick={
        onClick
      }
    >
      {label}
    </button>

  );
}


// ============================================================
// FORMAT BADGE
// ============================================================

function FormatBadge({
  label,
  description,
  active = false,
}) {

  return (

    <div
      className={
        `dashboard__format-badge ${
          active
            ? "dashboard__format-badge--active"
            : ""
        }`
      }
    >

      <strong>
        {label}
      </strong>

      <span>
        {description}
      </span>

    </div>

  );
}


// ============================================================
// FILE SIZE
// ============================================================

function formatFileSize(
  bytes
) {

  const value =
    Number(
      bytes
    ) || 0;


  if (
    value <
    1024
  ) {

    return `${value} B`;

  }


  if (
    value <
    1024 * 1024
  ) {

    return `${
      (
        value /
        1024
      ).toFixed(
        1
      )
    } KB`;

  }


  if (
    value <
    1024 *
    1024 *
    1024
  ) {

    return `${
      (
        value /
        (
          1024 *
          1024
        )
      ).toFixed(
        2
      )
    } MB`;

  }


  return `${
    (
      value /
      (
        1024 *
        1024 *
        1024
      )
    ).toFixed(
      2
    )
  } GB`;
}