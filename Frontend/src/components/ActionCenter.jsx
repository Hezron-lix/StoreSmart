import React, {
  useCallback,
  useEffect,
  useMemo,
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
    String(
      user?.role || ""
    )
      .trim()
      .toLowerCase() ===
    "super-admin";


  const [
    items,
    setItems,
  ] = useState([]);


  const [
    selectedFormat,
    setSelectedFormat,
  ] = useState(
    "json"
  );


  const [
    status,
    setStatus,
  ] = useState(
    "loading"
  );


  const [
    errorMessage,
    setErrorMessage,
  ] = useState("");


  const [
    rowState,
    setRowState,
  ] = useState({});


  // ==========================================================
  // LOAD CURRENT DATABASE ASSETS
  // ==========================================================

  const loadItems =
    useCallback(
      async () => {

        setStatus(
          "loading"
        );

        setErrorMessage(
          ""
        );


        try {

          const result =
            await getActionItems();


          const sorted =
            [...result].sort(
              (a, b) =>
                Number(
                  b.score || 0
                ) -
                Number(
                  a.score || 0
                )
            );


          setItems(
            sorted
          );


          setStatus(
            "ready"
          );

        }

        catch (err) {

          console.error(
            "Action Center load error:",
            err
          );


          setErrorMessage(
            err instanceof ApiError
              ? err.message
              : "Unable to load assets."
          );


          setStatus(
            "error"
          );
        }
      },
      []
    );


  // Initial load + reload whenever upload finishes.
  useEffect(
    () => {
      loadItems();
    },
    [
      loadItems,
      refreshKey,
    ]
  );


  // ==========================================================
  // LIVE COUNTS FROM DATABASE DATA
  // ==========================================================

  const formatCounts =
    useMemo(
      () => {

        const counts = {
          json: 0,
          csv: 0,
          txt: 0,
          yaml: 0,
        };


        for (
          const item of items
        ) {

          const format =
            String(
              item.sourceType ||
              ""
            )
              .trim()
              .toLowerCase();


          if (
            Object.prototype
              .hasOwnProperty
              .call(
                counts,
                format
              )
          ) {
            counts[
              format
            ] += 1;
          }
        }


        return counts;

      },
      [items]
    );


  // ==========================================================
  // FILTER CURRENT FORMAT
  // ==========================================================

  const filteredItems =
    useMemo(
      () =>
        items.filter(
          (item) =>
            String(
              item.sourceType ||
              ""
            )
              .toLowerCase()
              ===
            selectedFormat
        ),
      [
        items,
        selectedFormat,
      ]
    );


  const visibleItems =
    filteredItems.slice(
      0,
      DISPLAY_LIMIT
    );


  // ==========================================================
  // EXECUTE ACTION
  // ==========================================================

  async function handleAction(
    item,
    action
  ) {

    setRowState(
      (prev) => ({
        ...prev,

        [item.fileId]: {
          pending:
            true,

          currentAction:
            action,

          message:
            "",
        },
      })
    );


    try {

      const result =
        await executeAction({
          fileId:
            item.fileId,

          action,
        });


      // ------------------------------------------------------
      // DELETE:
      // Remove row immediately from frontend.
      // Backend already removes it from MySQL.
      // ------------------------------------------------------

      if (
        action ===
        "DELETE"
      ) {

        setItems(
          (current) =>
            current.filter(
              (row) =>
                row.fileId !==
                item.fileId
            )
        );


        setRowState(
          (prev) => ({
            ...prev,

            [item.fileId]: {
              pending:
                false,

              tone:
                "success",

              message:
                result?.message ||
                "Deleted successfully.",
            },
          })
        );


        return;
      }


      // ------------------------------------------------------
      // COMPRESS:
      // Keep row and reload latest size from database.
      // ------------------------------------------------------

      setRowState(
        (prev) => ({
          ...prev,

          [item.fileId]: {
            pending:
              false,

            tone:
              "success",

            message:
              result?.message ||
              "Compressed successfully.",
          },
        })
      );


      await loadItems();

    }

    catch (err) {

      if (
        err instanceof ApiError &&
        err.status === 403 &&
        (err.body?.decision === "APPROVAL_REQUIRED" || err.body?.approval_required === true)
      ) {
        setRowState(
          (prev) => ({
            ...prev,

            [item.fileId]: {
              pending:
                false,

              tone:
                "warning",

              message:
                `Dual-Approval Required: ${
                  err.body?.reason ||
                  err.body?.governance?.reason ||
                  err.body?.message ||
                  "High-risk action requires dual approval."
                }`,
            },
          })
        );

        return;
      }

      if (
        err instanceof ApiError &&
        err.status === 403 &&
        (err.body?.decision === "BLOCKED" || err.body?.status === "blocked")
      ) {

        const policyId =
          err.body?.governance?.policyId ||
          err.body?.policy_id ||
          "Policy";

        const reason =
          err.body?.governance?.reason ||
          err.body?.reason ||
          err.body?.message ||
          "Action blocked.";

        setRowState(
          (prev) => ({
            ...prev,

            [item.fileId]: {
              pending:
                false,

              tone:
                "blocked",

              message:
                `BLOCKED [${policyId}]: ${reason}`,
            },
          })
        );

        return;
      }

      setRowState(
        (prev) => ({
          ...prev,

          [item.fileId]: {
            pending:
              false,

            tone:
              "error",

            message:
              err?.body?.detail ||
              err?.body?.message ||
              err?.message ||
              "Action failed.",
          },
        })
      );
    }
  }


  // ==========================================================
  // STATES
  // ==========================================================

  if (
    status ===
    "loading"
  ) {
    return (
      <div className="action-center action-center--loading">
        Loading current database assets...
      </div>
    );
  }


  if (
    status ===
    "error"
  ) {
    return (
      <div className="action-center action-center--error">
        {errorMessage}
      </div>
    );
  }


  return (

    <div className="action-center">

      {/* =====================================================
          HEADER
      ===================================================== */}

      <div className="action-center__header">

        <div className="action-center__title">
          Action Center
        </div>

        <div className="action-center__subtitle">

          {isSuperAdmin
            ? "Review assets and execute Delete or Compress actions."
            : "Review prioritized storage assets."}

        </div>

        <p className="action-center__hint hds-text--sm hds-text--muted">
          Rows are ranked by Priority Score. Higher = more urgent. "Saves %" shows
          predicted compression. "Suggested" is the AI's recommended action.
          Only Super-Admins can execute actions.
        </p>

      </div>


      {/* =====================================================
          DYNAMIC SUMMARY
      ===================================================== */}

      <div className="action-center__summary">

        Showing{" "}

        <strong>
          {
            Math.min(
              DISPLAY_LIMIT,
              filteredItems.length
            )
          }
        </strong>

        {" "}of{" "}

        <strong>
          {
            filteredItems.length
              .toLocaleString()
          }
        </strong>

        {" "}

        {
          selectedFormat
            .toUpperCase()
        }

        {" "}assets

      </div>


      {/* =====================================================
          FORMAT FILTERS
      ===================================================== */}

      <div className="action-center__formats">

        {
          FORMATS.map(
            (format) => (

              <button
                key={
                  format
                }
                type="button"
                className={
                  `action-center__format ${
                    selectedFormat ===
                    format
                      ? "action-center__format--active"
                      : ""
                  }`
                }
                onClick={() =>
                  setSelectedFormat(
                    format
                  )
                }
              >

                {
                  format
                    .toUpperCase()
                }

                <span>
                  {
                    formatCounts[
                      format
                    ].toLocaleString()
                  }
                </span>

              </button>

            )
          )
        }

      </div>


      {/* =====================================================
          TABLE
      ===================================================== */}

      <div className="action-center__table-wrap">

        <table className="action-center__table">

          <thead>

            <tr>

              <th>
                File
              </th>

              <th>
                Source
              </th>

              <th>
                Department
              </th>

              <th>
                Size
              </th>

              <th>
                Priority
              </th>

              <th>
                Saves %
              </th>

              <th>
                Suggested
              </th>

              {
                isSuperAdmin &&
                (
                  <th>
                    Action
                  </th>
                )
              }

            </tr>

          </thead>


          <tbody>

            {
              visibleItems.length ===
              0
                ? (

                  <tr>

                    <td
                      colSpan={
                        isSuperAdmin
                          ? 8
                          : 7
                      }
                      className="action-center__empty"
                    >
                      No{" "}
                      {
                        selectedFormat
                          .toUpperCase()
                      }{" "}
                      assets currently exist in the database.
                    </td>

                  </tr>

                )

                : visibleItems.map(
                    (item) => {

                      const state =
                        rowState[
                          item.fileId
                        ] || {};


                      return (

                        <React.Fragment
                          key={
                            item.fileId
                          }
                        >

                          <tr>

                            <td className="action-center__file">

                              <div>
                                {
                                  item.fileName
                                }
                              </div>

                              <small>
                                {
                                  item.fileId
                                }
                              </small>

                            </td>


                            <td>
                              {
                                String(
                                  item.sourceType
                                )
                                  .toUpperCase()
                              }
                            </td>


                            <td>
                              {
                                item.department
                              }
                            </td>


                            <td className="action-center__mono">
                              {
                                formatSize(
                                  item.sizeGb
                                )
                              }
                            </td>


                            <td className="action-center__mono">
                              {
                                item.score !==
                                  null &&
                                item.score !==
                                  undefined

                                  ? Number(
                                      item.score
                                    ).toFixed(
                                      2
                                    )

                                  : "—"
                              }
                            </td>


                            <td className="action-center__mono">

                              {
                                item.savingsPct !==
                                  null &&
                                item.savingsPct !==
                                  undefined

                                  ? `${
                                      Number(
                                        item.savingsPct
                                      ).toFixed(
                                        2
                                      )
                                    }%`

                                  : "—"
                              }

                            </td>


                            <td className="action-center__recommended">

                              {
                                item.recommendedAction
                                  ? capitalize(
                                      item.recommendedAction
                                    )
                                  : "—"
                              }

                            </td>


                            {
                              isSuperAdmin &&
                              (

                                <td>

                                  <div className="action-center__actions">

                                    <button
                                      type="button"
                                      className="action-center__action action-center__action--delete"
                                      disabled={
                                        state.pending
                                      }
                                      onClick={() =>
                                        handleAction(
                                          item,
                                          "DELETE"
                                        )
                                      }
                                    >
                                      {
                                        state.pending &&
                                        state.currentAction ===
                                          "DELETE"
                                          ? "..."
                                          : "DEL"
                                      }
                                    </button>


                                    <button
                                      type="button"
                                      className="action-center__action action-center__action--compress"
                                      disabled={
                                        state.pending
                                      }
                                      onClick={() =>
                                        handleAction(
                                          item,
                                          "COMPRESS"
                                        )
                                      }
                                    >
                                      {
                                        state.pending &&
                                        state.currentAction ===
                                          "COMPRESS"
                                          ? "..."
                                          : "COM"
                                      }
                                    </button>

                                  </div>

                                </td>

                              )
                            }

                          </tr>


                          {
                            state.message &&
                            (

                              <tr className="action-center__message-row">

                                <td
                                  colSpan={
                                    isSuperAdmin
                                      ? 8
                                      : 7
                                  }
                                >

                                  <span
                                    className={
                                      `action-center__message action-center__message--${
                                        state.tone ||
                                        "success"
                                      }`
                                    }
                                  >
                                    {
                                      state.message
                                    }
                                  </span>

                                </td>

                              </tr>

                            )
                          }

                        </React.Fragment>

                      );
                    }
                  )
            }

          </tbody>

        </table>

      </div>

    </div>
  );
}


function capitalize(
  value
) {

  if (!value) {
    return "";
  }


  const text =
    String(
      value
    );


  return (
    text
      .charAt(0)
      .toUpperCase() +
    text
      .slice(1)
      .toLowerCase()
  );
}


function formatSize(
  value
) {

  const size =
    Number(
      value
    );


  if (
    !Number.isFinite(
      size
    )
  ) {
    return "0 GB";
  }


  if (
    size <
    0.01
  ) {
    return `${
      size.toFixed(
        4
      )
    } GB`;
  }


  return `${
    size.toFixed(
      2
    )
  } GB`;
}