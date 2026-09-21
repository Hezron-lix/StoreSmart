const express = require("express");
const axios = require("axios");

const { pool } = require("./database");

const {
  requireSuperAdmin,
} = require("./rbac");

const {
  validateAction,
} = require("./governance");

const {
  calculateHealthScore,
  calculatePriorityScore,
} = require("./health");

const {
  writeAudit,
  getAuditLogs,
} = require("./audit");

const {
  signup,
  login,
} = require("./auth");

const router = express.Router();

/*
==================================================
AUTHENTICATION
==================================================
*/

// Create new user
router.post("/auth/signup", signup);

// Login existing user
router.post("/auth/login", login);


/*
==================================================
HEALTH CHECK
==================================================
*/

router.get("/health", (req, res) => {
  res.json({
    success: true,
    service: "StorageWise AI Backend",
    status: "running",
  });
});


/*
==================================================
GET ALL ASSETS
==================================================

Assets are joined with prediction data so the
frontend Action Center can receive:

- savings_percent
- savings_gb
- priority_score
*/

router.get("/assets", async (req, res) => {
  try {

    const [rows] = await pool.query(`
      SELECT
        a.*,
        p.savings_percent,
        p.savings_gb,
        p.priority_score

      FROM assets a

      LEFT JOIN predictions p
        ON a.asset_id = p.asset_id

      ORDER BY a.id DESC
    `);

    res.json({
      success: true,
      count: rows.length,
      data: rows,
    });

  } catch (error) {

    console.error(
      "Assets error:",
      error.message
    );

    res.status(500).json({
      success: false,
      message: "Unable to fetch assets.",
    });
  }
});


/*
==================================================
IMPORT INGESTED ASSETS
==================================================

Receives canonical records from the Python
FastAPI ingestion service and stores them in
the existing MySQL `assets` table.

The existing database schema is preserved.
*/

router.post(
  "/assets/import",
  async (req, res) => {
    let connection;

    try {
      const { records } = req.body;

      if (!Array.isArray(records) || records.length === 0) {
        return res.status(400).json({
          success: false,
          message: "records must be a non-empty array.",
        });
      }

      const toMySQLDateTime = (value) => {
        if (!value) {
          return null;
        }

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
          return null;
        }

        return date
          .toISOString()
          .slice(0, 19)
          .replace("T", " ");
      };

      const validSourceTypes = new Set([
        "json",
        "txt",
        "csv",
        "yaml",
      ]);

      connection = await pool.getConnection();
      await connection.beginTransaction();

      const BATCH_SIZE = 500;

      let imported = 0;
      let skipped = 0;

      for (
        let start = 0;
        start < records.length;
        start += BATCH_SIZE
      ) {
        const batch = records.slice(
          start,
          start + BATCH_SIZE
        );

        const values = [];

        for (const record of batch) {
          if (
            !record ||
            !record.asset_id ||
            !validSourceTypes.has(record.source_type)
          ) {
            skipped += 1;
            continue;
          }

          const sizeGb = Number(
            record.size_gb ?? 0
          );

          values.push([
            String(record.asset_id),

            record.source_type,

            record.file_name ?? null,

            record.file_extension ?? null,

            Number.isFinite(sizeGb)
              ? sizeGb
              : 0,

            toMySQLDateTime(
              record.created_ts
            ),

            toMySQLDateTime(
              record.modified_ts
            ),

            record.owner_dept ??
              "unknown",

            JSON.stringify(
              record.tags ?? []
            ),

            record.checksum ??
              record.checksum_sha256 ??
              null,

            record.policy_id ??
              null,

            record.entropy_score ??
              null,

            record.is_duplicate
              ? 1
              : 0,
          ]);
        }

        if (!values.length) {
          continue;
        }

        const placeholders = values
          .map(
            () =>
              "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
          )
          .join(", ");

        await connection.query(
          `
          INSERT INTO assets
          (
            asset_id,
            source_type,
            file_name,
            file_extension,
            size_gb,
            created_ts,
            modified_ts,
            owner_dept,
            tags,
            checksum,
            policy_id,
            entropy_score,
            is_duplicate
          )

          VALUES
          ${placeholders}

          ON DUPLICATE KEY UPDATE
            source_type =
              VALUES(source_type),

            file_name =
              VALUES(file_name),

            file_extension =
              VALUES(file_extension),

            size_gb =
              VALUES(size_gb),

            created_ts =
              VALUES(created_ts),

            modified_ts =
              VALUES(modified_ts),

            owner_dept =
              VALUES(owner_dept),

            tags =
              VALUES(tags),

            checksum =
              VALUES(checksum),

            policy_id =
              VALUES(policy_id),

            entropy_score =
              VALUES(entropy_score),

            is_duplicate =
              VALUES(is_duplicate)
          `,
          values.flat()
        );

        imported += values.length;
      }

      await connection.commit();

      return res.json({
        success: true,

        message:
          "Canonical assets imported successfully.",

        received:
          records.length,

        imported,

        skipped,
      });

    } catch (error) {

      if (connection) {
        try {
          await connection.rollback();
        } catch {
          // Ignore rollback failure.
        }
      }

      console.error(
        "Asset import error:",
        error
      );

      return res.status(500).json({
        success: false,

        message:
          "Unable to import canonical assets.",

        error:
          error.message,
      });

    } finally {

      if (connection) {
        connection.release();
      }
    }
  }
);


