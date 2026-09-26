// Frontend/src/api.js

const API_BASE_URL =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://127.0.0.1:8000"
    : "http://localhost:8000";


// ============================================================
// API ERROR
// ============================================================

export class ApiError extends Error {

  constructor(
    message,
    status,
    body
  ) {

    super(
      message
    );

    this.name =
      "ApiError";

    this.status =
      status;

    this.body =
      body;

  }

}


// ============================================================
// TOKEN
// ============================================================

export function getToken() {

  return localStorage.getItem(
    "storagewise_token"
  );

}


// ============================================================
// COMMON JSON REQUEST
// ============================================================

async function apiRequest(
  endpoint,
  options = {}
) {

  const response =
    await fetch(
      `${API_BASE_URL}${endpoint}`,
      {
        cache:
          "no-store",

        ...options,

        headers: {
          "Content-Type":
            "application/json",

          ...(options.headers || {}),
        },
      }
    );


  let body =
    null;


  const contentType =
    response.headers.get(
      "content-type"
    );


  if (
    contentType &&
    contentType.includes(
      "application/json"
    )
  ) {

    body =
      await response.json();

  }

  else {

    body =
      await response.text();

  }


  if (
    !response.ok
  ) {

    throw new ApiError(
      body?.message ||
      body?.detail ||
      body?.governance?.reason ||
      "API request failed",

      response.status,

      body
    );

  }


  return body;
}


// ============================================================
// HELPERS
// ============================================================

function clamp(
  value,
  min = 0,
  max = 1
) {

  return Math.min(
    max,

    Math.max(
      min,
      Number(
        value
      ) || 0
    )
  );

}


function differenceInDays(
  startDate,
  endDate
) {

  if (
    !startDate ||
    !endDate
  ) {

    return 0;

  }


  const start =
    new Date(
      startDate
    );


  const end =
    new Date(
      endDate
    );


  if (
    Number.isNaN(
      start.getTime()
    ) ||
    Number.isNaN(
      end.getTime()
    )
  ) {

    return 0;

  }


  return Math.max(
    0,

    Math.ceil(
      (
        end.getTime() -
        start.getTime()
      ) /
      (
        1000 *
        60 *
        60 *
        24
      )
    )
  );

}


// ============================================================
// BACKEND HEALTH
// ============================================================

export async function getBackendHealth() {

  return apiRequest(
    "/health"
  );

}


// ============================================================
// UPLOAD FORMATS
// ============================================================

export const ALLOWED_UPLOAD_EXTENSIONS = [
  ".json",
  ".jsonl",
  ".csv",
  ".txt",
  ".yaml",
  ".yml",
];


export const UPLOAD_ACCEPT =
  ".json,.jsonl,.csv,.txt,.yaml,.yml";


// ============================================================
// FILE UPLOAD
// ============================================================

export async function uploadFiles(
  files
) {

  if (
    !files ||
    files.length ===
      0
  ) {

    throw new ApiError(
      "Select at least one file.",
      400,
      null
    );

  }


  const formData =
    new FormData();


  let validFileCount =
    0;


  for (
    const file
    of files
  ) {

    if (
      !file
    ) {

      continue;

    }


    const fileName =
      String(
        file.name ||
        ""
      );


    const dotIndex =
      fileName.lastIndexOf(
        "."
      );


    const extension =
      dotIndex >=
      0

        ? fileName
            .slice(
              dotIndex
            )
            .toLowerCase()

        : "";


    if (
      !ALLOWED_UPLOAD_EXTENSIONS.includes(
        extension
      )
    ) {

      throw new ApiError(
        `Unsupported file format: ${fileName}.`,
        400,
        null
      );

    }


    if (
      extension ===
        ".json" ||
      extension ===
        ".jsonl"
    ) {

      formData.append(
        "json_file",
        file
      );

    }

    else if (
      extension ===
      ".csv"
    ) {

      formData.append(
        "csv_file",
        file
      );

    }

    else if (
      extension ===
      ".txt"
    ) {

      formData.append(
        "txt_file",
        file
      );

    }

    else if (
      extension ===
        ".yaml" ||
      extension ===
        ".yml"
    ) {

      formData.append(
        "yaml_file",
        file
      );

    }


    validFileCount +=
      1;

  }


  if (
    validFileCount ===
    0
  ) {

    throw new ApiError(
      "No supported files selected.",
      400,
      null
    );

  }


  const response =
    await fetch(
      `${API_BASE_URL}/ingest`,
      {
        method:
          "POST",

        cache:
          "no-store",

        body:
          formData,
      }
    );


  let body =
    null;


  const contentType =
    response.headers.get(
      "content-type"
    );


  if (
    contentType &&
    contentType.includes(
      "application/json"
    )
  ) {

    body =
      await response.json();

  }

  else {

    body =
      await response.text();

  }


  if (
    !response.ok
  ) {

    throw new ApiError(
      body?.detail ||
      body?.message ||
      "File upload failed.",

      response.status,

      body
    );

  }


  return body;
}


