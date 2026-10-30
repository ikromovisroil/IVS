import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Icon, SegmentedControl, TextInput } from '../ds'
import { api } from '../api/client'
import { SSO_LOGIN_URL } from '../auth/me'
import { LANGS, useLang, useT } from '../i18n'
import type { Lang } from '../i18n'
import './login.css'

const FEATURES = [
  { icon: 'ri-file-list-3-line', title: 'Arizalar', text: "ATMga ariza yuborish, ijrosini va omborxona so'rovlarini kuzatish" },
  { icon: 'ri-computer-line', title: 'Ombor', text: 'Texnika, qo‘shimcha qurilmalar va materiallar hisobi' },
  { icon: 'ri-quill-pen-line', title: 'Hujjatlar', text: 'Dalolatnoma va aktlarni E-IMZO bilan imzolash va kelishish' },
  { icon: 'ri-pie-chart-line', title: 'Hisobot va statistika', text: "Tashkilot, xodim va texnikalar bo'yicha tahlil" },
]

const HELP_URL = 'https://t.me/report_yatm_bot'

interface AuthConfig {
  sso_enabled: boolean
  /** .env SSO_REQUIRED=0 — login/parol bilan kirish ochiq */
  password_login: boolean
}

/** ?next= (Django @login_required qo'shadi, sso_views.login_page uzatadi) — faqat shu saytning ichki yo'li */
function nextPath(): string | null {
  const next = new URLSearchParams(window.location.search).get('next')
  return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\') ? next : null
}

function PasswordForm() {
  const t = useT()
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const login = useMutation({
    mutationFn: () => api('/spa/auth/login/', { method: 'POST', body: JSON.stringify({ username: username.trim(), password }) }),
    onSuccess: () => {
      const next = nextPath()
      // Eski sahifadan kelingan bo'lsa — o'sha sahifaga qaytamiz, aks holda shu yerda interfeys ochiladi
      if (next) window.location.assign(next)
      else qc.invalidateQueries({ queryKey: ['me'] })
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (username.trim() && password) login.mutate()
  }

  return (
    <form className="ivs-auth-fields" onSubmit={submit} noValidate>
      {login.isError && (
        <div className="ivs-auth-alert is-error" role="alert">
          <Icon name="ri-error-warning-fill" size={20} />
          <p className="type-para-sm">{login.error.message}</p>
        </div>
      )}
      <TextInput label={t('Login')} name="username" autoComplete="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
      <TextInput label={t('Parol')} name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <Button size="xl" type="submit" icon="ri-login-box-line" style={{ width: '100%' }} loading={login.isPending} disabled={!username.trim() || !password}>
        {t('Kirish')}
      </Button>
    </form>
  )
}

/** Kirish sahifasi: chapda kirish (SSO yoki vaqtincha login/parol), katta ekranda o'ngda platforma haqida panel. */
export default function LoginPage() {
  const t = useT()
  const { lang, setLang } = useLang()
  const config = useQuery({
    queryKey: ['auth', 'config'],
    queryFn: () => api<AuthConfig>('/spa/auth/config/'),
    staleTime: Infinity,
  })
  const passwordLogin = !!config.data?.password_login
  const ssoOn = !!config.data?.sso_enabled

  const ssoButton = (variant: 'primary' | 'stroke') => (
    <Button
      size="xl"
      variant={variant}
      icon="ri-shield-keyhole-line"
      style={{ width: '100%' }}
      disabled={!ssoOn}
      onClick={() => window.location.assign(SSO_LOGIN_URL)}
    >
      {t('SSO orqali kirish')}
    </Button>
  )

  return (
    <div className="ivs-auth">
      <main className="ivs-auth-main">
        <header className="ivs-auth-top">
          <div className="ivs-auth-brand">
            <span className="ivs-auth-brand-logo">
              <Icon name="ri-server-fill" size={20} />
            </span>
            <span className="type-label-md">IVS</span>
          </div>
          <div className="ivs-auth-tools">
            <SegmentedControl
              aria-label={t('Til')}
              items={LANGS.map((l) => ({ value: l.value, label: l.short }))}
              value={lang}
              onChange={(v) => setLang(v as Lang)}
            />
            <a className="ivs-auth-help type-para-sm" href={HELP_URL} target="_blank" rel="noopener noreferrer">
              {t('Yordam kerakmi?')} <span>{t('Telegram bot')}</span>
            </a>
          </div>
        </header>

        <section className="ivs-auth-form" aria-labelledby="ivs-auth-title">
          <div className="ivs-auth-mark" aria-hidden="true">
            <span className="ivs-auth-mark-inner">
              <Icon name="ri-user-3-line" size={32} />
            </span>
          </div>

          <div className="ivs-auth-titles">
            <h1 id="ivs-auth-title" className="type-h5">
              {t('Tizimga kirish')}
            </h1>
            <p className="type-para-md">
              {passwordLogin && !ssoOn
                ? t('Davom etish uchun login va parolingizni kiriting.')
                : t('Davom etish uchun tashkilotingiz hisobi orqali kiring.')}
            </p>
          </div>

          <div className="ivs-auth-divider" role="presentation" />

          <div className="ivs-auth-actions">
            {config.isPending ? (
              <div className="ivs-auth-skeleton" aria-busy="true" />
            ) : passwordLogin ? (
              <>
                {ssoOn && (
                  <>
                    {ssoButton('primary')}
                    <div className="ivs-auth-or type-subhead-2xs">{t('yoki')}</div>
                  </>
                )}
                <PasswordForm />
              </>
            ) : (
              ssoButton('primary')
            )}
          </div>

          {!passwordLogin && !config.isPending && (
            <p className="ivs-auth-note type-para-xs">
              <Icon name="ri-lock-2-line" size={16} />
              {t('Kirish yagona identifikatsiya tizimi (SSO) orqali amalga oshiriladi.')}
            </p>
          )}
        </section>

        <footer className="ivs-auth-foot type-para-xs">
          <span>© {new Date().getFullYear()} IVS</span>
          <span>{t("Texnik va tarmoq xizmatlarini qo'llab-quvvatlash platformasi")}</span>
        </footer>
      </main>

      <aside className="ivs-auth-side" aria-label={t('Platforma imkoniyatlari')}>
        <div className="ivs-auth-rings" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="ivs-auth-side-body">
          <span className="ivs-auth-chip type-label-xs">
            <Icon name="ri-sparkling-2-fill" size={16} />
            {t('Yagona platforma')}
          </span>
          <h2 className="type-h4">{t('Texnik xizmatlar, ombor va hujjatlar — bitta joyda')}</h2>
          <p className="type-para-md">{t('Tashkilotlardagi texnika va tarmoq xizmatlarini boshqarish uchun ish joyi.')}</p>

          <ul className="ivs-auth-features">
            {FEATURES.map((f) => (
              <li key={f.title}>
                <span className="ivs-auth-feature-icon">
                  <Icon name={f.icon} size={20} />
                </span>
                <span>
                  <span className="type-label-sm">{t(f.title)}</span>
                  <span className="type-para-xs">{t(f.text)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}
