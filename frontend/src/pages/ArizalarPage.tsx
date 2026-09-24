import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Goal, Order, Paginated } from "../api/types";

export default function ArizalarPage() {
  const { me } = useAuth();
  const [items, setItems] = useState<Order[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [selectedGoal, setSelectedGoal] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ordersResp, goalsResp] = await Promise.all([
        api.get<Paginated<Order>>("/orders/"),
        api.get<Paginated<Goal>>("/goals/"),
      ]);
      setItems(ordersResp.data.results);
      setGoals(goalsResp.data.results);
    } catch {
      setError("Arizalarni yuklab bo'lmadi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createOrder() {
    if (!selectedGoal) return;
    setActionError(null);
    try {
      await api.post("/orders/", { goal: Number(selectedGoal), message_sender: message, materials: [] });
      setMessage("");
      setSelectedGoal("");
      await load();
    } catch {
      setActionError("Ariza yaratib bo'lmadi");
    }
  }

  async function runAction(orderId: number, path: string, body: Record<string, unknown> = {}) {
    setActionError(null);
    try {
      await api.post(`/orders/${orderId}/${path}/`, body);
      await load();
    } catch {
      setActionError("Amalni bajarib bo'lmadi");
    }
  }

  const myEmployeeId = me?.employee?.id;

  return (
    <div>
      <h1>Arizalar</h1>

      <div className="card">
        <h2>Yangi ariza</h2>
        <div className="filter-row">
          <select value={selectedGoal} onChange={(e) => setSelectedGoal(e.target.value)}>
            <option value="">Kategoriya tanlang...</option>
            {goals.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          <input placeholder="Izoh" value={message} onChange={(e) => setMessage(e.target.value)} />
          <button onClick={createOrder} disabled={!selectedGoal}>
            Yuborish
          </button>
        </div>
      </div>

      {actionError && <p className="error-text">{actionError}</p>}
      {loading && <p>Yuklanmoqda...</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !error && (
        <table className="data-table">
          <thead>
            <tr>
              <th>№</th>
              <th>Kategoriya</th>
              <th>Yuboruvchi</th>
              <th>Qabul qiluvchi</th>
              <th>Holati</th>
              <th>Amallar</th>
            </tr>
          </thead>
          <tbody>
            {items.map((o) => (
              <tr key={o.id}>
                <td>{o.id}</td>
                <td>{o.goal_name ?? "-"}</td>
                <td>{o.sender_name ?? "-"}</td>
                <td>{o.receiver_name ?? "-"}</td>
                <td>{o.status_display}</td>
                <td className="actions-cell">
                  {o.status === "viewed" && (
                    <button onClick={() => runAction(o.id, "accept")}>Qabul qilish</button>
                  )}
                  {o.status === "process" && o.receiver === myEmployeeId && (
                    <button onClick={() => runAction(o.id, "finish")}>Yakunlash</button>
                  )}
                  {o.status === "finished" && (o.sender === myEmployeeId || o.user === myEmployeeId) && (
                    <>
                      <button onClick={() => runAction(o.id, "decide", { action: "approved" })}>Tasdiqlash</button>
                      <button onClick={() => runAction(o.id, "decide", { action: "rejected" })}>Rad etish</button>
                    </>
                  )}
                  {o.status === "approved" && o.sender === myEmployeeId && (
                    <button onClick={() => runAction(o.id, "accepted", { rating: 5 })}>Yakuniy qabul (5)</button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-row">
                  Ariza topilmadi
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