// ============================================================
// EXECUTIVE HEALTH SCORE
// ============================================================

export async function getHealthScore() {

  // ----------------------------------------------------------
  // STORAGE
  // ----------------------------------------------------------

  const historyResponse =
    await apiRequest(
      "/storage-history"
    );


  const rawHistory =
    historyResponse.data ||
    [];


  if (
    rawHistory.length ===
    0
  ) {

    throw new ApiError(
      "Storage history is unavailable.",
      500,
      null
    );

  }


  const history =
    rawHistory.map(
      (row) => ({

        date:
          row.usage_date,

        usedGb:
          Number(
            row.total_used_gb
          ) || 0,

        capacityGb:
          Number(
            row.total_capacity_gb
          ) || 0,

      })
    );


  const latest =
    history[
      history.length -
      1
    ];


  const usedStorage =
    Number(
      latest.usedGb
    ) || 0;


  const totalStorage =
    Number(
      latest.capacityGb
    ) || 1000;


  // ----------------------------------------------------------
  // COMPRESSION
  // ----------------------------------------------------------

  const compression =
    await apiRequest(
      "/compression-insights"
    );


  const averageCompressionPercent =
    Number(
      compression
        .averageSavingsPercent
    ) || 0;


  const potentialSavingsGb =
    Number(
      compression
        .potentialSavingsGb
    ) || 0;


  const predictionCount =
    Number(
      compression
        .predictionCount
    ) || 0;


  // ----------------------------------------------------------
  // PROPHET
  // ----------------------------------------------------------

  const prophetResponse =
    await apiRequest(
      "/forecast-storage",
      {
        method:
          "POST",

        body:
          JSON.stringify({
            history:
              history.map(
                (row) => ({

                  date:
                    row.date,

                  usedGb:
                    row.usedGb,

                })
              ),
          }),
      }
    );


  const forecastData =
    prophetResponse.forecast ||
    {};


  const runwayToZeroDate =
    forecastData
      .runwayToZeroDate ||

    forecastData
      .runway_to_zero ||

    forecastData
      .runway_to_zero_date ||

    null;


  const daysToFull =
    runwayToZeroDate

      ? differenceInDays(
          latest.date,
          runwayToZeroDate
        )

      : 365;


  // ----------------------------------------------------------
  // HEALTH SCORE
  // ----------------------------------------------------------

  const result =
    await apiRequest(
      "/health-score",
      {
        method:
          "POST",

        body:
          JSON.stringify({
            usedStorage,
            totalStorage,
            averageCompressionPercent,
            daysToFull,
          }),
      }
    );


  const capacityValue =
    Number(
      result.components
        ?.capacity
    ) || 0;


  const efficiencyValue =
    Number(
      result.components
        ?.efficiency
    ) || 0;


  const stabilityValue =
    Number(
      result.components
        ?.stability
    ) || 0;


  // ----------------------------------------------------------
  // 30-DAY TREND
  // ----------------------------------------------------------

  const last30 =
    history.slice(
      -30
    );


  const trend =
    last30.map(
      (row) => {

        const historicalCapacity =
          row.capacityGb >
          0

            ? clamp(
                1 -
                (
                  row.usedGb /
                  row.capacityGb
                )
              )

            : 0;


        const historicalScore =
          clamp(
            (
              historicalCapacity *
              0.4
            ) +

            (
              efficiencyValue *
              0.3
            ) +

            (
              stabilityValue *
              0.3
            )
          );


        return {

          date:
            row.date,

          score:
            Number(
              historicalScore
                .toFixed(
                  4
                )
            ),

        };

      }
    );


  if (
    trend.length >
    0
  ) {

    trend[
      trend.length -
      1
    ].score =
      Number(
        result.score
      ) || 0;

  }


  let trendDirection =
    "stable";


  if (
    trend.length >=
    2
  ) {

    const first =
      Number(
        trend[0].score
      );


    const last =
      Number(
        trend[
          trend.length -
          1
        ].score
      );


    if (
      last -
      first >
      0.01
    ) {

      trendDirection =
        "improving";

    }

    else if (
      last -
      first <
      -0.01
    ) {

      trendDirection =
        "declining";

    }

  }


  return {

    grade:
      result.grade,

    score:
      Number(
        result.score
      ) || 0,


    capacity: {

      value:
        capacityValue,

      usedGb:
        usedStorage,

      totalGb:
        totalStorage,

      freeGb:
        Math.max(
          0,
          totalStorage -
          usedStorage
        ),

      freePercent:
        capacityValue *
        100,

    },


    efficiency: {

      value:
        efficiencyValue,

      savingsPercent:
        averageCompressionPercent,

      potentialSavingsGb,

      predictionCount,

    },


    stability: {

      value:
        stabilityValue,

      daysToFull,

      runwayToZeroDate,

    },


    trend,

    trendDirection,


    sources: {

      storage:
        historyResponse.source ||
        "database",

      compression:
        "Linear Regression",

      forecast:
        "Prophet",

    },

  };
}


