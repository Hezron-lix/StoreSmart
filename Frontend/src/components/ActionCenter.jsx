import React, {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  ApiError,
  executeAction,
  getActionItems,
} from "../api";

import "./ActionCenter.css";


const DISPLAY_LIMIT = 50;

const FORMATS = [
  "json",
  "csv",
  "txt",
  "yaml",
];


export default function ActionCenter({
  user,
  refreshKey = 0,
}) {
  const isSuperAdmin =
    String(user?.role || "")
      .trim()
      .toLowerCase() === "super-admin";

  const [items, setItems] = useState([]);
  const [selectedFormat, setSelectedFormat] = useState("json");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [formatCounts, setFormatCounts] = useState({
    json: 0,
    csv: 0,
    txt: 0,
    yaml: 0,
  });

  const [status, setStatus] = useState("loading");
  const [isFetching, setIsFetching] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [rowState, setRowState] = useState({});

  // ==========================================================
  // LOAD PAGINATED ASSETS FOR CURRENT FORMAT
  // ==========================================================

  const loadItems = useCallback(
    async (format = selectedFormat, pageNum = page) => {
      setErrorMessage("");

      try {
        const result = await getActionItems({
          sourceType: format,
          page: pageNum,
          limit: DISPLAY_LIMIT,
        });

        setItems(result.items || []);
        setTotal(result.total || 0);
        setTotalPages(result.totalPages || 1);
        if (result.formatCounts) {
          setFormatCounts(result.formatCounts);
        }
        setStatus("ready");
      } catch (err) {
        console.error("Action Center load error:", err);
        setErrorMessage(
          err instanceof ApiError ? err.message : "Unable to load assets."
        );
        setStatus("error");
      } finally {
        setIsFetching(false);
      }
    },
    [selectedFormat, page]
  );

  // Initial load + reload on refreshKey
  useEffect(() => {
    setStatus("loading");
    setPage(1);
    loadItems("json", 1);
  }, [refreshKey]);

  function handleFormatChange(newFormat) {
    if (newFormat === selectedFormat) return;
    setSelectedFormat(newFormat);
    setPage(1);
    setIsFetching(true);
    loadItems(newFormat, 1);
  }

  function handlePageChange(newPage) {
    if (newPage < 1 || newPage > totalPages || newPage === page) return;
    setPage(newPage);
    setIsFetching(true);
    loadItems(selectedFormat, newPage);
  }

  // ==========================================================
  // EXECUTE ACTION
  // ==========================================================

  async function handleAction(item, action) {
    setRowState((prev) => ({
      ...prev,
      [item.fileId]: {
        pending: true,
        currentAction: action,
        message: "",
      },
    }));

    try {
      const result = await executeAction({
        fileId: item.fileId,
        action,
      });

      if (action === "DELETE") {
        setItems((current) =>
          current.filter((row) => row.fileId !== item.fileId)
        );
        setTotal((prev) => Math.max(0, prev - 1));
        setFormatCounts((prev) => ({
          ...prev,
          [selectedFormat]: Math.max(0, (prev[selectedFormat] || 1) - 1),
        }));

        setRowState((prev) => ({
          ...prev,
          [item.fileId]: {
            pending: false,
            currentAction: null,
            message: "File deleted successfully from storage.",
            tone: "success",
          },
        }));
        return;
      }

      setRowState((prev) => ({
        ...prev,
        [item.fileId]: {
          pending: false,
          currentAction: null,
          message:
            result.outcome === "APPROVAL_REQUIRED"
              ? "Action flagged: requires secondary approval under governance policy."
              : result.message || "Compression applied successfully.",
          tone:
            result.outcome === "APPROVAL_REQUIRED" ? "warning" : "success",
        },
      }));
    } catch (err) {
      setRowState((prev) => ({
        ...prev,
        [item.fileId]: {
          pending: false,
          currentAction: null,
          message:
            err instanceof ApiError
              ? err.message
              : "Action failed. Check storage connectivity.",
          tone: "error",
        },
      }));
    }
  }

  // ==========================================================
  // LOADING STATE
  // ==========================================================

  if (status === "loading") {
    return (
      <div className="action-center hds-card">
        <div className="action-center__header">
          <div className="action-center__eyebrow section__eyebrow">
            Decision Engine
          </div>
          <h2 className="hds-heading--md">Candidate files for remediation</h2>
        </div>
        <div className="action-center__loading">
          <div className="action-center__spinner" />
          <p className="hds-text--sm hds-text--muted">
            Loading candidate assets from database…
          </p>
        </div>
      </div>
    );
  }

  // ==========================================================
  // ERROR STATE
  // ==========================================================

  if (status === "error") {
    return (
      <div className="action-center hds-card">
        <div className="action-center__header">
          <div className="action-center__eyebrow section__eyebrow">
            Decision Engine
          </div>
          <h2 className="hds-heading--md">Candidate files for remediation</h2>
        </div>
        <div className="action-center__error">
          <p className="hds-text--sm">{errorMessage}</p>
          <button
            type="button"
            className="hds-button hds-button--secondary hds-button--small"
            onClick={() => loadItems(selectedFormat, page)}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const pageNumbers = getPageNumbers(page, totalPages);

  return (
    <div className="action-center hds-card">
      {/* =====================================================
          HEADER
      ===================================================== */}

      <div className="action-center__header">
        <div>
          <div className="action-center__eyebrow section__eyebrow">
            Decision Engine
          </div>
          <h2 className="hds-heading--md">Candidate files for remediation</h2>
          <p className="hds-text--sm hds-text--muted">
            Recommended actions generated by StoreSmart's AI models. Super-Admins
            can execute DELETE or COMPRESS directly.
          </p>
        </div>
      </div>

      {/* =====================================================
          DYNAMIC SUMMARY
      ===================================================== */}

      <div className="action-center__summary">
        Showing{" "}
        <strong>
          {total === 0
            ? 0
            : `${(page - 1) * DISPLAY_LIMIT + 1}–${Math.min(
                page * DISPLAY_LIMIT,
                total
              )}`}
        </strong>{" "}
        of <strong>{total.toLocaleString()}</strong>{" "}
        {selectedFormat.toUpperCase()} assets
      </div>

      {/* =====================================================
          FORMAT FILTERS
      ===================================================== */}

      <div className="action-center__formats">
        {FORMATS.map((format) => (
          <button
            key={format}
            type="button"
            className={`action-center__format ${
              selectedFormat === format ? "action-center__format--active" : ""
            }`}
            onClick={() => handleFormatChange(format)}
          >
            {format.toUpperCase()}
            <span>{(formatCounts[format] || 0).toLocaleString()}</span>
          </button>
        ))}
      </div>

      {/* =====================================================
          TABLE
      ===================================================== */}

      <div
        className={`action-center__table-wrap ${
          isFetching ? "action-center__table-wrap--fetching" : ""
        }`}
      >
        <table className="action-center__table">
          <thead>
            <tr>
              <th>File</th>
              <th>Source</th>
              <th>Department</th>
              <th>Size</th>
              <th>Priority</th>
              <th>Saves %</th>
              <th>Suggested</th>
              {isSuperAdmin && <th>Action</th>}
            </tr>
          </thead>

          <tbody>
            {items.length === 0 ? (
              <tr>
                <td
                  colSpan={isSuperAdmin ? 8 : 7}
                  className="action-center__empty"
                >
                  No {selectedFormat.toUpperCase()} assets currently exist in
                  the database.
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const state = rowState[item.fileId] || {};

                return (
                  <React.Fragment key={item.fileId}>
                    <tr>
                      <td className="action-center__file">
                        <div>{item.fileName}</div>
                        <small>{item.fileId}</small>
                      </td>

                      <td>{String(item.sourceType).toUpperCase()}</td>

                      <td>{item.department}</td>

                      <td className="action-center__mono">
                        {formatSize(item.sizeGb)}
                      </td>

                      <td className="action-center__mono">
                        {item.score !== null && item.score !== undefined
                          ? Number(item.score).toFixed(2)
                          : "—"}
                      </td>

                      <td className="action-center__mono">
                        {item.savingsPct !== null &&
                        item.savingsPct !== undefined
                          ? `${Number(item.savingsPct).toFixed(2)}%`
                          : "—"}
                      </td>

                      <td>
                        <span
                          className={`action-center__suggested action-center__suggested--${
                            item.recommendedAction || "none"
                          }`}
                        >
                          {item.recommendedAction
                            ? capitalize(item.recommendedAction)
                            : "—"}
                        </span>
                      </td>

                      {isSuperAdmin && (
                        <td>
                          <div className="action-center__actions">
                            <button
                              type="button"
                              className="action-center__action action-center__action--delete"
                              disabled={state.pending}
                              onClick={() => handleAction(item, "DELETE")}
                            >
                              {state.pending && state.currentAction === "DELETE"
                                ? "..."
                                : "DEL"}
                            </button>

                            <button
                              type="button"
                              className="action-center__action action-center__action--compress"
                              disabled={state.pending}
                              onClick={() => handleAction(item, "COMPRESS")}
                            >
                              {state.pending &&
                              state.currentAction === "COMPRESS"
                                ? "..."
                                : "COM"}
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>

                    {state.message && (
                      <tr className="action-center__message-row">
                        <td colSpan={isSuperAdmin ? 8 : 7}>
                          <span
                            className={`action-center__message action-center__message--${
                              state.tone || "success"
                            }`}
                          >
                            {state.message}
                          </span>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* =====================================================
          PAGINATION BAR
      ===================================================== */}

      {totalPages > 1 && (
        <div className="action-center__pagination">
          <div className="action-center__pagination-info">
            Page <strong>{page}</strong> of{" "}
            <strong>{totalPages.toLocaleString()}</strong>
          </div>

          <div className="action-center__pagination-controls">
            <button
              type="button"
              className="hds-button hds-button--secondary hds-button--small"
              disabled={page <= 1 || isFetching}
              onClick={() => handlePageChange(1)}
              title="First page"
            >
              « First
            </button>

            <button
              type="button"
              className="hds-button hds-button--secondary hds-button--small"
              disabled={page <= 1 || isFetching}
              onClick={() => handlePageChange(page - 1)}
            >
              ‹ Prev
            </button>

            <div className="action-center__page-numbers">
              {pageNumbers.map((p, idx) =>
                p === "..." ? (
                  <span
                    key={`ellipsis-${idx}`}
                    className="action-center__ellipsis"
                  >
                    …
                  </span>
                ) : (
                  <button
                    key={p}
                    type="button"
                    className={`action-center__page-num ${
                      p === page ? "action-center__page-num--active" : ""
                    }`}
                    disabled={isFetching}
                    onClick={() => handlePageChange(p)}
                  >
                    {p}
                  </button>
                )
              )}
            </div>

            <button
              type="button"
              className="hds-button hds-button--secondary hds-button--small"
              disabled={page >= totalPages || isFetching}
              onClick={() => handlePageChange(page + 1)}
            >
              Next ›
            </button>

            <button
              type="button"
              className="hds-button hds-button--secondary hds-button--small"
              disabled={page >= totalPages || isFetching}
              onClick={() => handlePageChange(totalPages)}
              title="Last page"
            >
              Last »
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


function getPageNumbers(currentPage, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages = [];
  if (currentPage <= 4) {
    pages.push(1, 2, 3, 4, 5, "...", totalPages);
  } else if (currentPage >= totalPages - 3) {
    pages.push(
      1,
      "...",
      totalPages - 4,
      totalPages - 3,
      totalPages - 2,
      totalPages - 1,
      totalPages
    );
  } else {
    pages.push(
      1,
      "...",
      currentPage - 1,
      currentPage,
      currentPage + 1,
      "...",
      totalPages
    );
  }
  return pages;
}


function capitalize(value) {
  if (!value) {
    return "";
  }
  const text = String(value);
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}


function formatSize(value) {
  const size = Number(value);
  if (!Number.isFinite(size)) {
    return "0 GB";
  }
  if (size < 0.01) {
    return `${size.toFixed(4)} GB`;
  }
  return `${size.toFixed(2)} GB`;
}