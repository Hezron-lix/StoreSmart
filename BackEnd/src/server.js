const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");

dotenv.config();

const routes = require("./routes");

const {
  testDatabaseConnection,
} = require("./database");

const {
  loadPolicies,
} = require("./governance");

const {
  initializeAuditLog,
} = require("./audit");

const app = express();

const PORT = process.env.PORT || 5000;


/*
--------------------------------------
MIDDLEWARE
--------------------------------------
*/

app.use(cors());

/*
Allow larger JSON payloads because
FastAPI may send thousands of
canonical asset records at once.
*/

app.use(
  express.json({
    limit: "25mb",
  })
);


/*
IMPORTANT:

Do NOT use:

app.use(attachUser);

Authentication is now handled only on
protected routes using authenticateUser.
*/


/*
--------------------------------------
ROOT ROUTE
--------------------------------------
*/

app.get("/", (req, res) => {
  res.json({
    name: "StorageWise AI",
    service: "Backend API",
    status: "running",
  });
});


/*
--------------------------------------
API ROUTES
--------------------------------------
*/

app.use("/api", routes);


/*
--------------------------------------
GLOBAL ERROR HANDLER
--------------------------------------
*/

app.use((err, req, res, next) => {
  console.error(
    "Server error:",
    err
  );

  /*
  Handle request body that is too large.
  */

  if (err.type === "entity.too.large") {
    return res.status(413).json({
      success: false,
      message:
        "Request payload is too large.",
    });
  }

  res.status(500).json({
    success: false,
    message: "Internal server error",
  });
});


/*
--------------------------------------
START SERVER
--------------------------------------
*/

async function startServer() {
  try {
    await testDatabaseConnection();

    loadPolicies();

    initializeAuditLog();

    app.listen(
      PORT,
      () => {
        console.log(
          `🚀 StorageWise backend running on http://localhost:${PORT}`
        );
      }
    );

  } catch (error) {
    console.error(
      "Failed to start backend:",
      error
    );

    process.exit(1);
  }
}

startServer();