// ============================================================
// STORAGE HISTORY
// ============================================================

export async function getStorageHistory() {

  const result =
    await apiRequest(
      "/storage-history"
    );


  return (
    result.data ||
    []
  ).map(
    (row) => ({

      date:
        row.usage_date,

      usedGb:
        Number(
          row.total_used_gb
        ),

      capacityGb:
        Number(
          row.total_capacity_gb
        ),

    })
  );

}


// ============================================================
// PROPHET FORECAST
// ============================================================

export async function getForecast() {

  const historyResponse =
    await apiRequest(
      "/storage-history"
    );


  const history =
    historyResponse.data ||
    [];


  const prophetResponse =
    await apiRequest(
      "/forecast-storage",
      {
        method:
          "POST",

        body:
          JSON.stringify({

            history:
              history.map(
                (row) => ({

                  date:
                    row.usage_date,

                  usedGb:
                    Number(
                      row.total_used_gb
                    ),

                })
              ),

          }),
      }
    );


  const forecastData =
    prophetResponse.forecast ||
    {};


  return {

    history:
      history.map(
        (row) => ({

          date:
            row.usage_date,

          usedGb:
            Number(
              row.total_used_gb
            ),

        })
      ),


    forecast: (
      forecastData.forecast ||
      forecastData.predictions ||
      []
    ).map((point) => {
      const val = Number(point.predictedGb ?? point.usedGb ?? point.yhat ?? 0);
      return {
        ...point,
        date: point.date || point.ds,
        usedGb: val,
        predictedGb: val,
      };
    }),


    capacityGb:
      Number(
        forecastData
          .capacityGb ||

        forecastData
          .capacity_gb ||

        history[
          history.length -
          1
        ]?.total_capacity_gb ||

        1000
      ),


    runwayToZeroDate:
      forecastData
        .runwayToZeroDate ||

      forecastData
        .runway_to_zero ||

      forecastData
        .runway_to_zero_date ||

      null,

  };

}


// ============================================================
// LINEAR REGRESSION — SINGLE PREDICTION
// ============================================================

export async function getCompressionPrediction({
  entropyScore,
  fileExtension,
  sizeGb,
}) {

  const result =
    await apiRequest(
      "/predict-compression",
      {
        method:
          "POST",

        body:
          JSON.stringify({

            entropy_score:
              Number(
                entropyScore
              ),

            file_extension:
              fileExtension,

            size_gb:
              Number(
                sizeGb
              ),

          }),
      }
    );


  return result.prediction;

}


// ============================================================
// STORED COMPRESSION INSIGHTS
// ============================================================

