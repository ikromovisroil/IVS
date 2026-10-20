import type { StatusChipProps } from '../../ds'
import type { TechnicsStatus } from '../../api/types'
import { useT } from '../../i18n'

// main/models.py Technics.status → AlignUI StatusChip
export const TECHNICS_STATUS: Record<TechnicsStatus, { label: string; chip: StatusChipProps['status'] }> = {
  active: { label: 'Aktiv', chip: 'active' },
  free: { label: "Bo'sh", chip: 'absent' },
  repair: { label: "Ta'mirda", chip: 'in-progress' },
  defect: { label: 'Yaroqsiz', chip: 'failed' },
}

export const STATUS_OPTIONS = (Object.keys(TECHNICS_STATUS) as TechnicsStatus[]).map((value) => ({
  value,
  label: TECHNICS_STATUS[value].label,
}))

/** Select uchun tarjima qilingan holat variantlari */
export function useStatusOptions() {
  const t = useT()
  return STATUS_OPTIONS.map((o) => ({ ...o, label: t(o.label) }))
}
