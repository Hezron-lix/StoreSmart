const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const { pool } = require("./database");

async function signup(req, res) {
  try {
    const { username, password, role } = req.body;

    if (!username || !password || !role) {
      return res.status(400).json({
        message: "Username, password and role are required",
      });
    }

    const [existing] = await pool.query(
      "SELECT id FROM users WHERE username = ?",
      [username]
    );

    if (existing.length > 0) {
      return res.status(409).json({
        message: "User already exists",
      });
    }

    const passwordHash = await bcrypt.hash(password, 10);

    const [result] = await pool.query(
      `INSERT INTO users (username, password_hash, role)
       VALUES (?, ?, ?)`,
      [username, passwordHash, role]
    );

    const user = {
      id: result.insertId,
      username,
      role,
    };

    const token = jwt.sign(
      user,
      process.env.JWT_SECRET,
      { expiresIn: "8h" }
    );

    return res.status(201).json({
      message: "Account created",
      user,
      token,
    });
  } catch (error) {
    console.error(error);

    return res.status(500).json({
      message: "Signup failed",
    });
  }
}

async function login(req, res) {
  try {
    const { username, password } = req.body;

    const [rows] = await pool.query(
      "SELECT * FROM users WHERE username = ?",
      [username]
    );

    if (rows.length === 0) {
      return res.status(404).json({
        message: "User not found",
      });
    }

    const userRecord = rows[0];

    const validPassword = await bcrypt.compare(
      password,
      userRecord.password_hash
    );

    if (!validPassword) {
      return res.status(401).json({
        message: "Invalid password",
      });
    }

    const user = {
      id: userRecord.id,
      username: userRecord.username,
      role: userRecord.role,
    };

    const token = jwt.sign(
      user,
      process.env.JWT_SECRET,
      { expiresIn: "8h" }
    );

    return res.json({
      message: "Login successful",
      user,
      token,
    });
  } catch (error) {
    console.error(error);

    return res.status(500).json({
      message: "Login failed",
    });
  }
}

module.exports = {
  signup,
  login,
};