export async function getCompressionInsights() {

  return apiRequest(
    "/compression-insights"
  );

}


// ============================================================
// RUN LINEAR REGRESSION BATCH
// ============================================================

export async function runCompressionAI(
  limit = 100,
  sourceType = null
) {

  const body = {

    limit:
      Number(
        limit
      ),

  };


  if (
    sourceType
  ) {

    body.source_type =
      String(
        sourceType
      ).toLowerCase();

  }


  return apiRequest(
    "/run-compression-ai",
    {
      method:
        "POST",

      body:
        JSON.stringify(
          body
        ),
    }
  );

}


// ============================================================
// ACTION CENTER
// ============================================================

export async function getActionItems(options = {}) {
  const {
    sourceType = "json",
    page = 1,
    limit = 50,
  } = typeof options === "string" ? { sourceType: options } : options;

  // timestamp defeats any browser/proxy caching
  const cacheBuster = Date.now();
  const query = new URLSearchParams({
    source_type: sourceType,
    page: String(page),
    limit: String(limit),
    _: String(cacheBuster),
  });

  const result = await apiRequest(`/assets?${query.toString()}`);
  const assets = result.data || [];

  const items = assets.map(
    (asset) => {

      let tags =
        [];


      try {

        if (
          Array.isArray(
            asset.tags
          )
        ) {

          tags =
            asset.tags;

        }

        else if (
          typeof asset.tags ===
          "string"
        ) {

          tags =
            JSON.parse(
              asset.tags
            );

        }

      }

      catch {

        tags =
          [];

      }


      const hasPrediction =
        asset.savings_percent !==
          null &&

        asset.savings_percent !==
          undefined;


      return {

        fileId:
          asset.asset_id,

        fileName:
          asset.file_name ||
          asset.asset_id,

        fileExtension:
          asset.file_extension ||
          "",

        sourceType:
          asset.source_type ||
          "unknown",

        sizeGb:
          Number(
            asset.size_gb
          ) || 0,

        department:
          asset.owner_dept ||
          "unknown",

        policyId:
          asset.policy_id ||
          null,

        checksum:
          asset.checksum ||
          null,

        entropyScore:
          asset.entropy_score !==
            null &&

          asset.entropy_score !==
            undefined

            ? Number(
                asset.entropy_score
              )

            : null,

        isDuplicate:
          Boolean(
            Number(
              asset.is_duplicate
            )
          ),

        tags,

        createdTs:
          asset.created_ts ||
          null,

        modifiedTs:
          asset.modified_ts ||
          null,

        ingestedAt:
          asset.created_at ||
          null,


        score:
          hasPrediction

            ? Number(
                asset.priority_score
              ) || 0

            : null,


        savingsPct:
          hasPrediction

            ? Number(
                asset.savings_percent
              )

            : null,


        savingsGb:
          hasPrediction

            ? Number(
                asset.savings_gb
              ) || 0

            : null,


        riskScore:
          Number(
            asset.risk_score
          ) || 0,


        recommendedAction:
          hasPrediction

            ? (
                Number(
                  asset.savings_percent
                ) >=
                50

                  ? "compress"

                  : "delete"
              )

            : null,

      };

    }
  );

  return {
    items,
    count: result.count ?? items.length,
    total: result.total ?? items.length,
    totalPages: result.total_pages ?? Math.max(1, Math.ceil((result.total || items.length) / limit)),
    page: result.page ?? page,
    limit: result.limit ?? limit,
    formatCounts: result.format_counts || { json: 0, csv: 0, txt: 0, yaml: 0 },
  };
}


// ============================================================
// EXECUTE DELETE / COMPRESS
// ============================================================

export async function executeAction({
  fileId,
  action,
}) {

  const token =
    getToken();


  if (
    !token
  ) {

    throw new ApiError(
      "Please login before executing an action.",
      401,
      null
    );

  }


  return apiRequest(
    `/actions/${encodeURIComponent(
      fileId
    )}`,
    {
      method:
        "POST",

      headers: {

        Authorization:
          `Bearer ${token}`,

      },

      body:
        JSON.stringify({

          action:
            String(
              action
            )
              .trim()
              .toUpperCase(),

        }),
    }
  );

}


// ============================================================
// PRIORITY SCORE
// ============================================================

