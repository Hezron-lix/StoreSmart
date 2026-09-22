import React, { useEffect, useState } from "react";
import {
  ROLES,
  ROLE_LABELS,
  login,
  signup,
} from "../api";

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
      <div className="auth__card">
        {/* Brand mark at top of card */}
        <div className="auth__brand">
          <span className="auth__mark" aria-hidden="true">S</span>
          <span className="auth__brand-text">
            <span className="auth__brand-title">StoreSmart</span>
            <span className="auth__brand-subtitle">Storage governance console</span>
          </span>
        </div>

        {/* Mode toggle — pill switch */}
        <div className="auth__mode" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            role="tab"
            aria-selected={isLogin}
            className={
              "auth__mode-button" + (isLogin ? " auth__mode-button--active" : "")
            }
            onClick={() => switchMode("login")}
            disabled={busy}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={!isLogin}
            className={
              "auth__mode-button" + (!isLogin ? " auth__mode-button--active" : "")
            }
            onClick={() => switchMode("signup")}
            disabled={busy}
          >
            Create account
          </button>
        </div>

        {/* Heading + subtitle */}
        <div className="auth__heading">
          <h1 className="hds-heading--lg">
            {isLogin ? "Welcome back" : "Get started"}
          </h1>
          <p className="hds-text--sm hds-text--muted">
            {isLogin
              ? "Sign in to your StoreSmart account."
              : "Create an account to access the console."}
          </p>
        </div>

        {/* Notice */}
        {notice && (
          <p className="auth__notice" role="status">
            {notice}
          </p>
        )}

        {/* Error */}
        {error && (
          <p className="auth__error" role="alert">
            {error}
          </p>
        )}

        {/* Form */}
        <form className="auth__form" onSubmit={handleSubmit} noValidate>
          <label className="auth__field">
            <span className="auth__label">Username</span>
            <input
              className="auth__input"
              type="text"
              value={form.username}
              onChange={update("username")}
              autoComplete="username"
              autoFocus
              required
            />
          </label>

          <label className="auth__field">
            <span className="auth__label">Password</span>
            <input
              className="auth__input"
              type="password"
              value={form.password}
              onChange={update("password")}
              autoComplete={isLogin ? "current-password" : "new-password"}
              required
            />
          </label>

          {!isLogin && (
            <>
              <label className="auth__field">
                <span className="auth__label">Confirm password</span>
                <input
                  className="auth__input"
                  type="password"
                  value={form.confirm}
                  onChange={update("confirm")}
                  autoComplete="new-password"
                  required
                />
              </label>

              <fieldset className="auth__roles">
                <legend className="auth__label">Role</legend>
                <div className="auth__role-grid">
                  {[ROLES.VIEWER, ROLES.SUPER_ADMIN].map((r) => (
                    <label
                      key={r}
                      className={
                        "auth__role-tile" +
                        (form.role === r ? " auth__role-tile--active" : "")
                      }
                    >
                      <input
                        type="radio"
                        name="role"
                        value={r}
                        checked={form.role === r}
                        onChange={update("role")}
                      />
                      <span className="auth__role-name">
                        {ROLE_LABELS[r]}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </>
          )}

          <button
            type="submit"
            className="hds-button hds-button--primary auth__submit"
            disabled={busy}
          >
            {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>

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
    <div className="auth-popup__backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="auth-popup">
        <div className="auth-popup__icon" aria-hidden="true">✓</div>
        <h2 className="hds-heading--md auth-popup__title">{title}</h2>
        <p className="hds-text--sm hds-text--muted auth-popup__text">
          Welcome, {user.username}. Opening the {ROLE_LABELS[user.role]} dashboard…
        </p>
        <button
          type="button"
          className="hds-button hds-button--primary"
          style={{ width: "100%" }}
          onClick={() => onContinue(user)}
        >
          Continue
        </button>
      </div>
    </div>
  );
}