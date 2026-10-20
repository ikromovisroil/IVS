import type { SelectOption } from '../../ds'
import type { Emp } from './api'
import { empLabel } from './format'

export const empOptions = (list: Emp[] | undefined): SelectOption[] => (list ?? []).map((e) => ({ value: e.id, label: empLabel(e) }))

export const toId = (v: SelectOption['value'] | null): number | null => (v == null || v === '' ? null : Number(v))
