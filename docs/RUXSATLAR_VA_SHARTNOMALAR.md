# Shartnoma, kategoriya va ruxsatlar

## 1. Model

```
Group (Uskuna turi)  1 ──< Category (Uskuna kategoriyasi)
Category  >──< Contract        (Contract.categories, related_name="contracts")
Employee  1 ──< Liable         (xodimga bitta qator)
Liable.categorys  >──< Category   -> texnikalarni ko'rish uchun
Liable.contracts  >──< Contract   -> hisobot va Dalolatnoma uchun
```

- `Category.group` - oddiy FK. `Contract.categories` - ko'p-ko'pga (A4 printer bir necha shartnomada bo'la oladi).
- `Liable.categorys` va `Liable.contracts` bir-biriga bog'liq emas: texnika kategoriya bo'yicha,
  Dalolatnoma shartnoma bo'yicha aniqlanadi.

## 2. Nimaga nima bog'liq

| Joy | Qoida |
|---|---|
| Texnikalar (`barn_tex`), kategoriya filtri | Faqat xodimga biriktirilgan kategoriyalar (`Liable.categorys`) |
| Dalolatnoma menyusi/sahifasi | `worker` tashkilot va kamida bitta shartnoma (`Employee.can_make_document`) |
| Hisobot / Dalolatnoma oldindan ko'rish | Xodimning shartnomalari (`Liable.contracts`); har birida shartnomaning kategoriyalaridagi texnikalar |
| Kategoriyasiz shartnoma | Faqat `NO_CATEGORY_USE_ALL_TECHNICS_IDS` dagilar uchun hamma texnika |

## 3. Rol berish (Xodimlar -> Ruxsatlar oynasi)

- **"Texnikalarni ko'rish"** belgilansa "Texnika kategoriyasi" tanlovi yoqiladi; tanlanganlar `Liable.categorys` ga yoziladi (tanlanmasa - hech narsa).
- **"Hisobotlarni ko'rish"** belgilansa "Shartnomalar" tanlovi yoqiladi; tanlanganlar `Liable.contracts` ga yoziladi. Tanlanmasa - hamma shartnoma (Dalolatnoma ishlashi uchun).
- "Hisobotlarni ko'rish" faqat `worker` tashkilot xodimiga beriladi.
- Har saqlashda xodimning `Liable` qatori o'chirilib, qayta yoziladi.

## 4. Ruxsatlar (permissions)

| Guruh | Ruxsat |
|---|---|
| Ariza | `add_order`, `change_order`, `confirm_order` |
| Hujjat (Dalolatnoma) | `add_deed`, `change_deed` |
| Ko'rish doirasi | `all_organization`, `all_region` |
| Texnika | `view_technics` → `add_/change_/delete_technics` |
| Material | `view_material` → `add_/change_/delete_material`, `material_service`, `all_material_employee` |
| Xodimlar | `view_employee` → `add_/change_/delete_employee` |
| Maxsus | `boss_employee`, `shop_employee`, `status_employee`, `permission_employee`, `report_employee` |

- `view_*` olib tashlansa, unga bog'liq ruxsatlar ham olib tashlanadi.
- `SUPER_PERMS` (`all_organization`, `all_region`, `permission_employee`,
  `all_material_employee`) faqat shunday ruxsati bor xodim tomonidan beriladi.
- Tashkilot turiga qarab ko'rinadigan maydonlar (`_visible_perm_fields`):
  `add_order`, `add_deed`/`change_deed`, `all_organization`/`all_region`,
  `report_employee` — faqat `worker` uchun; `confirm_order` — faqat `worker` bo'lmaganlar uchun.

## 5. Dalolatnoma (Document) oqimi

1. `document_get` / `document_post`: `worker` tashkilot xodimi va kamida bitta shartnoma (`can_make_document`) tekshiriladi.
2. Imzolovchi faqat ruxsat etilgan xodimlardan (`department 283` yoki o'z hududidagi `298`).
3. Tashkilot/bo'lim va hudud tanlanadi (hudud tanlash faqat `all_region` bilan).
4. `ajax_document_preview` xodim shartnomalari bo'yicha texnika jadvalini yig'adi
   (`SKIP_CONTRACT_IDS` dagi shartnomalar uchun 2-sahifa yashiriladi).
5. Matn PDFga aylantirilib, kelishuvchilarga (`DeedConsent`) yuboriladi.

## 6. Admin panel

- **Shartnoma**: kategoriyalarni `filter_horizontal` orqali tanlash.
- **Kategoriya**: uskuna turi (group) va shartnomalar ro'yxati ko'rinadi.
- **Liable**: xodim + kategoriyalar + shartnomalar.

## 7. Migratsiya

`0081`-`0088`: `Contract.categories` yaratiladi, eski `Category.contract` ko'chiriladi,
`Liable` xodimga bitta qatorga birlashtirilib, `categorys` va `contracts` (M2M) ga o'tkaziladi.
Eski kategoriya biriktirishlari `categorys` ga saqlanadi. Deploydan keyin: `python manage.py migrate`.
