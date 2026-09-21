const path = require("path");
const XLSX = require("xlsx");

const policyFile = path.join(
  __dirname,
  "../../data/Retention_Policy_Matrix.xlsx"
);

let policies = [];

function loadPolicies() {
  try {
    const workbook = XLSX.readFile(policyFile);

    const firstSheet =
      workbook.Sheets[workbook.SheetNames[0]];

    policies = XLSX.utils.sheet_to_json(firstSheet);

    console.log(
      `✅ ${policies.length} retention policies loaded`
    );
  } catch (error) {
    console.error(
      "⚠️ Could not load retention policies:",
      error.message
    );

    policies = [];
  }
}

function findPolicy(policyId) {
  if (!policyId) return null;

  return policies.find((policy) => {
    const id =
      policy["Policy ID"] ||
      policy["policy_id"] ||
      policy["Policy_ID"];

    return id === policyId;
  });
}

function calculateFileAgeYears(createdTs) {
  if (!createdTs) return 0;

  const created = new Date(createdTs);
  const now = new Date();

  return (
    (now - created) /
    (1000 * 60 * 60 * 24 * 365)
  );
}

/*
 Rule 1
 Retention:
 Block DELETE when file has not reached retention period.
*/
function checkRetention(asset, action) {
  if (action !== "DELETE") {
    return { allowed: true };
  }

  const policy = findPolicy(asset.policy_id);

  if (!policy) {
    return { allowed: true };
  }

  const retentionYears = Number(
    policy["Retention period"] ||
      policy["Retention Years"] ||
      policy["retention_years"] ||
      0
  );

  const ageYears = calculateFileAgeYears(
    asset.created_ts
  );

  if (retentionYears && ageYears < retentionYears) {
    return {
      allowed: false,
      policyId: asset.policy_id,
      rule: "RETENTION",
      reason:
        `File is ${ageYears.toFixed(1)} years old. ` +
        `Retention requires ${retentionYears} years.`,
    };
  }

  return { allowed: true };
}

/*
 Rule 2
 Priority:
 Legal data cannot be compressed.
*/
function checkPriority(asset, action) {
  if (action !== "COMPRESS") {
    return { allowed: true };
  }

  const tags = Array.isArray(asset.tags)
    ? asset.tags
    : [];

  const isLegal =
    tags
      .map((tag) => String(tag).toLowerCase())
      .includes("legal") ||
    String(asset.policy_id || "")
      .toUpperCase()
      .includes("LGL");

  if (isLegal) {
    return {
      allowed: false,
      policyId: asset.policy_id || "LEGAL-POLICY",
      rule: "PRIORITY",
      reason:
        "Legal files are protected from compression.",
    };
  }

  return { allowed: true };
}

/*
 Rule 3
 Conflict Resolution:
 Governance always overrides the AI recommendation.
*/
function checkConflict(asset, action) {
  if (action === "DELETE") {
    const retentionResult =
      checkRetention(asset, action);

    if (!retentionResult.allowed) {
      return {
        ...retentionResult,
        rule: "AI_POLICY_CONFLICT",
        reason:
          "AI recommendation overridden by retention policy. " +
          retentionResult.reason,
      };
    }
  }

  return { allowed: true };
}

function validateAction(asset, action) {
  const checks = [
    checkRetention(asset, action),
    checkPriority(asset, action),
    checkConflict(asset, action),
  ];

  const blocked = checks.find(
    (result) => !result.allowed
  );

  if (blocked) {
    return {
      allowed: false,
      ...blocked,
    };
  }

  return {
    allowed: true,
    reason: "All governance checks passed.",
  };
}

module.exports = {
  loadPolicies,
  validateAction,
};