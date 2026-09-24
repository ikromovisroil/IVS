import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Login yoki parol noto'g'ri");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>IVS</h1>
        <p className="subtitle">Tizimga kirish</p>

        <label>
          Login
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
        </label>

        <label>
          Parol
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>

        {error && <div className="error-text">{error}</div>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Kirilmoqda..." : "Kirish"}
        </button>
      </form>
    </div>
  );
}
