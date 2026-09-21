const fs = require("fs");
const path = require("path");

const logDirectory = path.join(
  __dirname,
  "../../logs"
);

const auditFile = path.join(
  logDirectory,
  "audit.csv"
);

function initializeAuditLog() {
  if (!fs.existsSync(logDirectory)) {
    fs.mkdirSync(logDirectory, {
      recursive: true,
    });
  }

  if (!fs.existsSync(auditFile)) {
    const header =
      "timestamp,user,role,action,file,policy_id,outcome\n";

    fs.writeFileSync(auditFile, header);
  }
}

function cleanCsvValue(value) {
  if (value === null || value === undefined) {
    return "";
  }

  return `"${String(value).replace(/"/g, '""')}"`;
}

function writeAudit({
  user,
  role,
  action,
  file,
  policyId,
  outcome,
}) {
  initializeAuditLog();

  const row = [
    new Date().toISOString(),
    user,
    role,
    action,
    file,
    policyId || "",
    outcome,
  ]
    .map(cleanCsvValue)
    .join(",");

  fs.appendFileSync(
    auditFile,
    `${row}\n`,
    "utf8"
  );
}

function getAuditLogs() {
  initializeAuditLog();

  return fs.readFileSync(
    auditFile,
    "utf8"
  );
}

module.exports = {
  initializeAuditLog,
  writeAudit,
  getAuditLogs,
};