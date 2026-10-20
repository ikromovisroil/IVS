import { useQuery } from '@tanstack/react-query'
import { apiAll } from '../../api/client'
import type { Category, Named } from '../../api/types'

const DAY = 24 * 60 * 60 * 1000
const opts = (xs: Named[] | undefined) => (xs ?? []).map((x) => ({ value: x.id, label: x.name }))

/** Turi (guruh), kategoriya va tashkilot ro'yxatlari — filtrlar va forma uchun. */
export function useTechnicsRefs() {
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => apiAll<Named>('/groups/'), staleTime: DAY })
  const categories = useQuery({ queryKey: ['categories'], queryFn: () => apiAll<Category>('/categories/'), staleTime: DAY })
  const organizations = useQuery({ queryKey: ['organizations'], queryFn: () => apiAll<Named>('/organizations/'), staleTime: DAY })

  return {
    groupOptions: opts(groups.data),
    organizationOptions: opts(organizations.data),
    categoryOptions: (groupId: number | null) =>
      opts((categories.data ?? []).filter((c) => groupId == null || c.group === groupId)),
  }
}