/*
==================================================
GET STORAGE HISTORY
==================================================
*/

router.get(
  "/storage-history",
  async (req, res) => {

    try {

      const [rows] = await pool.query(`
        SELECT
          id,
          usage_date,
          total_used_gb,
          total_capacity_gb

        FROM storage_history

        ORDER BY usage_date ASC
      `);

      res.json({
        success: true,
        data: rows,
      });

    } catch (error) {

      console.error(
        "Storage history error:",
        error.message
      );

      res.status(500).json({
        success: false,
        message:
          "Unable to fetch storage history.",
      });
    }
  }
);


/*
==================================================
LINEAR REGRESSION
==================================================
*/

router.post(
  "/predict-compression",
  async (req, res) => {

    try {

      const {
        entropy_score,
        file_extension,
        size_gb,
      } = req.body;

      if (
        entropy_score === undefined ||
        !file_extension ||
        size_gb === undefined
      ) {

        return res.status(400).json({
          success: false,
          message:
            "entropy_score, file_extension and size_gb are required.",
        });
      }

      const response = await axios.post(
        `${process.env.LINEAR_REGRESSION_URL}/predict`,
        {
          entropy_score,
          file_extension,
          size_gb,
        }
      );

      res.json({
        success: true,
        prediction: response.data,
      });

    } catch (error) {

      console.error(
        "Linear Regression error:",
        error.message
      );

      res.status(503).json({
        success: false,
        message:
          "Linear Regression service unavailable.",
      });
    }
  }
);


/*
==================================================
PROPHET FORECAST
==================================================
*/

router.post(
  "/forecast-storage",
  async (req, res) => {

    try {

      const response = await axios.post(
        `${process.env.PROPHET_URL}/forecast`,
        req.body
      );

      res.json({
        success: true,
        forecast: response.data,
      });

    } catch (error) {

      console.error(
        "Prophet error:",
        error.message
      );

      res.status(503).json({
        success: false,
        message:
          "Prophet service unavailable.",
      });
    }
  }
);


/*
==================================================
HEALTH SCORE
==================================================
*/

router.post(
  "/health-score",
  (req, res) => {

    try {

      const {
        usedStorage,
        totalStorage,
        averageCompressionPercent,
        daysToFull,
      } = req.body;

      if (
        usedStorage === undefined ||
        totalStorage === undefined ||
        averageCompressionPercent === undefined ||
        daysToFull === undefined
      ) {

        return res.status(400).json({
          success: false,
          message:
            "usedStorage, totalStorage, averageCompressionPercent and daysToFull are required.",
        });
      }

      const result =
        calculateHealthScore({
          usedStorage: Number(usedStorage),
          totalStorage: Number(totalStorage),
          averageCompressionPercent:
            Number(averageCompressionPercent),
          daysToFull: Number(daysToFull),
        });

      res.json({
        success: true,
        ...result,
      });

    } catch (error) {

      res.status(400).json({
        success: false,
        message: error.message,
      });
    }
  }
);


/*
==================================================
PRIORITY SCORE
==================================================
*/

