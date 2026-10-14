import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import ActivityRail from "../components/ActivityRail";

export default function Login() {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({ username: "", email: "", password: "" });

  const { login, register } = useAuth();
  const navigate = useNavigate();

  async function handleLogin(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(loginForm.email.trim(), loginForm.password);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(
        registerForm.username.trim(),
        registerForm.email.trim(),
        registerForm.password
      );
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode(next) {
    setMode(next);
    setError(null);
  }

  return (
    <div className="auth-shell">
      <div className="auth-panel">
        <div className="auth-card">
          <div className="brand">
            <span className="brand-mark" />
            <span className="brand-name">EMAIL AGENT</span>
          </div>

          {error && <div className="alert error visible">{error}</div>}

          {mode === "login" ? (
            <form onSubmit={handleLogin}>
              <div className="eyebrow">Welcome back</div>
              <h1>Sign in</h1>
              <p className="auth-sub">Access your agent's dashboard and session history.</p>

              <div className="field">
                <label htmlFor="login-email">Email</label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={loginForm.email}
                  onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="login-password">Password</label>
                <input
                  id="login-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                />
              </div>

              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? "Signing in…" : "Sign in"}
              </button>

              <div className="switch-mode">
                No account yet?{" "}
                <button type="button" onClick={() => switchMode("register")}>
                  Create one
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegister}>
              <div className="eyebrow">Get started</div>
              <h1>Create account</h1>
              <p className="auth-sub">Set up access to your Email Agent dashboard.</p>

              <div className="field">
                <label htmlFor="reg-username">Username</label>
                <input
                  id="reg-username"
                  type="text"
                  minLength={2}
                  maxLength={50}
                  required
                  value={registerForm.username}
                  onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="reg-email">Email</label>
                <input
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="reg-password">Password</label>
                <input
                  id="reg-password"
                  type="password"
                  minLength={8}
                  autoComplete="new-password"
                  required
                  value={registerForm.password}
                  onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                />
                <div className="field-hint">At least 8 characters, with one letter and one digit.</div>
              </div>

              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? "Creating account…" : "Create account"}
              </button>

              <div className="switch-mode">
                Already have an account?{" "}
                <button type="button" onClick={() => switchMode("login")}>
                  Sign in
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      <ActivityRail />
    </div>
  );
}
