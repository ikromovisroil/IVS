import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV_GROUPS: { title: string; items: { to: string; label: string; perm?: string }[] }[] = [
  {
    title: "Ariza",
    items: [{ to: "/arizalar", label: "Arizalar" }],
  },
  {
    title: "Material / Texnika",
    items: [
      { to: "/materiallar", label: "Materiallar", perm: "main.view_material" },
      { to: "/texnikalar", label: "Texnikalar", perm: "main.view_technics" },
    ],
  },
  {
    title: "Hujjatlar",
    items: [{ to: "/akt", label: "Akt" }],
  },
];

export default function AppLayout() {
  const { me, loading, logout, hasPerm } = useAuth();

  if (loading) return <div className="center-screen">Yuklanmoqda...</div>;
  if (!me) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">IVS</div>
        <nav>
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-group-title">{group.title}</div>
              {group.items
                .filter((item) => !item.perm || hasPerm(item.perm))
                .map((item) => (
                  <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
                    {item.label}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="employee-name">{me.employee?.full_name ?? me.username}</div>
          <button className="btn-secondary" onClick={logout}>
            Chiqish
          </button>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
