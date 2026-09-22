import React, {
  createContext,
  useContext,
  useState,
} from "react";

import Dashboard from "./pages/Dashboard";
import AuthPage from "./pages/AuthPage";

import {
  ROLES,
  ROLE_LABELS,
  getSession,
  clearSession,
} from "./api";

import "./App.css";

export const RoleContext = createContext({
  role: ROLES.VIEWER,
  user: null,
  logout: () => {},
});

export function useRole() {
  return useContext(RoleContext);
}

export { ROLES };

export default function App() {
  const [user, setUser] = useState(() => getSession());

  if (!user) {
    return (
      <AuthPage
        onAuthenticated={(authenticatedUser) => {
          setUser(authenticatedUser);
        }}
      />
    );
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  return (
    <RoleContext.Provider
      value={{
        role: user.role,
        user,
        logout,
      }}
    >
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header__inner">
            <div className="app-header__brand">
              <span className="app-header__mark" aria-hidden="true">
                S
              </span>
              <div className="app-header__brand-text">
                <span className="app-header__title">StoreSmart</span>
                <span className="app-header__subtitle">
                  Storage governance console
                </span>
              </div>
            </div>
            <UserBadge user={user} onLogout={logout} />
          </div>
        </header>
        <main className="app-main">
          <Dashboard user={user} />
        </main>
      </div>
    </RoleContext.Provider>
  );
}

function UserBadge({ user, onLogout }) {
  return (
    <div className="user-badge">
      <span className="user-badge__name">{user.username}</span>
      <span className="hds-tag hds-tag--brand">
        {ROLE_LABELS[user.role]}
      </span>
      <button
        type="button"
        className="hds-button hds-button--secondary hds-button--small"
        onClick={onLogout}
      >
        Log out
      </button>
    </div>
  );
}