import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Material, Paginated } from "../api/types";

export default function MaterialsPage() {
  const [items, setItems] = useState<Material[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<Paginated<Material>>("/materials/", {
        params: q ? { search: q } : {},
      });
      setItems(resp.data.results);
    } catch {
      setError("Materiallarni yuklab bo'lmadi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load("");
  }, [load]);

  return (
    <div>
      <h1>Materiallar</h1>

      <form
        className="filter-row"
        onSubmit={(e) => {
          e.preventDefault();
          load(search);
        }}
      >
        <input placeholder="Nomi, 1C kod ..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <button type="submit">Qidirish</button>
      </form>

      {loading && <p>Yuklanmoqda...</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !error && (
        <table className="data-table">
          <thead>
            <tr>
              <th>№</th>
              <th>Nomi</th>
              <th>Birligi</th>
              <th>Soni</th>
              <th>Narxi</th>
              <th>Kod</th>
              <th>Mas'ul xodim</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m, idx) => (
              <tr key={m.id}>
                <td>{idx + 1}</td>
                <td>{m.name}</td>
                <td>{m.unit_name ?? "-"}</td>
                <td>{m.number}</td>
                <td>{m.price ?? "-"}</td>
                <td>{m.code ?? "-"}</td>
                <td>{m.employee_name ?? "-"}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="empty-row">
                  Ma'lumot topilmadi
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
