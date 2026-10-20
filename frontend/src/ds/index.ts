// AlignUI Design System (Claude Design: "AlignUI Design System") — React komponentlari.
// bundle.js, bundle.css, tokens.css va alignui.d.ts (asli index.d.ts) dizayn tizimidan ko'chirilgan.
// O'zgarishlar: bundle.css dagi RemixIcon CDN importi olib tashlangan (npm'dan yuklanadi); bundle.js dagi Select
// ichki matnlari ("No results", "N options", "Clear") props.labels dan olinadigan qilingan — tarjima uchun (pastdagi Select).
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { useT } from '../i18n'
import './react-global'
import './bundle.js'
import 'remixicon/fonts/remixicon.css'
import './tokens.css'
import './bundle.css'

export type * from './alignui'

type Types = typeof import('./alignui')

// alignui.d.ts dagi Window turida AppShell, MobileHeader va LandingNavbar yo'q, bundle esa ularni eksport qiladi.
const DS = window.AlignUIDesignSystem_019de2 as Window['AlignUIDesignSystem_019de2'] &
  Pick<Types, 'AppShell' | 'MobileHeader' | 'LandingNavbar'>

export const {
  AppShell,
  AreaChart,
  Avatar,
  AvatarGroup,
  Badge,
  BarChart,
  BudgetOverviewWidget,
  Button,
  CellUser,
  Checkbox,
  ConversionRateWidget,
  CourseProgressWidget,
  CoursesWidget,
  CreditScoreWidget,
  DailyFeedbackWidget,
  DailyWorkHoursWidget,
  DashboardSidebar,
  DataTable: DSDataTable,
  Delta,
  EmployeeSpotlightWidget,
  ExchangeWidget,
  Flag,
  GaugeChart,
  HBarChart,
  Heatmap,
  Icon,
  Kbd,
  LandingNavbar,
  Legend,
  LineChart,
  MajorExpensesWidget,
  MobileHeader,
  MyCardsWidget,
  NavItem,
  PageHeader,
  Pagination,
  ProgressBar,
  ProgressCircle,
  QuickTransferWidget,
  RadarChart,
  Radio,
  RecentTransactionsWidget,
  SearchField,
  SegmentBar,
  SegmentedControl,
  Select: DSSelect,
  Sidebar,
  SpendingSummaryWidget,
  StatCard,
  StatusBadge,
  StatusChip,
  Switch,
  Tag,
  TextInput,
  Textarea,
  TimeTrackerWidget,
  Topbar,
  TotalBalanceWidget,
  TotalExpensesWidget,
  TotalSalesWidget,
  TotalVisitorsWidget,
  Trend,
  UserRetentionWidget,
  VisitorChannelsWidget,
  WeeklyVisitorsWidget,
  Widget,
  WidgetButton,
} = DS

// DataTable: tor ustunlar (T/r, №, kengligi ≤ 80px) matn kengligida qolsin. Jadval `table-layout: auto` bo'lgani uchun
// ortiqcha joy barcha ustunlarga bo'linib, "T/r" kabi ustunlar keng bo'lib ketardi; width: 1% + nowrap ularni siqadi.
const NARROW_LABEL = /^(t\/r|№|#|ariza №|n)$/i

function isNarrow(c: { label?: unknown; width?: number | string }) {
  return (typeof c.width === 'number' && c.width <= 80) || (typeof c.label === 'string' && NARROW_LABEL.test(c.label.trim()))
}

export const DataTable = ((props: Parameters<typeof DSDataTable>[0]) =>
  createElement(DSDataTable, {
    ...props,
    columns: props.columns.map((c) =>
      isNarrow(c)
        ? {
            ...c,
            // px berilgan bo'lsa — 44–52px (table-layout: fixed jadvallarda ham to'g'ri); aks holda 1% (auto jadvalda kontent kengligi)
            width: typeof c.width === 'number' ? Math.max(44, Math.min(c.width, 52)) : '1%',
            render: (row: unknown) => createElement('span', { className: 'ivs-cell-nowrap' }, c.render ? c.render(row) : (row as Record<string, ReactNode>)[c.key]) }
        : c,
    ),
  })) as typeof DSDataTable

// Select: dizayn tizimining ichki matnlari (placeholder, qidiruv, "topilmadi", variantlar soni, "Tozalash") joriy tilda.
type SelectProps = Parameters<typeof DSSelect>[0]

export const Select = (props: SelectProps) => {
  const t = useT()
  return createElement(DSSelect, {
    ...props,
    placeholder: props.placeholder ?? t('Tanlang...'),
    searchPlaceholder: props.searchPlaceholder ?? t('Qidirish...'),
    labels: { noResults: t('“{q}” bo‘yicha hech narsa topilmadi'), count: t('{n} ta variant'), clear: t('Tozalash') },
  } as SelectProps)
}
