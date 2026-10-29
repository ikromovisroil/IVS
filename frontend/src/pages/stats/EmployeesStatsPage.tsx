import FilterBar from "../../components/FilterBar";
import EmptyState from "../../components/EmptyState";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  BarChart,
  CellUser,
  DataTable,
  HBarChart,
  Icon,
  Legend,
  Select,
  Widget,
} from "../../ds";
import type { DataTableColumn } from "../../ds";
import Page from "../../layout/Page";
import { api, apiAll } from "../../api/client";
import type { Named } from "../../api/types";
import { can, useMe } from "../../auth/me";
import { avatarColor, formatNumber, initials } from "../../lib/format";
import { useT } from "../../i18n";
import { formatDate, paletteColor, pickQuery, useParamState } from "./shared";
import { DateRange, Stat, StatsTabs } from "./ui";
import "./stats.css";

interface EmployeeRow {
  receiver_id: number;
  full_name: string;
  process_count: number;
  finished_count: number;
  approved_count: number;
  rejected_count: number;
  total_count: number;
  avg_rating: number | null;
}
interface EmployeeStats {
  filters: { region: string; date1: string; date2: string };
  ready: boolean;
  employees: EmployeeRow[];
  goals: { id: number; name: string; total: number }[];
}

const KEYS = ["region", "date1", "date2"] as const;

// Holatlar: eski jadval ustunlari tartibida
const STATUS_SERIES = [
  {
    key: "process_count",
    label: "Ish jarayonida",
    color: "var(--state-information-base)",
  },
  {
    key: "finished_count",
    label: "Yakunladi",
    color: "var(--state-warning-base)",
  },
  {
    key: "approved_count",
    label: "Qabul qilindi#stat",
    color: "var(--state-success-base)",
  },
  {
    key: "rejected_count",
    label: "Rad etilgan",
    color: "var(--state-error-base)",
  },
] as const;

const num = (n: number) =>
  n ? formatNumber(n) : <span className="st-muted">0</span>;

