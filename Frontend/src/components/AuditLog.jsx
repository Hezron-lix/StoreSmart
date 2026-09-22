import React, { useEffect, useMemo, useState } from "react";
import { getAuditLog, ApiError } from "../api";
import "./AuditLog.css";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "allowed", label: "Allowed" },
  { value: "blocked", label: "Blocked" },
];

export default function AuditLog() {
  const [entries, setEntries] = useState([]);
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus("loading");
      setErrorMessage("");
      try {
        const result = await getAuditLog();
        if (!cancelled) {
          setEntries(Array.isArray(result) ? result : []);
          setStatus("ready");
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(
            err instanceof ApiError
              ? err.message
              : "Unable to load the audit log."
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

  const filteredEntries = useMemo(() => {
    if (filter === "all") return entries;
    if (filter === "allowed") {
      return entries.filter((e) => e.outcome === "success");
    }
    if (filter === "blocked") {
      return entries.filter((e) => e.outcome !== "success");
    }
    return entries;
  }, [entries, filter]);

  if (status === "loading") {
    return (
      <div className="audit-log audit-log--loading">
        <p className="hds-text--sm hds-text--muted">Loading audit log…</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="audit-log audit-log--error">
        <p className="hds-text--sm">{errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="audit-log">

      <div className="audit-log__header">
        <div>
          <span className="section__eyebrow">Audit log</span>
          <h2 className="hds-heading--md">Every action attempted on the platform</h2>
          <p className="hds-text--sm hds-text--muted">
            Immutable record of every DELETE and COMPRESS request, with the
            policy that allowed, blocked, or flagged it for approval. Sourced
            from the append-only CSV at <code>logs/audit.csv</code>.
          </p>
        </div>
      </div>

      <div className="audit-log__filters" role="group" aria-label="Audit log filter">
        {FILTERS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={
              "audit-log__filter" +
              (filter === opt.value ? " audit-log__filter--active" : "")
            }
            onClick={() => setFilter(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="audit-log__summary hds-text--sm hds-text--muted">
        Showing <strong>{filteredEntries.length.toLocaleString()}</strong>{" "}
        of <strong>{entries.length.toLocaleString()}</strong> entries
      </div>

      {filteredEntries.length === 0 ? (
        <div className="audit-log__empty">
          <p className="hds-text--sm hds-text--muted">
            {entries.length === 0
              ? "No audit records yet. Actions taken in the Action Center will appear here."
              : "No entries match the current filter."}
          </p>
        </div>
      ) : (
        <div className="audit-log__table-wrap">
          <table className="audit-log__table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>User</th>
                <th>Role</th>
                <th>Action</th>
                <th>File</th>
                <th>Policy</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {filteredEntries.map((entry, index) => (
                <tr key={`${entry.timestamp}-${entry.file}-${index}`}>
                  <td className="audit-log__mono">{entry.timestamp}</td>
                  <td>{entry.user}</td>
                  <td>{entry.role}</td>
                  <td className="audit-log__mono">{entry.action}</td>
                  <td className="audit-log__mono">{entry.file}</td>
                  <td className="audit-log__mono">{entry.policyId || "—"}</td>
                  <td><OutcomeTag outcome={entry.outcome} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}

function OutcomeTag({ outcome }) {
  if (outcome === "success") {
    return <span className="audit-log__tag audit-log__tag--success">Allowed</span>;
  }
  if (outcome === "blocked") {
    return <span className="audit-log__tag audit-log__tag--blocked">Blocked</span>;
  }
  if (outcome === "APPROVAL_REQUIRED") {
    return <span className="audit-log__tag audit-log__tag--warning">Approval required</span>;
  }
  return <span className="audit-log__tag">{outcome || "—"}</span>;
}
