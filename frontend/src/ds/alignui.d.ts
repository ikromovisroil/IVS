import type * as React from 'react';

/** A RemixIcon class name ("ri-add-line") or any React node. */
export type IconProp = string | React.ReactNode;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style. Default "primary". */
  variant?: 'primary' | 'stroke' | 'lighter' | 'ghost' | 'error' | 'error-lighter' | 'success' | 'warning' | 'purple' | 'dark';
  /** Height 48 / 40 / 36 / 28px. Default "md". */
  size?: 'xl' | 'lg' | 'md' | 'sm';
  icon?: IconProp;
  iconRight?: IconProp;
  /** Square button showing only `icon`; pass aria-label. */
  iconOnly?: boolean;
  /** Fully rounded (radius-full). */
  pill?: boolean;
  /** Shows a spinner and disables the button. */
  loading?: boolean;
}
export declare function Button(props: ButtonProps): React.ReactElement;

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: React.ReactNode;
  /** Helper text under the field; red when `error`. */
  hint?: React.ReactNode;
  error?: boolean;
}
export declare function TextInput(props: TextInputProps): React.ReactElement;

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: boolean;
}
export declare function Textarea(props: TextareaProps): React.ReactElement;

export interface SelectOption {
  value: string | number;
  label: string;
  /** Icon shown in a tinted square. */
  icon?: IconProp;
  /** CSS color for the icon and its tint, e.g. "var(--purple-500)". */
  color?: string;
}
export interface SelectProps {
  id?: string;
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: boolean;
  options: SelectOption[];
  value?: SelectOption['value'] | null;
  defaultValue?: SelectOption['value'] | null;
  onChange?: (value: SelectOption['value'] | null) => void;
  placeholder?: string;
  /** Search box at the top of the panel. Default true. */
  searchable?: boolean;
  searchPlaceholder?: string;
  /** "Clear" link in the footer. Default true. */
  clearable?: boolean;
  disabled?: boolean;
  className?: string;
}
export declare function Select(props: SelectProps): React.ReactElement;

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'type'> {
  label?: React.ReactNode;
  /** Secondary line under the label. */
  sub?: React.ReactNode;
  indeterminate?: boolean;
  onChange?: (checked: boolean, event: React.ChangeEvent<HTMLInputElement>) => void;
}
export declare function Checkbox(props: CheckboxProps): React.ReactElement;

export interface RadioProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'type'> {
  label?: React.ReactNode;
  sub?: React.ReactNode;
  /** Called with this radio's `value`. */
  onChange?: (value: RadioProps['value'], event: React.ChangeEvent<HTMLInputElement>) => void;
}
export declare function Radio(props: RadioProps): React.ReactElement;

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'type'> {
  label?: React.ReactNode;
  sub?: React.ReactNode;
  onChange?: (checked: boolean, event: React.ChangeEvent<HTMLInputElement>) => void;
}
export declare function Switch(props: SwitchProps): React.ReactElement;

export interface BadgeProps {
  tone?: 'primary' | 'success' | 'error' | 'warning' | 'purple' | 'orange' | 'teal' | 'pink' | 'sky' | 'neutral';
  /** Font 14 / 16 / 16px with growing padding. Default "md". */
  size?: 'sm' | 'md' | 'lg';
  /** Leading dot in the badge color. */
  dot?: boolean;
  icon?: IconProp;
  onRemove?: (event: React.MouseEvent) => void;
  children?: React.ReactNode;
  className?: string;
}
export declare function Badge(props: BadgeProps): React.ReactElement;

export interface StatusBadgeProps {
  status?: 'online' | 'away' | 'busy' | 'offline' | 'active';
  /** Defaults to the status name. */
  children?: React.ReactNode;
  className?: string;
}
export declare function StatusBadge(props: StatusBadgeProps): React.ReactElement;