router.post(
  "/priority-score",
  (req, res) => {

    const {
      risk,
      savings,
    } = req.body;

    if (
      risk === undefined ||
      savings === undefined
    ) {

      return res.status(400).json({
        success: false,
        message:
          "risk and savings are required.",
      });
    }

    const priorityScore =
      calculatePriorityScore(
        Number(risk),
        Number(savings)
      );

    res.json({
      success: true,
      risk: Number(risk),
      savings: Number(savings),
      priorityScore,
    });
  }
);


/*
==================================================
ACTION CENTER
==================================================
*/

router.post(
  "/actions/:assetId",
  requireSuperAdmin,
  async (req, res) => {

    try {

      const {
        assetId,
      } = req.params;

      if (!req.body.action) {

        return res.status(400).json({
          success: false,
          message:
            "Action is required.",
        });
      }

      const action =
        String(
          req.body.action
        ).toUpperCase();

      if (
        ![
          "DELETE",
          "COMPRESS",
        ].includes(action)
      ) {

        return res.status(400).json({
          success: false,
          message:
            "Action must be DELETE or COMPRESS.",
        });
      }

      /*
      --------------------------------------------
      FIND ASSET
      --------------------------------------------
      */

      const [rows] =
        await pool.query(
          `
          SELECT *
          FROM assets
          WHERE asset_id = ?
          `,
          [assetId]
        );

      if (!rows.length) {

        return res.status(404).json({
          success: false,
          message:
            "Asset not found.",
        });
      }

      const asset =
        rows[0];


      /*
      --------------------------------------------
      PARSE TAGS
      --------------------------------------------
      */

      try {

        if (
          typeof asset.tags ===
          "string"
        ) {

          asset.tags =
            JSON.parse(
              asset.tags
            );
        }

      } catch {

        asset.tags = [];
      }


      /*
      --------------------------------------------
      GOVERNANCE CHECK
      --------------------------------------------
      */

      const governance =
        validateAction(
          asset,
          action
        );


      /*
      --------------------------------------------
      BLOCKED ACTION
      --------------------------------------------
      */

      if (
        !governance.allowed
      ) {

        writeAudit({
          user:
            req.user.name,

          role:
            req.user.role,

          action,

          file:
            asset.file_name ||
            asset.asset_id,

          policyId:
            governance.policyId,

          outcome:
            "blocked",
        });


        await pool.query(
          `
          INSERT INTO actions
          (
            asset_id,
            user_name,
            role,
            action_type,
            policy_id,
            outcome,
            reason
          )

          VALUES
          (?, ?, ?, ?, ?, ?, ?)
          `,
          [
            asset.asset_id,

            req.user.name,

            req.user.role,

            action,

            governance.policyId ||
              null,

            "blocked",

            governance.reason,
          ]
        );


        return res
          .status(403)
          .json({
            success: false,

            decision:
              "BLOCKED",

            governance,
          });
      }


      /*
      --------------------------------------------
      ALLOWED ACTION
      --------------------------------------------

      Hackathon simulation:

      We are NOT actually deleting
      or compressing physical files.

      We simulate the successful action.
      */

      await pool.query(
        `
        INSERT INTO actions
        (
          asset_id,
          user_name,
          role,
          action_type,
          policy_id,
          outcome,
          reason
        )

        VALUES
        (?, ?, ?, ?, ?, ?, ?)
        `,
        [
          asset.asset_id,

          req.user.name,

          req.user.role,

          action,

          asset.policy_id ||
            null,

          "success",

          "Governance checks passed",
        ]
      );


      writeAudit({
        user:
          req.user.name,

        role:
          req.user.role,

        action,

        file:
          asset.file_name ||
          asset.asset_id,

        policyId:
          asset.policy_id,

        outcome:
          "success",
      });


      return res.json({
        success: true,

        decision:
          "ALLOWED",

        action,

        assetId,

        message:
          `${action} simulated successfully.`,
      });

    } catch (error) {

      console.error(
        "Action error:",
        error
      );

      res.status(500).json({
        success: false,
        message:
          "Unable to execute action.",
      });
    }
  }
);


/*
==================================================
AUDIT LOG
==================================================
*/

router.get(
  "/audit",
  (req, res) => {

    try {

      const logs =
        getAuditLogs();

      res
        .type("text/csv")
        .send(logs);

    } catch (error) {

      console.error(
        "Audit error:",
        error.message
      );

      res.status(500).json({
        success: false,
        message:
          "Unable to retrieve audit logs.",
      });
    }
  }
);


module.exports = router;