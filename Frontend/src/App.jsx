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
} from "./auth";

import "./App.css";

const RoleContext = createContext({
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
          <div className="app-header__brand">
            <span className="app-header__title">
              StorageWise AI
            </span>

            <span className="app-header__subtitle">
              Data Governance Console
            </span>
          </div>

          <UserBadge
            user={user}
            onLogout={logout}
          />
        </header>

        <main className="app-main">
          <Dashboard user={user} />
        </main>
      </div>
    </RoleContext.Provider>
  );
}

function UserBadge({
  user,
  onLogout,
}) {
  return (
    <div className="user-badge">
      <span className="user-badge__name">
        {user.username}
      </span>

      <span
        className={`user-badge__role user-badge__role--${user.role}`}
      >
        {ROLE_LABELS[user.role]}
      </span>

      <button
        type="button"
        className="user-badge__logout"
        onClick={onLogout}
      >
        Log out
      </button>
    </div>
  );
}