export interface TagProps {
  icon?: IconProp;
  /** Palette name or any CSS color; omit for the neutral tag. */
  color?: 'purple' | 'blue' | 'orange' | 'green' | 'pink' | 'teal' | 'red' | 'sky' | 'yellow' | (string & {});
  /** Show the × button. Default true. */
  removable?: boolean;
  /** Called on ×; without it the tag hides itself. */
  onRemove?: (event: React.MouseEvent) => void;
  children?: React.ReactNode;
  className?: string;
}
export declare function Tag(props: TagProps): React.ReactElement | null;

export interface AvatarProps {
  initials?: string;
  src?: string;
  /** Accessible name. */
  name?: string;
  /** Pixel size: 24, 32, 40, 48, 56, 64. Default 40. */
  size?: number;
  fontSize?: number;
  /** Palette name or any CSS color for the initials fill. Default primary-base. */
  color?: 'blue' | 'purple' | 'orange' | 'green' | 'teal' | 'red' | 'pink' | 'sky' | 'yellow' | 'gray' | (string & {});
  status?: 'online' | 'away' | 'busy' | 'offline';
  className?: string;
}
export declare function Avatar(props: AvatarProps): React.ReactElement;

export interface AvatarGroupProps {
  items: AvatarProps[];
  /** 32, 40 or 48. Default 40. */
  size?: number;
  /** Avatars shown before the "+N" chip. Default 4. */
  max?: number;
  className?: string;
}
export declare function AvatarGroup(props: AvatarGroupProps): React.ReactElement;

export interface NavItemProps extends React.HTMLAttributes<HTMLElement> {
  icon?: IconProp;
  label?: React.ReactNode;
  active?: boolean;
  /** Red count pill at the end. */
  badge?: React.ReactNode;
  /** Renders an <a> when set, else a <button>. */
  href?: string;
}
export declare function NavItem(props: NavItemProps): React.ReactElement;

export interface SidebarProps {
  brand: { name: React.ReactNode; sub?: React.ReactNode; icon?: IconProp; logo?: string };
  sections: { label?: React.ReactNode; items: NavItemProps[] }[];
  user?: { initials?: string; src?: string; name: string; email?: string };
  onSelect?: (item: NavItemProps, event: React.MouseEvent) => void;
  className?: string;
  'aria-label'?: string;
}
export declare function Sidebar(props: SidebarProps): React.ReactElement;

export interface TopbarProps {
  title: React.ReactNode;
  /** Actions on the right, usually Buttons. */
  children?: React.ReactNode;
  className?: string;
}
export declare function Topbar(props: TopbarProps): React.ReactElement;

export interface StatCardProps {
  label: React.ReactNode;
  value: React.ReactNode;
  /** One line under the value, e.g. "↑ 12 this month". */
  change?: React.ReactNode;
  /** Paints `change` in state-error. */
  negative?: boolean;
  className?: string;
}
export declare function StatCard(props: StatCardProps): React.ReactElement;

