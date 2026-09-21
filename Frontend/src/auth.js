const API_BASE_URL = "http://localhost:8000/api";

export const ROLES = {
  VIEWER: "Viewer",
  SUPER_ADMIN: "Super-Admin",
};

export const ROLE_LABELS = {
  [ROLES.VIEWER]: "Viewer",
  [ROLES.SUPER_ADMIN]: "Super-Admin",
};

// ------------------------------------------------------------
// SIGN UP
// ------------------------------------------------------------

export async function signup({ username, password, role }) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
        role,
      }),
    });

    const data = await response.json();

    if (response.status === 409) {
      return {
        status: "exists",
      };
    }

    if (!response.ok) {
      return {
        status: "error",
        message: data.message || data.detail || "Unable to create account.",
      };
    }

    saveSession(data.user, data.token);

    return {
      status: "success",
      user: data.user,
      token: data.token,
    };
  } catch (error) {
    console.error("Signup error:", error);

    return {
      status: "error",
      message: "Unable to connect to backend.",
    };
  }
}

// ------------------------------------------------------------
// LOGIN
// ------------------------------------------------------------

export async function login({ username, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    });

    const data = await response.json();

    if (response.status === 404) {
      return {
        status: "not_found",
      };
    }

    if (response.status === 401) {
      return {
        status: "error",
        message: "Incorrect password.",
      };
    }

    if (!response.ok) {
      return {
        status: "error",
        message: data.message || data.detail || "Login failed.",
      };
    }

    saveSession(data.user, data.token);

    return {
      status: "success",
      user: data.user,
      token: data.token,
    };
  } catch (error) {
    console.error("Login error:", error);

    return {
      status: "error",
      message: "Unable to connect to backend.",
    };
  }
}

// ------------------------------------------------------------
// SESSION STORAGE
// ------------------------------------------------------------

function saveSession(user, token) {
  if (token) {
    localStorage.setItem(
      "storagewise_token",
      token
    );
  }

  if (user) {
    localStorage.setItem(
      "storagewise_user",
      JSON.stringify(user)
    );
  }
}

// ------------------------------------------------------------
// GET CURRENT USER
// ------------------------------------------------------------

export function getCurrentUser() {
  const storedUser =
    localStorage.getItem("storagewise_user");

  if (!storedUser) {
    return null;
  }

  try {
    return JSON.parse(storedUser);
  } catch (error) {
    console.error(
      "Invalid stored user session:",
      error
    );

    localStorage.removeItem(
      "storagewise_user"
    );

    return null;
  }
}

// ------------------------------------------------------------
// APP.JSX SESSION HELPER
// ------------------------------------------------------------

export function getSession() {
  const user = getCurrentUser();
  const token = getToken();

  if (!user || !token) {
    return null;
  }

  return user;
}

// ------------------------------------------------------------
// GET JWT TOKEN
// ------------------------------------------------------------

export function getToken() {
  return localStorage.getItem(
    "storagewise_token"
  );
}

// ------------------------------------------------------------
// CLEAR SESSION
// ------------------------------------------------------------

export function clearSession() {
  localStorage.removeItem(
    "storagewise_token"
  );

  localStorage.removeItem(
    "storagewise_user"
  );
}

// ------------------------------------------------------------
// LOGOUT
// ------------------------------------------------------------

export function logout() {
  clearSession();
}