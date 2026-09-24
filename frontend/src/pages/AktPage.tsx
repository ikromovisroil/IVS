import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Deed, Employee, Paginated } from "../api/types";

export default function AktPage() {
  const { me } = useAuth();
  const [items, setItems] = useState<Deed[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [senderId, setSenderId] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [deedsResp, employeesResp] = await Promise.all([
        api.get<Paginated<Deed>>("/deeds/", { params: { status: "act" } }),
        api.get<Paginated<Employee>>("/employees/"),
      ]);
      setItems(deedsResp.data.results);
      setEmployees(employeesResp.data.results);
    } catch {
      setError("Hujjatlarni yuklab bo'lmadi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createAkt() {
    if (!senderId || !body.trim() || !me?.employee) return;
    setActionError(null);
    try {
      await api.post("/deeds/", {
        organization: me.employee.organization,
        sender: Number(senderId),
        user: me.employee.id,
        status: "act",
        body,
      });
      setBody("");
      setSenderId("");
      await load();
    } catch {
      setActionError("Akt yaratib bo'lmadi");
    }
  }

  async function generatePdf(deedId: number) {
    setActionError(null);
    setBusyId(deedId);
    try {
      await api.post(`/deeds/${deedId}/generate-pdf/`);
      await load();
    } catch {
      setActionError("PDF hosil qilib bo'lmadi");
    } finally {
      setBusyId(null);
    }
  }

  async function resolveConsent(consentId: number, kind: "approve" | "reject") {
    setActionError(null);
    const message = kind === "reject" ? window.prompt("Rad etish sababini yozing:") ?? "" : "";
    if (kind === "reject" && !message.trim()) return;

    try {
      await api.post(`/deed-consents/${consentId}/${kind}/`, { message });
      await load();
    } catch {
      setActionError("Amalni bajarib bo'lmadi");
    }
  }

  const apiOrigin = (import.meta.env.VITE_API_BASE_URL as string) ?? "http://127.0.0.1:8000";

  function resolveFileUrl(file: string) {
    // Backend 'file' maydonini so'rov konteksti bilan TO'LIQ URL sifatida
    // qaytaradi - shu sabab qayta prefiks qo'shmaymiz.
    return file.startsWith("http") ? file : `${apiOrigin}${file}`;
  }

  return (
    <div>
      <h1>Akt</h1>

      <div className="card">
        <h2>Yangi Akt</h2>
        <div className="filter-row">
          <select value={senderId} onChange={(e) => setSenderId(e.target.value)}>
            <option value="">Imzolovchi xodim...</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.full_name}
              </option>
            ))}
          </select>
        </div>
        <textarea
          className="body-textarea"
          placeholder="Hujjat matni..."
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
        />
        <button onClick={createAkt} disabled={!senderId || !body.trim()}>
          Yaratish
        </button>
      </div>

      {actionError && <p className="error-text">{actionError}</p>}
      {loading && <p>Yuklanmoqda...</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !error && (
        <div className="deed-list">
          {items.map((d) => (
            <div className="deed-card" key={d.id}>
              <div className="deed-card-head">
                <b>{d.code}</b>
                <span>{d.status_sender_display}</span>
              </div>
              <div>Imzolovchi: {d.sender_name ?? "-"}</div>
              <div>Yaratdi: {d.user_name ?? "-"}</div>

              <div className="deed-card-actions">
                <button onClick={() => generatePdf(d.id)} disabled={busyId === d.id}>
                  {busyId === d.id ? "Tayyorlanmoqda..." : "PDF yaratish"}
                </button>
                {d.file && (
                  <a href={resolveFileUrl(d.file)} target="_blank" rel="noopener noreferrer">
                    PDF yuklab olish
                  </a>
                )}
              </div>

              {d.consents.length > 0 && (
                <div className="consent-list">
                  <div className="consent-title">Kelishuvchilar</div>
                  {d.consents.map((c) => (
                    <div className="consent-row" key={c.id}>
                      <span>{c.employee_name}</span>
                      <span>{c.status_display}</span>
                      {c.status === "viewed" && c.employee === me?.employee?.id && (
                        <span className="consent-actions">
                          <button onClick={() => resolveConsent(c.id, "approve")}>Tasdiqlash</button>
                          <button onClick={() => resolveConsent(c.id, "reject")}>Rad etish</button>
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {items.length === 0 && <p className="empty-row">Akt topilmadi</p>}
        </div>
      )}
    </div>
  );
}
