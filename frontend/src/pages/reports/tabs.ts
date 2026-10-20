import type { ReportKind } from './api'

// templates/base.html "Hisobotlar" menyusi tartibida; ko'rinishi /api/v1/spa/reports/ (reports[kind]) bo'yicha.
export const REPORT_TABS: { kind: ReportKind; path: string; label: string; icon: string; subtitle: string }[] = [
  { kind: 'document', path: '/reports/document', label: 'Dalolatnoma', icon: 'ri-file-paper-2-line', subtitle: "Shartnoma bo'yicha bajarilgan ishlar dalolatnomasi va 1-ilova." },
  { kind: 'svod', path: '/reports/svod', label: 'Yakuniy hisobot', icon: 'ri-file-chart-line', subtitle: "Tashkilotlar va hududlar bo'yicha sarf materiallar yakuniy hisoboti." },
  { kind: 'reestr', path: '/reports/reestr', label: 'Reestr', icon: 'ri-list-check-3', subtitle: "Tashkilot bo'limlari bo'yicha o'rnatilgan materiallar reestri." },
  { kind: 'akt', path: '/reports/akt', label: 'Akt', icon: 'ri-file-list-2-line', subtitle: "Sarf materiallarini o'rnatish ishlari haqida dalolatnoma." },
  { kind: 'service', path: '/reports/service', label: 'Sarf materiallar', icon: 'ri-archive-drawer-line', subtitle: "Uskuna va materiallarni hisobdan chiqarish dalolatnomasi." },
]