export default function EmployeesStatsPage() {
  const t = useT();
  const me = useMe();
  const { params, set } = useParamState();
  const qs = pickQuery(params, KEYS);

  const regions = useQuery({
    queryKey: ["stats", "ref", "regions"],
    queryFn: () => apiAll<Named>("/regions/"),
    staleTime: 300_000,
  });
  const stats = useQuery({
    queryKey: ["stats", "employees", qs],
    queryFn: () =>
      api<EmployeeStats>(`/spa/stats/employees/${qs ? `?${qs}` : ""}`),
    placeholderData: keepPreviousData,
  });
  const data = stats.data;
  // Filtr berilmasa server joriy oyni qo'llaydi — sanalar javobdan
  const value = {
    region: params.get("region") ?? "",
    date1:
      params.has("date1") || params.has("region") || params.has("date2")
        ? (params.get("date1") ?? "")
        : (data?.filters.date1 ?? ""),
    date2:
      params.has("date1") || params.has("region") || params.has("date2")
        ? (params.get("date2") ?? "")
        : (data?.filters.date2 ?? ""),
  };
  const update = (patch: Partial<typeof value>) => set({ ...value, ...patch });

  const rows = data?.employees ?? [];
  const goals = data?.goals ?? [];
  const sum = (key: keyof EmployeeRow) =>
    rows.reduce((s, r) => s + (Number(r[key]) || 0), 0);
  const total = sum("total_count");
  const rated = rows.filter((r) => r.avg_rating != null);
  const avgRating = rated.length
    ? (
        rated.reduce((s, r) => s + (r.avg_rating ?? 0), 0) / rated.length
      ).toFixed(1)
    : "—";

  const columns: DataTableColumn<EmployeeRow>[] = [
    {
      key: "n",
      label: t("T/r"),
      width: 56,
      render: (r) => rows.indexOf(r) + 1,
    },
    {
      key: "full_name",
      label: t("F.I.O"),
      sortable: true,
      sortValue: (r) => r.full_name,
      render: (r) => (
        <CellUser
          name={r.full_name}
          initials={initials(r.full_name)}
          color={avatarColor(r.receiver_id)}
          size={32}
        />
      ),
    },
    {
      key: "process_count",
      label: t("Ish jarayonida"),
      align: "right",
      sortable: true,
      sortValue: (r) => r.process_count,
      render: (r) => num(r.process_count),
    },
    {
      key: "finished_count",
      label: t("Yakunladi"),
      align: "right",
      sortable: true,
      sortValue: (r) => r.finished_count,
      render: (r) => num(r.finished_count),
    },
    {
      key: "approved_count",
      label: t("Qabul qilindi#stat"),
      align: "right",
      sortable: true,
      sortValue: (r) => r.approved_count,
      render: (r) => num(r.approved_count),
    },
    {
      key: "rejected_count",
      label: t("Rad etilgan"),
      align: "right",
      sortable: true,
      sortValue: (r) => r.rejected_count,
      render: (r) => num(r.rejected_count),
    },
    {
      key: "total_count",
      label: t("Jami"),
      align: "right",
      sortable: true,
      sortValue: (r) => r.total_count,
      render: (r) => <b>{formatNumber(r.total_count)}</b>,
    },
    {
      key: "avg_rating",
      label: t("Reyting"),
      align: "right",
      sortable: true,
      sortValue: (r) => r.avg_rating ?? -1,
      render: (r) =>
        r.avg_rating != null ? (
          <span className="st-rating">
            {r.avg_rating.toFixed(1)} <Icon name="ri-star-fill" size={16} />
          </span>
        ) : (
          null
        ),
    },
  ];

  const top = rows.slice(0, 8);
  const shortName = (n: string) => n.split(" ").slice(0, 2).join(" ");
  const period =
    data?.filters.date1 || data?.filters.date2
      ? `${formatDate(data.filters.date1) || "…"} — ${formatDate(data.filters.date2) || "…"}`
      : t("Barcha davr");

  return (
    <Page
      icon="ri-pie-chart-line"
      title="Statistika"
      subtitle="Bajaruvchi xodimlar samaradorligi va ariza murojaatlari."
    >
      <StatsTabs />

      <FilterBar>
        <div className="st-filter">
          <Select
            placeholder={t("Hudud")}
            options={[
              ...(can(me, "main.all_region")
                ? [{ value: "all", label: t("Barcha hududlar") }]
                : []),
              ...(regions.data ?? []).map((r) => ({
                value: String(r.id),
                label: r.name,
              })),
            ]}
            value={value.region || null}
            error={!!data && !data.ready}
            onChange={(v) => update({ region: v == null ? "" : String(v) })}
          />
        </div>
        <DateRange date1={value.date1} date2={value.date2} onChange={update} />
      </FilterBar>

      {stats.isError ? (
        <div className="ivs-empty" role="alert">
          {stats.error.message}
        </div>
      ) : stats.isPending ? (
        <div className="ivs-empty" aria-busy="true">
          {t("Yuklanmoqda…")}
        </div>
      ) : // Hudud tanlanmaguncha server hisoblamaydi — nol ko'rsatkichlar o'rniga keyingi qadamni ko'rsatamiz
      !data?.ready ? (
        <EmptyState
          icon="ri-map-pin-line"
          title="Hududni tanlang"
          description="Xodimlar statistikasini ko‘rish uchun hududni tanlang."
        />
      ) : (
        <div className={stats.isFetching ? "ivs-loading" : undefined}>
          <div className="aui-stats st-stats">
            <Stat label={t("Xodimlar")} value={rows.length} note={period} />
            <Stat label={t("Jami arizalar")} value={total} />
            <Stat
              label={t("Qabul qilindi#stat")}
              value={sum("approved_count")}
              note={
                total
                  ? `${Math.round((sum("approved_count") * 100) / total)}%`
                  : undefined
              }
            />
            <Stat label={t("O'rtacha reyting")} value={avgRating} />
          </div>

          <div className="aui-dgrid st-grid">
            <Widget
              className="aui-span-full"
              icon="ri-user-star-line"
              title={t("Xodimlar samaradorligi")}
            >
              {rows.length === 0 ? (
                <EmptyState
                  icon="ri-search-line"
                  title="Ma'lumot topilmadi"
                  description="Filtrlarni o‘zgartirib ko‘ring."
                />
              ) : (
                <DataTable
                  rows={rows}
                  columns={columns}
                  getRowId={(r) => r.receiver_id}
                  rowHeight={52}
                  minWidth={860}
                  caption={t("Xodimlar samaradorligi")}
                />
              )}
            </Widget>

            {top.length > 0 && (
              <Widget
                className="aui-span-2"
                icon="ri-bar-chart-2-line"
                title={t("Holatlar bo'yicha (eng faol 8 xodim)")}
              >
                <BarChart
                  data={top.map((r) => ({
                    label: shortName(r.full_name),
                    values: STATUS_SERIES.map((s) => r[s.key]),
                  }))}
                  series={STATUS_SERIES.map((s) => ({ color: s.color }))}
                  height={200}
                  label={t("Xodimlar arizalari holatlar bo'yicha")}
                />
                <Legend
                  items={STATUS_SERIES.map((s) => ({
                    label: t(s.label),
                    color: s.color,
                  }))}
                />
              </Widget>
            )}

            <Widget
              className={top.length ? undefined : "aui-span-full"}
              icon="ri-file-list-3-line"
              title={t("Ariza murojaatlari tahlili")}
            >
              {goals.length === 0 ? (
                <EmptyState
                  icon="ri-search-line"
                  title="Ma'lumot topilmadi"
                  description="Filtrlarni o‘zgartirib ko‘ring."
                />
              ) : (
                <>
                  <HBarChart
                    className="st-hbars"
                    data={goals
                      .filter((g) => g.total)
                      .map((g, i) => ({
                        label: g.name,
                        value: g.total,
                        display: t("{n} ta", { n: g.total }),
                        color: paletteColor(i),
                      }))}
                  />
                  <div className="st-goal-list">
                    {goals.map((g, i) => (
                      <div key={g.id} className="st-goal-row type-para-sm">
                        <span className="st-muted">{i + 1}</span>
                        <span className="st-ellipsis" title={g.name}>
                          {g.name}
                        </span>
                        <b>{formatNumber(g.total)}</b>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </Widget>
          </div>
        </div>
      )}
    </Page>
  );
}
