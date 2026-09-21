const jwt = require("jsonwebtoken");

const ROLES = {
  VIEWER: "Viewer",
  SUPER_ADMIN: "Super-Admin",
};

/*
--------------------------------------
AUTHENTICATE JWT
--------------------------------------
*/

function authenticateUser(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return res.status(401).json({
      success: false,
      message: "Authentication token required.",
    });
  }

  const token = authHeader.split(" ")[1];

  try {
    const decoded = jwt.verify(
      token,
      process.env.JWT_SECRET
    );

    req.user = {
      id: decoded.id,
      username: decoded.username,
      role: decoded.role,
    };

    next();
  } catch (error) {
    return res.status(401).json({
      success: false,
      message: "Invalid or expired token.",
    });
  }
}

/*
--------------------------------------
SUPER ADMIN ONLY
--------------------------------------
*/

function requireSuperAdmin(req, res, next) {
  if (
    !req.user ||
    req.user.role !== ROLES.SUPER_ADMIN
  ) {
    return res.status(403).json({
      success: false,
      message:
        "Only Super-Admin can execute this action.",
    });
  }

  next();
}

module.exports = {
  ROLES,
  authenticateUser,
  requireSuperAdmin,
};