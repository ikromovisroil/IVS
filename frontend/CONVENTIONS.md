# Yangi interfeys: sahifa yozish qoidalari

Namuna: `src/pages/technics/` (ro'yxat + filtrlar + forma oynasi). Yangi sahifa shunday tuziladi.

## Fayl va marshrut

- Har bir bo'lim faqat o'z papkasida ishlaydi: `src/pages/<bo'lim>/`. Marshrutlar o'sha papkadagi
  `routes.tsx` da (`export const routes: AppRoute[]`), `App.tsx` ularni yig'adi.
- Yo'llar menyudagi (`src/layout/nav.ts`) yo'l bilan boshlanadi: `/orders/...`, `/materials/...`.
  Bo'lim ichidagi sahifalar — `PageTabs` (SegmentedControl) bilan.
- Ilova `/app` ostida ishlaydi (`BASENAME`, `src/routes.ts`). `navigate()` va `<Link>` uni o'zi qo'shadi;
  oddiy `<a href>`, `window.location` yoki serverga yuboriladigan qaytish manzilida — qo'lda (`BASENAME + path`).
- Umumiy fayllarga (`components/`, `layout/`, `lib/`, `api/`, `ds/`, `App.tsx`) tegilmaydi; kerak bo'lsa
  bo'lim papkasida yoziladi va hisobotda aytiladi.

## Dizayn: AlignUI

- Faqat `src/ds` komponentlari (`import { Button, DataTable, Select, Widget } from '../../ds'`),
  turlari `src/ds/alignui.d.ts` da. O'z tugmasi/inputi/jadvalini yozmang.
- Ranglar, bo'shliqlar, radius, soyalar faqat tokenlar orqali (`var(--text-sub-600)`, `var(--stroke-soft-200)`,
  `var(--bg-weak-50)`, `var(--primary-base)`, `var(--state-error-base)` ...; ro'yxat `src/ds/tokens.css`).
  Hex rang yozilmaydi. Matn klasslari: `type-label-md`, `type-para-sm`, `type-para-xs`, `type-h5`, `type-mono-xs`.
- Ikonkalar: RemixIcon nomlari (`ri-add-line`; UI uchun `-line`, holat uchun `-fill`).
- Jadval: `DataTable` + `CellUser` (avatar+ism), holat `StatusChip`, ikki qatorli katak
  `.aui-cell-text > .aui-cell-primary + .aui-cell-secondary`. Sahifalash serverda: `Pagination` alohida.
- Statistika qatori `.aui-stats`, asboblar qatori `.aui-toolbar` (+ `.aui-toolbar-grow`), kartalar `Widget`,
  vidjetlar setkasi `.aui-dgrid`, forma setkasi `.ivs-form-grid` (`.is-wide` — to'liq qator).
- Telefon kengligida (390px) ham ishlashi kerak.

## Umumiy komponentlar

| | |
|---|---|
| `layout/Page` | AppShell + PageHeader: `<Page icon title subtitle actions>` |
| `components/PageTabs` | bo'lim ichidagi tablar (manzilga bog'langan) |
| `components/Modal` | forma oynasi (sarlavha, kontent, pastki tugmalar) |
| `components/ConfirmDialog` | "Haqiqatan ham...?" + ixtiyoriy sabab maydoni |
| `components/SearchInput` | qidiruv (kechiktirilgan) |
| `components/DataState` | xato / bo'sh / yuklanmoqda holatlari |
| `components/toast` | `const toast = useToast(); toast('Saqlandi')` |
| `lib/useUrlFilters` | filtrlar va sahifa manzil satrida |
| `lib/format` | `initials`, `avatarColor`, `formatNumber` |
| `auth/me` | `useMe()`, `can(me, 'main.view_technics')` |
| `api/client` | `api<T>(path, {method, body, query})`, `apiAll`, `ApiError.fieldErrors`, `Page<T>` |

## Ma'lumot

- `@tanstack/react-query`: `useQuery` (kalit — bo'lim nomi bilan boshlanadi: `['orders', ...]`),
  `useMutation` + `invalidateQueries`.
- API: avval mavjud `/api/v1/...` (Swagger: `/swagger/`, kod: `api/`). Yetmasa — o'z bo'limingiz modulida
  (`api/spa/<bo'lim>.py`, `/api/v1/spa/<bo'lim>/...`), ruxsat va mantiq `main/` dagi mavjud funksiyalardan.
  `api/views.py`, `api/urls.py`, `api/serializers.py`, `main/*` o'zgartirilmaydi.
- Eski sahifadagi har bir imkoniyat (tugma, filtr, eksport, holat o'zgarishi, ruxsat sharti) yangisida ham bo'ladi.
- Matnlar o'zbekcha (lotin), eski interfeysdagi atamalar saqlanadi.

## Tarjima (uz / ru)

- `const t = useT()` (`src/i18n`). Kalit — o'zbekcha matnning o'zi: `t('Arizalar')`, o'zgaruvchi bilan `t('Qurilmalar: {n} ta', { n })`.
  Bo'laklarni qo'shib yasamang (`t('Jami') + ': ' + n` emas).
- Ruscha tarjima — bo'lim lug'atida: `src/i18n/ru/<bo'lim>.ts` (kalit kodda yozilganidek, belgi-belgi bir xil).
  Topilmasa o'zbekcha ko'rinadi; dev rejimda konsolga `[i18n] ru tarjimasi yo‘q` yoziladi.
- Bu komponentlar o'z matn propslarini o'zi tarjima qiladi — o'zbekcha bering, `t()` ga o'ramang:
  `Page` (title, subtitle), `PageTabs` (label, tab.label), `Modal` (title, subtitle), `ConfirmDialog` (title, message-satr,
  confirmLabel, reason.label), `EmptyState`/`DataState` (title, description, emptyText...), `SearchInput` (placeholder),
  `useToast()` matni, `DatePicker` (label, placeholder, hint), `FileUpload` (label, hint). Boshqa hamma joyda — `t()`.
- Modul darajasidagi o'zgarmaslar (holat nomlari, tab ro'yxatlari) o'zbekcha qoladi — ko'rsatilgan joyda `t(...)`.
- Tarjima qilinmaydi: serverdan kelgan ma'lumot (ism, tashkilot, ariza turi, kategoriya), kodlar, PDF/hujjat matni
  (dalolatnoma, akt va h.k. shablonlari — rasmiy hujjat o'zbekcha), Excel eksporti.
- Oy/kun nomlari: `useLang()` + `src/i18n/format.ts` (MONTHS, MONTHS_SHORT, WEEKDAYS...).
- Mavzu: `src/theme.ts` (light/dark/system) — ranglar faqat tokenlar orqali bo'lsa tungi rejim o'zi ishlaydi.
