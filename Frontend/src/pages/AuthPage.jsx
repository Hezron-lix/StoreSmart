import React, { useEffect, useState } from "react";
import {
  ROLES,
  ROLE_LABELS,
  login,
  signup,
} from "../auth";

import "./AuthPage.css";

const POPUP_MS = 1800;

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("login");

  const [form, setForm] = useState({
    username: "",
    password: "",
    confirm: "",
    role: ROLES.VIEWER,
  });

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [popup, setPopup] = useState(null);

  const isLogin = mode === "login";

  const update = (field) => (e) => {
    setForm((current) => ({
      ...current,
      [field]: e.target.value,
    }));
  };

  function switchMode(next, message = "") {
    setMode(next);
    setError("");
    setNotice(message);

    setForm((current) => ({
      ...current,
      password: "",
      confirm: "",
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();

    setError("");
    setNotice("");

    const username = form.username.trim();

    if (!username || !form.password) {
      setError("Enter a username and password.");
      return;
    }

    setBusy(true);

    try {
      // LOGIN
      if (isLogin) {
        const result = await login({
          username,
          password: form.password,
        });

        if (result.status === "not_found") {
          switchMode(
            "signup",
            `No account found for "${username}". Create one to continue.`
          );
          return;
        }

        if (result.status === "error") {
          setError(result.message);
          return;
        }

        setPopup({
          user: result.user,
          title: "Login successful",
        });

        return;
      }

      // SIGNUP VALIDATION
      if (form.password.length < 6) {
        setError(
          "Password must be at least 6 characters."
        );
        return;
      }

      if (form.password !== form.confirm) {
        setError("Passwords don't match.");
        return;
      }

      // SIGNUP
      const result = await signup({
        username,
        password: form.password,
        role: form.role,
      });

      if (result.status === "exists") {
        switchMode(
          "login",
          `"${username}" already has an account. Sign in instead.`
        );
        return;
      }

      if (result.status === "error") {
        setError(result.message);
        return;
      }

      setPopup({
        user: result.user,
        title: "Account created",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <form
        className="auth__card"
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="auth__brand">
          <span className="auth__title">
            StorageWise AI
          </span>

          <span className="auth__subtitle">
            Data Governance Console
          </span>
        </div>

        <div className="auth__heading">
          {isLogin ? "Sign in" : "Create account"}
        </div>

        {notice && (
          <p className="auth__notice">
            {notice}
          </p>
        )}

        {error && (
          <p
            className="auth__error"
            role="alert"
          >
            {error}
          </p>
        )}

        <label className="auth__field">
          <span>Username</span>

          <input
            type="text"
            value={form.username}
            onChange={update("username")}
            autoComplete="username"
            autoFocus
          />
        </label>

        <label className="auth__field">
          <span>Password</span>

          <input
            type="password"
            value={form.password}
            onChange={update("password")}
            autoComplete={
              isLogin
                ? "current-password"
                : "new-password"
            }
          />
        </label>

        {!isLogin && (
          <>
            <label className="auth__field">
              <span>Confirm password</span>

              <input
                type="password"
                value={form.confirm}
                onChange={update("confirm")}
                autoComplete="new-password"
              />
            </label>

            <label className="auth__field">
              <span>Role</span>

              <select
                value={form.role}
                onChange={update("role")}
              >
                <option value={ROLES.VIEWER}>
                  {ROLE_LABELS[ROLES.VIEWER]}
                </option>

                <option value={ROLES.SUPER_ADMIN}>
                  {ROLE_LABELS[ROLES.SUPER_ADMIN]}
                </option>
              </select>
            </label>
          </>
        )}

        <button
          type="submit"
          className="auth__submit"
          disabled={busy}
        >
          {busy
            ? "Please wait…"
            : isLogin
              ? "Login"
              : "Sign up"}
        </button>

        <p className="auth__switch">
          {isLogin
            ? "New here?"
            : "Already have an account?"}{" "}

          <button
            type="button"
            className="auth__link"
            onClick={() =>
              switchMode(
                isLogin
                  ? "signup"
                  : "login"
              )
            }
          >
            {isLogin
              ? "Create an account"
              : "Sign in"}
          </button>
        </p>
      </form>

      {popup && (
        <SuccessPopup
          title={popup.title}
          user={popup.user}
          onContinue={onAuthenticated}
        />
      )}
    </div>
  );
}

function SuccessPopup({
  title,
  user,
  onContinue,
}) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onContinue(user);
    }, POPUP_MS);

    return () => clearTimeout(timer);
  }, [user, onContinue]);

  return (
    <div
      className="auth-popup__backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="auth-popup">
        <div
          className="auth-popup__icon"
          aria-hidden="true"
        >
          ✓
        </div>

        <div className="auth-popup__title">
          {title}
        </div>

        <p className="auth-popup__text">
          Welcome, {user.username}. Opening the{" "}
          {ROLE_LABELS[user.role]} dashboard…
        </p>

        <button
          type="button"
          className="auth__submit"
          onClick={() =>
            onContinue(user)
          }
        >
          Continue
        </button>
      </div>
    </div>
  );
}