export async function getPriorityScore({
  risk,
  savings,
}) {

  return apiRequest(
    "/priority-score",
    {
      method:
        "POST",

      body:
        JSON.stringify({

          risk:
            Number(
              risk
            ),

          savings:
            Number(
              savings
            ),

        }),
    }
  );

}


// ============================================================
// AUDIT LOG
// ============================================================

export async function getAuditLog() {

  const response =
    await fetch(
      `${API_BASE_URL}/audit?_=${Date.now()}`,
      {
        cache:
          "no-store",
      }
    );


  if (
    !response.ok
  ) {

    throw new ApiError(
      "Unable to load audit log.",
      response.status,
      null
    );

  }


  const csv =
    await response.text();


  if (
    !csv.trim()
  ) {

    return [];

  }


  const lines =
    csv
      .trim()
      .split(
        /\r?\n/
      );


  if (
    lines.length <=
    1
  ) {

    return [];

  }


  return lines
    .slice(
      1
    )
    .map(
      (line) => {

        const values =
          line
            .match(
              /(".*?"|[^",]+)(?=\s*,|\s*$)/g
            )
            ?.map(
              (value) =>
                value
                  .replace(
                    /^"|"$/g,
                    ""
                  )
                  .replace(
                    /""/g,
                    '"'
                  )
            );


        if (
          !values
        ) {

          return null;

        }


        return {

          timestamp:
            values[0],

          user:
            values[1],

          role:
            values[2],

          action:
            values[3],

          file:
            values[4],

          policyId:
            values[5] ||
            null,

          outcome:
            values[6],

        };

      }
    )
    .filter(
      Boolean
    );

}

// ============================================================
// ROLES
// ============================================================

export const ROLES = {
  VIEWER: "Viewer",
  SUPER_ADMIN: "Super-Admin",
};

export const ROLE_LABELS = {
  [ROLES.VIEWER]: "Viewer",
  [ROLES.SUPER_ADMIN]: "Super-Admin",
};

// ============================================================
// AUTHENTICATION
// ============================================================

/**
 * Sign up a new user. Returns:
 *   { status: "success", user, token }
 *   { status: "exists" }
 *   { status: "error", message }
 */
export async function signup({ username, password, role }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, role }),
    });

    const data = await response.json();

    if (response.status === 409) {
      return { status: "exists" };
    }

    if (!response.ok) {
      return {
        status: "error",
        message: data.message || data.detail || "Unable to create account.",
      };
    }

    saveSession(data.user, data.token);
    return { status: "success", user: data.user, token: data.token };
  } catch (error) {
    console.error("Signup error:", error);
    return { status: "error", message: "Unable to connect to backend." };
  }
}

/**
 * Log in an existing user. Returns:
 *   { status: "success", user, token }
 *   { status: "not_found" }
 *   { status: "error", message }
 */
export async function login({ username, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (response.status === 404) {
      return { status: "not_found" };
    }

    if (response.status === 401) {
      return { status: "error", message: "Incorrect password." };
    }

    if (!response.ok) {
      return {
        status: "error",
        message: data.message || data.detail || "Login failed.",
      };
    }

    saveSession(data.user, data.token);
    return { status: "success", user: data.user, token: data.token };
  } catch (error) {
    console.error("Login error:", error);
    return { status: "error", message: "Unable to connect to backend." };
  }
}

// ============================================================
// SESSION
// ============================================================

function saveSession(user, token) {
  if (token) {
    localStorage.setItem("storagewise_token", token);
  }
  if (user) {
    localStorage.setItem("storagewise_user", JSON.stringify(user));
  }
}

export function getCurrentUser() {
  const storedUser = localStorage.getItem("storagewise_user");
  if (!storedUser) return null;
  try {
    return JSON.parse(storedUser);
  } catch (error) {
    console.error("Invalid stored user session:", error);
    localStorage.removeItem("storagewise_user");
    return null;
  }
}

export function getSession() {
  const user = getCurrentUser();
  const token = getToken();
  if (!user || !token) return null;
  return user;
}

export function clearSession() {
  localStorage.removeItem("storagewise_token");
  localStorage.removeItem("storagewise_user");
}

export function logout() {
  clearSession();
}