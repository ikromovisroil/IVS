import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Paginated, Technics } from "../api/types";

export default function TexnikaPage() {
  const [items, setItems] = useState<Technics[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<Paginated<Technics>>("/technics/", {
        params: q ? { search: q } : {},
      });
      setItems(resp.data.results);
    } catch {
      setError("Texnikalarni yuklab bo'lmadi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load("");
  }, [load]);

  return (
    <div>
      <h1>Texnikalar</h1>

      <form
        className="filter-row"
        onSubmit={(e) => {
          e.preventDefault();
          load(search);
        }}
      >
        <input placeholder="Nomi, inventar, seriya ..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <button type="submit">Qidirish</button>
      </form>

      {loading && <p>Yuklanmoqda...</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !error && (
        <table className="data-table">
          <thead>
            <tr>
              <th>№</th>
              <th>F.I.O</th>
              <th>Nomi</th>
              <th>I/R</th>
              <th>S/R</th>
              <th>Holati</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t, idx) => (
              <tr key={t.id}>
                <td>{idx + 1}</td>
                <td>{t.employee_name ?? "Biriktirilmagan"}</td>
                <td>{t.name}</td>
                <td>{t.inventory ?? "-"}</td>
                <td>{t.serial ?? "-"}</td>
                <td>{t.status_display}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-row">
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
