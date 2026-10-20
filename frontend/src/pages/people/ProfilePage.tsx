import { useQuery } from '@tanstack/react-query'
import { Avatar, Badge, Widget } from '../../ds'
import Page from '../../layout/Page'
import DataState from '../../components/DataState'
import { api } from '../../api/client'
import { avatarColor, initials } from '../../lib/format'
import { useT } from '../../i18n'
import { formatDateTime } from './api'
import type { Profile } from './api'
import './people.css'

function Row({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  const t = useT()
  return (
    <div className="ivs-people-row">
      <dt>{t(label)}</dt>
      <dd className={mono ? 'ivs-people-mono' : undefined}>{value || '—'}</dd>
    </div>
  )
}

/** "Profil" — templates/main/profil.html (main/views.py: profil). */
export default function ProfilePage() {
  const t = useT()
  const q = useQuery({ queryKey: ['people', 'profile'], queryFn: () => api<Profile>('/spa/people/profile/') })
  const p = q.data
  const structure = p ? [p.organization_name, p.department_name, p.directorate_name, p.division_name].filter(Boolean) : []

  return (
    <Page icon="ri-user-line" title="Profil" subtitle="Shaxsiy ma'lumotlar va ish joyi.">
      <DataState isPending={q.isPending} error={q.error} empty={false} emptyText="">
        {p && (
          <div className="ivs-people-profile">
            <Widget className="ivs-people-card">
              <div className="ivs-people-card-body">
                <Avatar initials={initials(p.full_name)} name={p.full_name} size={64} fontSize={22} color={avatarColor(p.id)} />
                <h2 className="type-h5">{p.full_name}</h2>
                <p className="type-para-sm ivs-people-note">{p.rank_name || t('Lavozim kiritilmagan')}</p>
                {p.organization_type && (
                  <Badge tone={p.organization_type === 'worker' ? 'primary' : 'teal'} dot>
                    {t(p.organization_type === 'worker' ? 'ATM xodimi' : 'Mijoz tashkilot')}
                  </Badge>
                )}
              </div>
            </Widget>

            <div className="ivs-people-profile-main">
              <Widget icon="ri-building-line" title={t('Tashkilot nomi')}>
                {structure.length ? (
                  <ol className="ivs-people-path">
                    {structure.map((s) => (
                      <li key={s} className="type-para-sm">
                        {s}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="type-para-sm ivs-people-note">{t('Tashkilotga biriktirilmagan.')}</p>
                )}
              </Widget>

              <Widget icon="ri-profile-line" title={t('Profil tafsilotlari')}>
                <dl className="ivs-people-dl">
                  <Row label="To'liq ism" value={p.full_name} />
                  <Row label="Lavozim" value={p.rank_name} />
                  <Row label="Tel" value={p.phone} />
                  <Row label="Email" value={p.email} />
                  <Row label="Pinfl" value={p.pinfl} mono />
                  <Row label="Hudud" value={p.region_name} />
                  <Row label="Login" value={p.username} mono />
                  <Row label="Oxirgi kirish" value={formatDateTime(p.last_login)} />
                </dl>
              </Widget>
            </div>
          </div>
        )}
      </DataState>
    </Page>
  )
}