/* ── Dashboard kit ─────────────────────────────────────── */
export interface IconProps { /** AlignUI icon name (see Icon.alignui) or any RemixIcon name, with or without "ri-". */ name: string; /** px; default 20. */ size?: number; color?: string; /** Accessible name; omit for decorative icons. */ title?: string; className?: string; style?: React.CSSProperties; }
export declare function Icon(props: IconProps): React.ReactElement;
export interface FlagProps { /** Country or region name in any case ("United States", "uzbekistan"); see Flag.names. */ name: string; /** px; default 24. */ size?: number; title?: string; className?: string; }
export declare function Flag(props: FlagProps): React.ReactElement;
export interface SegmentedItem { value: string | number; label: React.ReactNode; count?: number; icon?: string; }
export interface SegmentedControlProps { items: SegmentedItem[]; value?: SegmentedItem['value']; defaultValue?: SegmentedItem['value']; onChange?: (v: SegmentedItem['value']) => void; className?: string; 'aria-label'?: string; }
export declare function SegmentedControl(props: SegmentedControlProps): React.ReactElement;
export interface ProgressBarProps { value: number; max?: number; showValue?: boolean; label?: string; color?: string; className?: string; }
export declare function ProgressBar(props: ProgressBarProps): React.ReactElement;
export interface ProgressCircleProps { value: number; size?: number; strokeWidth?: number; color?: string; label?: string; children?: React.ReactNode; className?: string; }
export declare function ProgressCircle(props: ProgressCircleProps): React.ReactElement;
export interface DeltaProps { /** Signed string: "+5%", "-3%". */ value: string; tone?: 'success' | 'error' | 'neutral'; className?: string; }
export declare function Delta(props: DeltaProps): React.ReactElement;
export interface TrendProps { value: string; down?: boolean; arrow?: 'up-down' | 'diag'; className?: string; }
export declare function Trend(props: TrendProps): React.ReactElement;
export interface StatusChipProps { status: 'completed' | 'active' | 'paid' | 'in-progress' | 'pending' | 'absent' | 'failed' | 'refunded'; children?: React.ReactNode; className?: string; }
export declare function StatusChip(props: StatusChipProps): React.ReactElement;
export declare function Kbd(props: { children: React.ReactNode; className?: string }): React.ReactElement;
export interface WidgetAction { label: React.ReactNode; icon?: string; iconRight?: string; onClick?: (e: React.MouseEvent) => void; }
export interface WidgetProps { icon?: string | React.ReactNode; title?: React.ReactNode; action?: WidgetAction | React.ReactNode; extra?: React.ReactNode; /** Default true when there is a header. */ divider?: boolean; className?: string; style?: React.CSSProperties; children?: React.ReactNode; }
export declare function Widget(props: WidgetProps): React.ReactElement;
export interface WidgetButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { icon?: string; iconRight?: string; }
export declare function WidgetButton(props: WidgetButtonProps): React.ReactElement;
export declare function Legend(props: { items: { label: React.ReactNode; color: string }[]; className?: string }): React.ReactElement;
export declare function SearchField(props: { placeholder?: string; shortcut?: string; className?: string }): React.ReactElement;
export interface DataTableColumn<R = any> { key: string; label: React.ReactNode; sortable?: boolean; render?: (row: R) => React.ReactNode; sortValue?: (row: R) => any; width?: number | string; align?: 'left' | 'center' | 'right'; }
export interface DataTableProps<R = any> { columns: DataTableColumn<R>[]; rows: R[]; getRowId?: (row: R, index: number) => string | number; selectable?: boolean; defaultSelected?: (string | number)[]; onSelectionChange?: (ids: (string | number)[]) => void; rowActions?: boolean | ((row: R, e: React.MouseEvent) => void); /** px; default 64. */ rowHeight?: number; /** The table keeps this width and scrolls sideways below it. px or CSS length; default 720, 0 to let it squeeze. */ minWidth?: number | string; defaultSort?: { key: string; dir: 'asc' | 'desc' } | null; pagination?: PaginationProps; caption?: string; className?: string; }
export declare function DataTable<R = any>(props: DataTableProps<R>): React.ReactElement;
export declare function CellUser(props: { name: React.ReactNode; sub?: React.ReactNode; initials?: string; src?: string; color?: AvatarProps['color']; size?: number; avatar?: boolean }): React.ReactElement;
export interface PaginationProps { pageCount: number; page?: number; defaultPage?: number; onChange?: (page: number) => void; /** Rows per page shown in the picker; omit to hide it. */ perPage?: number; className?: string; }
export declare function Pagination(props: PaginationProps): React.ReactElement;
export interface DashboardNavItem { icon?: string; /** CSS color: renders a dot instead of an icon (favourites). */ dot?: string; label: React.ReactNode; active?: boolean; shortcut?: string; badge?: React.ReactNode; href?: string; onClick?: (e: React.MouseEvent) => void; }
export interface DashboardSidebarProps { brand: { name: React.ReactNode; sub?: React.ReactNode; icon?: string; logo?: string }; sections: { label?: React.ReactNode; addable?: boolean; items: DashboardNavItem[] }[]; footerItems?: DashboardNavItem[]; user?: { name: string; email?: string; initials?: string; src?: string; color?: AvatarProps['color']; verified?: boolean }; onSelect?: (item: DashboardNavItem, e: React.MouseEvent) => void; /** 80px rail: icons only (Figma Sidebar Collapsed). AppShell sets this by width. */ collapsed?: boolean; /** Shows the round edge chevron (rail → overlay). */ onExpand?: () => void; /** Shows a close button (drawer). */ onClose?: () => void; id?: string; className?: string; 'aria-label'?: string; }
export declare function DashboardSidebar(props: DashboardSidebarProps): React.ReactElement;
export interface PageHeaderProps { title: React.ReactNode; subtitle?: React.ReactNode; avatar?: AvatarProps; icon?: string; search?: boolean; notifications?: boolean | 'none'; children?: React.ReactNode; className?: string; style?: React.CSSProperties; }
export declare function PageHeader(props: PageHeaderProps): React.ReactElement;
/** 72px dashboard header for phones (Figma mobile Navigation). AppShell shows it under 768px. */
export interface MobileHeaderProps { brand?: { name?: string; icon?: string; logo?: string }; search?: boolean; notifications?: boolean | 'none'; children?: React.ReactNode; open?: boolean; onMenu?: () => void; controls?: string; className?: string; }
export declare function MobileHeader(props: MobileHeaderProps): React.ReactElement;
/** Sidebar + header + scrolling content; responsive by its own width: ≥1280 sidebar 272 · 768–1279 rail 80 · <768 MobileHeader + drawer. Give it height: 100dvh. */
export interface AppShellProps { sidebar: DashboardSidebarProps; header?: React.ReactNode; children?: React.ReactNode; collapse?: 'auto' | 'expanded' | 'rail' | 'drawer'; mobileHeader?: Omit<MobileHeaderProps, 'open' | 'onMenu' | 'controls'>; defaultOpen?: boolean; onOpenChange?: (open: boolean) => void; className?: string; style?: React.CSSProperties; }
export declare function AppShell(props: AppShellProps): React.ReactElement;
/** Figma Navigation [Landing Page]: 72px bar ≥1024px of its own width, 64px bar + full-width menu below. */
export interface LandingNavLink { label: React.ReactNode; href?: string; badge?: React.ReactNode; active?: boolean; menu?: { feature?: { icon?: string; title: React.ReactNode; description?: React.ReactNode; chips?: { icon?: string; label: React.ReactNode; href?: string }[]; footnote?: React.ReactNode }; groups?: { label: React.ReactNode; items: { label: React.ReactNode; href?: string; external?: boolean; icon?: string }[] }[] }; }
export interface LandingNavbarProps { brand?: { name?: string; icon?: string; logo?: string; href?: string; wordmark?: boolean }; links?: LandingNavLink[]; actions?: { secondary?: { label: React.ReactNode; href?: string }; primary?: { label: React.ReactNode; href?: string } }; tools?: React.ReactNode; variant?: 'bar' | 'floating'; defaultMenu?: number; defaultOpen?: boolean; className?: string; }
export declare function LandingNavbar(props: LandingNavbarProps): React.ReactElement;
export interface LineChartProps { data: number[]; height?: number; width?: number; color?: string; smooth?: boolean; area?: boolean; grid?: number; hgrid?: number; strokeWidth?: number; xLabels?: React.ReactNode[]; min?: number; max?: number; label?: string; className?: string; }
export declare function LineChart(props: LineChartProps): React.ReactElement;
export declare function AreaChart(props: { series: { data: number[]; color: string; opacity?: number }[]; height?: number; max?: number; length?: number; xLabels?: React.ReactNode[]; label?: string; className?: string }): React.ReactElement;
export declare function BarChart(props: { data: { label: string; values: number[] }[]; series?: { color: string }[]; max?: number; height?: number; yTicks?: React.ReactNode[]; label?: string; className?: string }): React.ReactElement;
export declare function HBarChart(props: { data: { label: string; value: number; display?: React.ReactNode; color?: string }[]; max?: number; ticks?: React.ReactNode[]; highlight?: number; className?: string }): React.ReactElement;
export declare function SegmentBar(props: { segments: { label: React.ReactNode; value: number; color?: string }[]; legend?: boolean; className?: string }): React.ReactElement;
export declare function GaugeChart(props: { segments: { value: number; color?: string }[]; total?: number; caption?: React.ReactNode; value?: React.ReactNode; size?: number; strokeWidth?: number; label?: string; className?: string }): React.ReactElement;
export declare function Heatmap(props: { rows: number[][]; xLabels?: React.ReactNode[]; color?: string; label?: string; className?: string }): React.ReactElement;
export declare function RadarChart(props: { axes: string[]; series: { data: number[]; color: string }[]; size?: number; label?: string; className?: string }): React.ReactElement;
/** Widgets: every prop is optional and defaults to Figma's sample data. */
export interface WidgetBaseProps { className?: string; }
export declare function TimeTrackerWidget(props: WidgetBaseProps & { project?: string; seconds?: number; tasks?: { title: string; time: string; icon?: string; color?: string }[] }): React.ReactElement;
export declare function DailyWorkHoursWidget(props: WidgetBaseProps & { hours?: number; minutes?: number; segments?: { label: string; value: number; color?: string }[] }): React.ReactElement;
export declare function CourseProgressWidget(props: WidgetBaseProps & { value?: number; course?: string; description?: string }): React.ReactElement;
export declare function EmployeeSpotlightWidget(props: WidgetBaseProps & { person?: { name: string; role?: string; initials?: string; src?: string; color?: AvatarProps['color'] }; caption?: string }): React.ReactElement;
export declare function DailyFeedbackWidget(props: WidgetBaseProps & { question?: string }): React.ReactElement;
export declare function CoursesWidget(props: WidgetBaseProps & { rows?: { id: string | number; name: string; initials?: string; color?: AvatarProps['color']; role?: string; course: string; dates?: string; progress: number; status: StatusChipProps['status'] }[] }): React.ReactElement;
export interface Transaction { title: string; sub?: string; amount: string; date?: string; icon?: string; color?: string; }
export declare function MyCardsWidget(props: WidgetBaseProps & { card?: { label?: string; amount?: string }; transactions?: Transaction[] }): React.ReactElement;
export declare function BudgetOverviewWidget(props: WidgetBaseProps & { data?: { label: string; values: number[] }[]; chartHeight?: number }): React.ReactElement;
export declare function SpendingSummaryWidget(props: WidgetBaseProps): React.ReactElement;
export declare function ExchangeWidget(props: WidgetBaseProps & { amount?: string }): React.ReactElement;
export declare function TotalBalanceWidget(props: WidgetBaseProps & { value?: string; delta?: string; data?: number[] }): React.ReactElement;
export declare function TotalExpensesWidget(props: WidgetBaseProps & { value?: string; delta?: string; data?: number[] }): React.ReactElement;
export declare function QuickTransferWidget(props: WidgetBaseProps & { contacts?: { name: string; initials?: string; color?: AvatarProps['color'] }[] }): React.ReactElement;
export declare function RecentTransactionsWidget(props: WidgetBaseProps & { transactions?: Transaction[] }): React.ReactElement;
export declare function CreditScoreWidget(props: WidgetBaseProps & { score?: number; ratio?: number; note?: string }): React.ReactElement;
export declare function MajorExpensesWidget(props: WidgetBaseProps & { data?: { label: string; value: number; display?: string; color?: string }[] }): React.ReactElement;
export declare function TotalSalesWidget(props: WidgetBaseProps & { value?: string; delta?: string; data?: number[] }): React.ReactElement;
export declare function TotalVisitorsWidget(props: WidgetBaseProps & { value?: string; delta?: string }): React.ReactElement;
export declare function ConversionRateWidget(props: WidgetBaseProps & { value?: string; delta?: string }): React.ReactElement;
export declare function VisitorChannelsWidget(props: WidgetBaseProps & { value?: string; delta?: string }): React.ReactElement;
export declare function UserRetentionWidget(props: WidgetBaseProps & { value?: string; delta?: string; rows?: number[][] }): React.ReactElement;
export declare function WeeklyVisitorsWidget(props: WidgetBaseProps & { value?: string; delta?: string }): React.ReactElement;

