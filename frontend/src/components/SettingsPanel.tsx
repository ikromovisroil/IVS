import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Avatar, Button, Icon, Switch } from '../ds'
import { LOGOUT_URL, useMe } from '../auth/me'
import { LANGS, useLang, useT } from '../i18n'
import { avatarColor, initials } from '../lib/format'
import { usePush } from '../lib/push'
import { useTheme } from '../theme'
import type { Theme } from '../theme'
import './SettingsPanel.css'

const THEMES: { value: Theme; label: string; hint: string }[] = [
  { value: 'light', label: "Yorug'", hint: 'Kunduzgi ish uchun' },
  { value: 'dark', label: 'Tungi', hint: 'Ko‘zni kamroq charchatadi' },
  { value: 'system', label: 'Tizim#mavzu', hint: 'Qurilma sozlamasiga ergashadi' },
]

interface Props {
  open: boolean
  onClose: () => void
}

/** Yon panel: profil, til va mavzu. Sidebar pastidagi profil tugmasidan ochiladi. */
export default function SettingsPanel({ open, onClose }: Props) {
  const me = useMe()
  const t = useT()
  const { lang, setLang } = useLang()
  const { theme, setTheme } = useTheme()
  const push = usePush()
  const navigate = useNavigate()
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const back = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    panel.current?.querySelector<HTMLElement>('.ivs-sp-close')?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      back?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  const name = me.employee?.full_name || me.username
  const sub = [me.employee?.rank_name, me.employee?.organization_name].filter(Boolean).join(' · ')

  return createPortal(
    <div className="ivs-sp-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside ref={panel} className="ivs-sp" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="ivs-sp-head">
          <h2 id={titleId} className="type-label-lg">
            {t('Sozlamalar')}
          </h2>
          <Button className="ivs-sp-close" variant="ghost" size="sm" icon="ri-close-line" iconOnly aria-label={t('Yopish')} onClick={onClose} />
        </header>

        <div className="ivs-sp-body">
          <section className="ivs-sp-profile">
            <Avatar size={48} initials={initials(name)} color={avatarColor(me.employee?.id ?? me.username)} name={name} />
            <div className="ivs-sp-who">
              <span className="type-label-md">{name}</span>
              {sub && <span className="type-para-xs ivs-sp-muted">{sub}</span>}
            </div>
            <Button
              variant="stroke"
              size="sm"
              onClick={() => {
                onClose()
                navigate('/profile')
              }}
            >
              {t('Profil')}
            </Button>
          </section>

          <section className="ivs-sp-section" aria-labelledby={`${titleId}-lang`}>
            <div className="ivs-sp-section-head">
              <Icon name="ri-translate-2" size={18} />
              <h3 id={`${titleId}-lang`} className="type-label-sm">
                {t('Til')}
              </h3>
            </div>
            <div className="ivs-sp-options is-two" role="radiogroup" aria-labelledby={`${titleId}-lang`}>
              {LANGS.map((l) => (
                <button
                  key={l.value}
                  type="button"
                  role="radio"
                  aria-checked={lang === l.value}
                  className={`ivs-sp-option${lang === l.value ? ' is-active' : ''}`}
                  onClick={() => setLang(l.value)}
                >
                  <span className="ivs-sp-lang">{l.short}</span>
                  <span className="ivs-sp-option-text">
                    <span className="type-label-sm">{l.label}</span>
                  </span>
                  <span className="ivs-sp-check" aria-hidden="true">
                    <Icon name="ri-check-line" size={14} />
                  </span>
                </button>
              ))}
            </div>
          </section>

          {push.state !== 'unsupported' && (
            <section className="ivs-sp-section" aria-labelledby={`${titleId}-push`}>
              <div className="ivs-sp-section-head">
                <Icon name="ri-notification-3-line" size={18} />
                <h3 id={`${titleId}-push`} className="type-label-sm">
                  {t('Bildirishnomalar')}
                </h3>
              </div>
              <Switch
                label={t('Brauzer bildirishnomalari')}
                sub={t(
                  push.state === 'denied'
                    ? "Brauzer sozlamalarida bildirishnomalarga ruxsat berilmagan. Manzil satridagi qulf belgisi orqali yoqing."
                    : "Sahifa yopiq bo'lsa ham yangi ariza va hujjatlar haqida xabar keladi.",
                )}
                checked={push.state === 'on'}
                disabled={push.busy || push.state === 'loading' || push.state === 'denied'}
                onChange={(on) => void push.toggle(on)}
              />
              {push.error && (
                <p className="ivs-form-error type-para-sm" role="alert">
                  {push.error}
                </p>
              )}
            </section>
          )}

          <section className="ivs-sp-section" aria-labelledby={`${titleId}-theme`}>
            <div className="ivs-sp-section-head">
              <Icon name="ri-contrast-2-line" size={18} />
              <h3 id={`${titleId}-theme`} className="type-label-sm">
                {t('Mavzu')}
              </h3>
            </div>
            <div className="ivs-sp-themes" role="radiogroup" aria-labelledby={`${titleId}-theme`}>
              {THEMES.map((th) => (
                <button
                  key={th.value}
                  type="button"
                  role="radio"
                  aria-checked={theme === th.value}
                  className={`ivs-sp-theme${theme === th.value ? ' is-active' : ''}`}
                  onClick={() => setTheme(th.value)}
                >
                  <span className={`ivs-sp-preview is-${th.value}`} aria-hidden="true">
                    <span className="ivs-sp-pv-side" />
                    <span className="ivs-sp-pv-main">
                      <span />
                      <span />
                      <span />
                    </span>
                  </span>
                  <span className="ivs-sp-theme-label">
                    <span className="type-label-sm">{t(th.label)}</span>
                    <span className="type-para-xs ivs-sp-muted">{t(th.hint)}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <footer className="ivs-sp-foot">
          <a className="ivs-sp-link" href="https://t.me/report_yatm_bot" target="_blank" rel="noopener noreferrer">
            <Icon name="ri-telegram-line" size={18} />
            {t('Telegram bot')}
          </a>
          <a className="ivs-sp-link is-danger" href={LOGOUT_URL}>
            <Icon name="ri-logout-box-r-line" size={18} />
            {t('Chiqish')}
          </a>
        </footer>
      </aside>
    </div>,
    document.body,
  )
}
