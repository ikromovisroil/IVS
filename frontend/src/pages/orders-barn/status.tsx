import { StatusChip } from '../../ds'
import type { StatusChipProps } from '../../ds'
import type { BarnStatus } from './types'
import { useT } from '../../i18n'

// main/models.py Order.status → AlignUI StatusChip (eski ranglar: kutilmoqda — sariq, bajarildi — yashil, rad — qizil)
const CHIP: Record<BarnStatus, { label: string; chip: StatusChipProps['status'] }> = {
  viewed: { label: 'Yangi', chip: 'pending' },
  process: { label: 'Jarayonda', chip: 'in-progress' },
  finished: { label: 'Tayyorlandi', chip: 'active' }, // ATM arizalaridagi (orders/types.ts ORDER_STATUS) bilan bir xil
  approved: { label: 'Tasdiqlandi', chip: 'completed' },
  accepted: { label: 'Qabul qilindi', chip: 'completed' },
  canceled: { label: 'Bekor qilindi', chip: 'absent' },
  rejected: { label: 'Rad etildi', chip: 'failed' },
}

export function OrderStatus({ status, label }: { status: BarnStatus; label?: string }) {
  const t = useT()
  const c = CHIP[status] ?? CHIP.viewed
  // status_display — serverdagi o'zbekcha nom (CHIP bilan bir xil), lug'atdan tarjima qilinadi
  return <StatusChip status={c.chip}>{t(label || c.label)}</StatusChip>
}