declare global {
  interface Window {
    AlignUIDesignSystem_019de2: {
      Button: typeof Button; TextInput: typeof TextInput; Textarea: typeof Textarea; Select: typeof Select;
      Checkbox: typeof Checkbox; Radio: typeof Radio; Switch: typeof Switch;
      Badge: typeof Badge; StatusBadge: typeof StatusBadge; Tag: typeof Tag;
      Avatar: typeof Avatar; AvatarGroup: typeof AvatarGroup;
      NavItem: typeof NavItem; Sidebar: typeof Sidebar; Topbar: typeof Topbar; StatCard: typeof StatCard;
      Icon: typeof Icon; Flag: typeof Flag; SegmentedControl: typeof SegmentedControl; ProgressBar: typeof ProgressBar; ProgressCircle: typeof ProgressCircle; Delta: typeof Delta; Trend: typeof Trend; StatusChip: typeof StatusChip; Kbd: typeof Kbd; Widget: typeof Widget; WidgetButton: typeof WidgetButton; Legend: typeof Legend; DataTable: typeof DataTable; CellUser: typeof CellUser; Pagination: typeof Pagination; SearchField: typeof SearchField; DashboardSidebar: typeof DashboardSidebar; PageHeader: typeof PageHeader; LineChart: typeof LineChart; AreaChart: typeof AreaChart; BarChart: typeof BarChart; HBarChart: typeof HBarChart; SegmentBar: typeof SegmentBar; GaugeChart: typeof GaugeChart; Heatmap: typeof Heatmap; RadarChart: typeof RadarChart; TimeTrackerWidget: typeof TimeTrackerWidget; DailyWorkHoursWidget: typeof DailyWorkHoursWidget; CourseProgressWidget: typeof CourseProgressWidget; EmployeeSpotlightWidget: typeof EmployeeSpotlightWidget; DailyFeedbackWidget: typeof DailyFeedbackWidget; CoursesWidget: typeof CoursesWidget; MyCardsWidget: typeof MyCardsWidget; BudgetOverviewWidget: typeof BudgetOverviewWidget; SpendingSummaryWidget: typeof SpendingSummaryWidget; ExchangeWidget: typeof ExchangeWidget; TotalBalanceWidget: typeof TotalBalanceWidget; TotalExpensesWidget: typeof TotalExpensesWidget; QuickTransferWidget: typeof QuickTransferWidget; RecentTransactionsWidget: typeof RecentTransactionsWidget; CreditScoreWidget: typeof CreditScoreWidget; MajorExpensesWidget: typeof MajorExpensesWidget; TotalSalesWidget: typeof TotalSalesWidget; TotalVisitorsWidget: typeof TotalVisitorsWidget; ConversionRateWidget: typeof ConversionRateWidget; VisitorChannelsWidget: typeof VisitorChannelsWidget; UserRetentionWidget: typeof UserRetentionWidget; WeeklyVisitorsWidget: typeof WeeklyVisitorsWidget;
    };
  }
}
