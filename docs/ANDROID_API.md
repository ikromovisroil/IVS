# IMV API — Android ilova uchun qo'llanma

Interaktiv hujjat (Swagger): `https://<server>/swagger/` (saytga kirgan holatda ochiladi). Bu fayl — qoidalar va oqimlar;
aniq maydonlar va javoblar Swagger'da.

Asosiy manzil: **`https://<server>/api/v1/`** (versiyalangan; ilovada shuni ishlating). Eski `https://<server>/api/` ham ishlaydi, lekin
yangi imkoniyatlar faqat `v1` ga kafolatlanadi. Quyidagi misollarda qisqalik uchun `/api/...` yoziladi — ular `/api/v1/...` bilan bir xil. Barcha so'rov/javoblar JSON (fayllar — `multipart/form-data`). Vaqtlar — ISO 8601.

---

## 1. Kirish (SSO) va tokenlar

Ilovada parol yo'q — kirish SSO (`sso.mf.uz`, OAuth 2.0 + PKCE) orqali. Ikki variant bor, ikkalasi ham bir xil JWT beradi.

### A variant — SSO hujjatidagi standart oqim (tavsiya)
Ilova SSO bilan o'zi gaplashadi, **`client-secret` ilovada bo'lmaydi** (u faqat serverda).
**Shart:** ilovaning `redirect_uri` si (masalan deep link) SSO clientida ro'yxatdan o'tkazilgan va serverda `MOBILE_SSO_REDIRECT_URIS`
sozlamasiga qo'shilgan bo'lishi kerak. Aks holda `/api/auth/sso/token/` `503` qaytaradi.

1. `code_verifier` (43–128 belgi) va `code_challenge = BASE64URL(SHA256(code_verifier))` (paddingsiz) yaratiladi.
2. Foydalanuvchi SSO sahifasiga yuboriladi:
   `https://sso.mf.uz/oauth2/login?clientId=<CLIENT_ID>&redirectUri=<REDIRECT_URI>&codeChallenge=<code_challenge>`
   (clientId serverdagi `SSO_CLIENT_ID` bilan bir xil bo'lishi kerak — jamoadan so'rang).
3. Kirgach SSO ilovaning `redirect_uri` iga `code` qaytaradi.
4. `POST /api/auth/sso/token/` `{"code": "...", "code_verifier": "...", "redirect_uri": "<REDIRECT_URI>"}` →
   `{"access", "refresh", "employee"}` (server SSO'dan tokenni o'zi oladi).

### B variant — SSO'da yangi redirect_uri talab qilmaydigan oqim (ishlaydi)
Ilova SSO provayderiga **bevosita bormaydi**: brauzerni (Chrome Custom Tab) serverning mobil kirish manziliga ochadi.
Quyida shu variantning qadamlari:

1. Ilova `code_verifier` yaratadi (tasodifiy, 43–128 belgi: `A-Z a-z 0-9 - . _ ~`) va
   `code_challenge = BASE64URL(SHA256(code_verifier))` (paddingsiz `=` siz, 43 belgi).
2. Custom Tab'da ochadi: `GET /api/auth/mobile/start/?code_challenge=<code_challenge>`. Foydalanuvchi SSO'dan o'tadi.
3. Brauzer ilovaning deep link'iga qaytadi: `ivsapp://auth?code=<code>`
   (kod **2 daqiqa** amal qiladi; sxema nomi `MOBILE_APP_REDIRECT` sozlamasida, kelishilganidan farq qilsa serverda o'zgartiriladi).
   Ilovada shu sxema uchun `intent-filter` bo'lishi kerak.
4. `POST /api/auth/mobile/exchange/` `{"code": "...", "code_verifier": "..."}` →
   `{"access": "...", "refresh": "...", "employee": {...}}`. Kod faqat `code_verifier` egasi uchun ishlaydi. Daqiqasiga 20 ta so'rov.
5. Keyingi so'rovlar: `Authorization: Bearer <access>`. Access **1 soat**.
6. Yangilash: `POST /api/token/refresh/` `{"refresh": "..."}` → `{"access", "refresh"}`.
   **Har safar yangi `refresh` qaytadi, eskisi bekor bo'ladi — yangisini darhol saqlang.** Refresh 30 kun.
   `401` kelsa refresh bilan yangilang; refresh ham yaroqsiz bo'lsa — qaytadan kirish.
7. Chiqish: `POST /api/auth/logout/` `{"refresh": "..."}` (Bearer bilan) → `204`.

Kirish natijalari: tizimda yo'q foydalanuvchi — brauzerda `403` ("Siz tizimda ro'yxatda yo'qsiz"); bloklangan — token berilmaydi.
**Imzolash (Face ID)** hozircha API'da yo'q — alohida integratsiya qilinadi.

## 2. Foydalanuvchi kimligi — `GET /api/me/`

Kirgandan keyin darhol chaqiriladi va ilovaning ekranlari shunga qarab quriladi. Ruxsatlar o'zgarishi mumkin, shuning uchun
ilova ochilganda va tokenni yangilaganda qayta so'rang.

```json
{
  "username": "...", "is_superuser": false,
  "employee": {"id": 1, "full_name": "...", "organization": 2, "organization_name": "...", "rank_name": "...", "...": "..."},
  "organization_type": "client",
  "orders": {
    "can_create": true, "can_create_on_behalf": false, "can_execute": false,
    "can_confirm": false, "can_assign": false,
    "send_goals": [{"id": 5, "name": "Kompyuter ta'miri", "organization": 1}],
    "can_create_material_order": true,
    "material_goals": [{"id": 9, "name": "Material so'rov", "organization": 2}],
    "execute_goals": []
  },
  "permissions": ["main.view_employee", "main.change_order", "..."]
}
```

- `organization_type`: `worker` — **ATM vakili**, `client` — **mijoz**.
- `orders.can_create` — ATM arizasi yubora oladimi; `can_create_on_behalf` — boshqa xodim nomidan (`add_order`);
  `can_execute` — arizalarni qabul qilish/yakunlash (ATM vakili + `change_order`); `can_confirm` — tasdiqlovchi (`confirm_order`);
  `can_assign` — ijrochini tanlash (superuser).
- `send_goals` — ATM arizasi uchun ariza turlari; `material_goals` — mijozning **o'z omborxonasiga** material arizasi turlari
  (ATM xodimida bo'sh); `execute_goals` — bajaruvchi ijro qila oladigan turlar.
- `permissions` — Django ruxsatlari (`app.codename`). Tugma va menyularni shu ro'yxat bilan ko'rsating/yashiring.
  **Ilovadagi yashirish faqat qulaylik** — har bir so'rovda server o'zi tekshiradi va ruxsatsiz amalga `403` qaytaradi.

## 3. Umumiy qoidalar

- **Sahifalash:** barcha ro'yxatlar 20 tadan: `?page=2`, `?page_size=50` (eng ko'pi 100). Javob: `{"count", "next", "previous", "results": [...]}`.
- **Qidiruv va filtr:** `?search=...` va resursga xos filtrlar (Swagger'da ko'rsatilgan).
- **Xatolar:** `400` — tekshiruv xatosi (`{"maydon": ["xabar"]}` yoki `{"detail": "xabar"}`) — xabarni foydalanuvchiga ko'rsating;
  `401` — token yo'q yoki eskirgan (javobda `WWW-Authenticate: Bearer`; refresh bilan yangilang); `403` — ruxsat yo'q; `404` — topilmadi yoki sizga ko'rinmaydi; `405` — bu amal yo'q.
- **Ko'rish doirasi:** server tashkilot, hudud va ishtirokchilik bo'yicha o'zi cheklaydi (boshqalarning ma'lumoti kelmaydi).
- **Fayllar:** rasm (material) — faqat JPG/PNG, 5 MB gacha; hujjat PDF — 10 MB gacha; ilovalar — PDF/Word/Excel, 10 MB gacha, 10 tagacha.
  Server nginx/gateway'da hajm cheklovi bo'lsa `413` kelishi mumkin.
- Ko'rsatiladigan nomlar `*_name`, `*_display` maydonlarida keladi (masalan `status_display`).

### 3.1 API versiyasi, ilova versiyasi va texnik ishlar

- Barcha javoblarda `X-API-Version: 1` sarlavhasi bor. API kelajakda buzuvchi o'zgarish bilan chiqsa `/api/v2/` bo'ladi; `v1` shu vaqtgacha o'zgarmaydi.
- **Ilova ochilganda (kirishdan oldin)** `GET /api/v1/app/config/?platform=android&version=1.0.3` ni chaqiring (token kerak emas):
  ```json
  {"api_version": "v1", "server_time": "...",
   "app": {"platform": "android", "current_version": "1.0.3", "latest_version": "1.4.1", "min_version": "1.2.0",
           "update_available": true, "force_update": true, "update_url": "https://...", "message": "..."},
   "maintenance": {"enabled": false, "message": "..."}}
  ```
  `force_update: true` — ilova ishlashni to'xtatib, `update_url` ga yo'naltirishi kerak; `update_available` — yangilash tavsiya etiladi (yopish mumkin).
- Har so'rovga `X-App-Version: 1.0.3` sarlavhasini qo'shing. Versiya `min_version` dan eski bo'lsa server **426** `{"code": "upgrade_required", "detail", "min_version", "update_url"}` qaytaradi
  (`app/config/` bundan mustasno) — shu javobda ham yangilash ekranini ko'rsating.
- Texnik ishlar paytida barcha so'rovlar **503** `{"code": "maintenance", "detail"}` (+ `Retry-After`) qaytaradi; `app/config/` ishlaydi va `maintenance.enabled` ni ko'rsatadi.

## 4. Ma'lumotnomalar (faqat o'qish)

`organizations`, `regions`, `departments`, `directorates`, `divisions`, `ranks`, `groups`, `contracts`, `categories`, `structure-categories`,
`units`, `material-categories`, `goals`. Hammasi nom bo'yicha tartiblangan va sahifalangan.

Ruxsat va doira qoidalari (saytdagidek):
- `material-categories` — o'z tashkiloti kategoriyalari (+ umumiylari); `all_organization` bo'lsa hammasi. `contracts` — `permission_employee` kerak.
- `order-goals`, `material-users`, `liables`, `material-employees` — **faqat o'qish** (yozish `405`): saytda ular faqat ruxsatlar oynasida
  (`PUT /api/employees/{id}/permissions/`) o'zgaradi. O'qish uchun `permission_employee` kerak va faqat o'z tashkiloti (`all_organization` — hammasi).
- `material-movements` — faqat o'qish, `view_material` kerak; faqat o'z tashkiloti materiallari bo'yicha, ko'rishga ruxsat etilgan xodimlar (o'zi yoki
  `all_material_employee`) materiallari yoki o'zi ishtirok etgan harakatlar.
- `technics` ro'yxati/ko'rish: xodimga Liable orqali texnika kategoriyalari biriktirilgan bo'lsa, faqat shu kategoriyalar (saytdagidek).
- So'rovlar chegarasi: foydalanuvchi uchun 1200 so'rov/daqiqa; `/api/v1/token/` (login) — 30 urinish/daqiqa. Oshsa `429` + `Retry-After` — kutib, qayta urining.

Ketma-ket tanlash: `departments?organization=X&region=Y` → `directorates?department=Z` → `divisions?directorate=W`.
Ko'rinish tashkilot va hududga bog'liq (`all_organization`/`all_region` huquqi bo'lmasa — faqat o'zinikilar).

## 5. Xodimlar — `/api/employees/`

Ruxsatlar: ko'rish `view_employee`, qo'shish `add_employee`, tahrirlash `change_employee`, o'chirish `delete_employee`.
Faqat o'z tashkiloti (`all_organization` bo'lsa hammasi).

- Filtr: `organization`, `department`, `directorate`, `division`, `region`, `rank`; qidiruv: F.I.O yoki PINFL.
- **Qo'shish** `POST`: `first_name`, `last_name`, `organization` majburiy; `pinfl` (ixtiyoriy, takrorlanmaydi), `father_name`, `department`,
  `directorate`, `division`, `rank`, `phone`. `User` serverda yaratiladi (kirish SSO orqali, parol kerak emas). Javobda `id`, `username`.
  Bo'lim/boshqarma/bo'linma zanjiri va tashkilotga mosligi tekshiriladi.
- **Tahrirlash** `PATCH`: `first_name`, `last_name`, `father_name`, `pinfl` (14 xonali, takrorlanmaydi), `department`, `directorate`, `division`, `rank`, `phone`.
  Tashkilot o'zgarmaydi. Joylashuv o'zgarsa xodimdagi texnikalar uchun `technics_action`: `release` (standart — bo'shatiladi),
  `with` (birga ko'chadi), `stay` (eski joyda qoladi).
- **O'chirish** `DELETE` → `204`; o'zini o'chirib bo'lmaydi (400); hisob faolsizlantiriladi.

### 5.1 Xodimga ruxsat (rol) berish — `/api/employees/{id}/permissions/`

Saytdagi "ruxsatlar" oynasi. Ko'rish uchun `permission_employee`, o'zgartirish uchun qo'shimcha `change_employee` kerak.
Faqat o'z tashkiloti xodimi (`all_organization` bo'lsa — hammasi).

- `GET /api/permissions/catalog/` — ruxsatlar guruhlari (`title`, `items: [{key, label}]`), bog'liqliklar (`dependent`) va SUPER ruxsatlar.
- `GET /api/employees/{id}/permissions/` — joriy holat:
  - `permissions[]`: `key`, `label`, `group`, `granted` (xodimga **bevosita** berilgan — o'zgartiriladigan), `effective` (guruh orqali ham hisobda),
    **`editable`** (siz bu xodimga bu ruxsatni bera/ola olasizmi). `editable=false` bo'lgan katakchani o'chirib/yashirib qo'ying.
  - `goals`, `categories`, `contracts`, `material_categories`: `enabled` (tegishli ruxsat yoqilganmi), `options` (tanlash variantlari), `selected`.
- `PUT /api/employees/{id}/permissions/`:
  ```json
  {"permissions": {"change_order": true, "view_technics": true, "add_technics": false},
   "goals": [3, 5], "categories": [2], "contracts": [1], "material_categories": [4]}
  ```
  **Faqat yuborilgan kalitlar o'zgaradi.** Javob — yangilangan holat + `ignored` (qo'llanmagan kalitlar).

Qoidalar (saytdagidek):
- Nishon xodim tashkilotiga va sizning tashkilotingiz turiga qarab ayrim ruxsatlar yo'q: masalan `add_order`, `add_deed`, `change_deed`, `all_organization`, `all_region`,
  `report_employee` — faqat **worker** nishonga; `confirm_order` — worker bo'lmagan nishonga; `boss_employee`, `shop_employee`, `status_employee`, `permission_employee` —
  faqat siz worker tashkilot xodimi bo'lsangiz. Bunday kalitlar `ignored` ga tushadi.
- **SUPER ruxsatlarni** (`all_organization`, `all_region`, `permission_employee`, `all_material_employee`) faqat o'zingizda bor bo'lsa bera olasiz (aks holda `ignored`).
- "Ko'rish" o'chirilsa unga bog'liqlar ham o'chadi: `view_technics` → qo'shish/tahrirlash/o'chirish; `view_material` → qo'shish, tahrirlash, o'chirish, sarflash, `all_material_employee`;
  `view_employee` → qo'shish, tahrirlash, o'chirish.
- `goals` — faqat `change_order` yoqilgan bo'lsa; `categories` (texnika kategoriyalari) — `view_technics`; `contracts` — `report_employee` (bo'sh bo'lsa hammasi);
  `material_categories` — faqat worker bo'lmagan nishon uchun, nishon tashkilotining kategoriyalari. Mos ruxsat o'chirilsa tanlovlar tozalanadi.
- Xato: noma'lum kalit, `true/false` bo'lmagan qiymat yoki variantlarda yo'q ID — `400`. Boshqa tashkilot xodimi (huquqsiz) — `404`.
- O'zgartirish audit jurnaliga yoziladi.

### 5.2 Statistika — xodimlar (arizalar) — `/api/stats/employees/`

`status_employee` huquqi kerak. `GET /api/stats/employees/?region=&date1=&date2=` — o'z tashkiloti ariza turlari bo'yicha bajaruvchi xodimlarning arizalari
(`date1`/`date2` — arizaning yaratilgan sanasi, `YYYY-MM-DD`). Hech qanday filtr berilmasa joriy oy; biror filtr berilsa faqat u qo'llanadi.
Javob: `period`, `employees[]` (`receiver_id`, `full_name`, `process_count` jarayonda, `finished_count` bajarildi, `approved_count` tasdiqlandi,
`rejected_count` rad etilgan va bekor qilingan, `total_count`, `avg_rating`) — jami bo'yicha kamayish tartibida, va `goals[]` (ariza turi bo'yicha jami).

## 6. Texnika — `/api/technics/`

Ruxsatlar: ko'rish `view_technics`, qo'shish `add_technics`, tahrirlash va biriktirish `change_technics`, o'chirish `delete_technics`.
Doira: tashkilot va hudud (`all_organization`/`all_region`).

- Filtr: `group`, `category`, `region`, `organization`, `department`, `directorate`, `division`, `employee`, `status`; qidiruv: nom, inventar, seriya, MAC, IP.
- `status`: `free` (bo'sh), `active`, `repair`, `defect`. Javobda biriktirilgan qo'shimcha qurilmalar — `extra_devices`.
- **Qo'shish**: `group`, `category`, `organization`, `name` majburiy; `parametr`, `inventory`, `serial`, `mac`, `ip`, `year`, `price`, `address`, `is_online`.
  Hudud xodimdan olinadi. Bir tashkilotda faol seriya takrorlanmaydi (`B/N` bundan mustasno). `all_organization` yo'q bo'lsa — faqat o'z tashkiloti.
- **Tahrirlash** `PATCH`: guruh va hudud o'zgarmaydi; `status` o'zgaradi.
- **Biriktirish** `POST /{id}/assign/`: `{"employee": id}` — xodimga (bo'lim/boshqarma/bo'linma xodimdan olinadi, holat `active`);
  yoki `{"department": id, "directorate": id, "division": id}` — strukturaga (butun zanjirni yuboring); `{}` — bo'shatiladi.
  **Bo'shatish** — `POST /{id}/unassign/`. `GET /{id}/qr/` — QR rasm (PNG).
- **O'chirish** — `DELETE` (texnika arxivlanadi, ro'yxatda ko'rinmaydi).

### 6.1 Statistika — texnika — `/api/stats/technics/`

`status_employee` huquqi kerak. O'z tashkilotining faol texnikalari guruh va kategoriya bo'yicha: `total`, `groups[]` (`technics_count`, `percent`, `categories[]` —
`count`, `percent`), diagramma uchun `pie` (barcha guruhlar) va `bar` (eng ko'p 8 guruh) — `labels` va `values` ro'yxatlari.

## 7. Qo'shimcha qurilmalar — `/api/structures/`

Ruxsatlar **texnika huquqlari** bilan: ko'rish va tahrirlash `change_technics`, qo'shish `add_technics`, o'chirish `delete_technics`.
`category`, `organization`, `name` majburiy; seriya tashkilot ichida takrorlanmaydi. Texnikaga biriktirish: `POST /{id}/assign/ {"technics": id}`
(texnika sizning doirangizda, bir tashkilotdan va qurilma bo'sh bo'lishi kerak); ajratish: `POST /{id}/unassign/` (`{"technics": id}` ixtiyoriy).

## 8. Materiallar — `/api/materials/`

Ruxsatlar: ko'rish `view_material`, qo'shish `add_material`, tahrirlash `change_material`, o'chirish `delete_material`,
xodimga berish (`give`) `change_material`, sarflash (`service`) `material_service`.

- **Ko'rinish:** o'z tashkilotining faol, soni 0 dan ko'p materiallari — `all_material_employee` bo'lsa moddiy javobgar xodimlarniki,
  aks holda o'zi va unga biriktirilgan xodimlarniki.
- **Qo'shish/tahrirlash** (rasm bilan `multipart`): `name` majburiy; `category`, `unit`, `number`, `code`, `price` (>=0), `year`, `image` (JPG/PNG, 5 MB).
  Kategoriya o'z tashkilotiniki bo'lishi kerak. Tahrirlashda o'zgarishlar harakat jurnaliga yoziladi.
- `POST /give/` `{"employee_id": id, "items": [{"material_id", "number"}]}` — materialni xodimga berish (bir tranzaksiya).
- `POST /service/` `{"material_id", "give_number", "body"}` — sarflash (egasi, unga biriktirilgan xodim yoki `all_material_employee`).
- `DELETE` — arxivlanadi (jurnalga yoziladi).

### 8.1 Material kirim-chiqim hisoboti (tarix) — `/api/materials/report/`

Saytdagi "Material hisoboti" (`mat_info`). `view_material` kerak.
- `GET /api/materials/report/employees/` — hisobotda tanlash mumkin xodimlar (oddiy xodim — faqat o'zi; `all_material_employee` — tashkilotdagi moddiy javobgarlar).
- `GET /api/materials/report/?employee=<id>&date1=2026-10-01&date2=2026-10-31&name=` — `employee` majburiy; sana berilmasa joriy oy; 20 tadan sahifalanadi.
  Har bir material: `initial_balance` (davr boshidagi qoldiq), `income` va `income_sum` (kirim), `outcome` va `outcome_sum` (chiqim),
  `current_balance` va `current_sum` (joriy), `price`, `unit`, `category` va `movements` (harakatlar tarixi: `date`, `user`, `employee`, `income`, `outcome`, `status`, `body`).
  Tanlanmagan xodimning hisobotini ko'rishga ruxsat bo'lmasa `403` (saytda faqat eksport shuni tekshirardi, API'da ro'yxat ham tekshiriladi).

### 8.2 Excel (.xlsx) eksport — `/api/export/...`

Fayl sifatida yuklab olinadi (`Content-Disposition: attachment`); `Bearer` token bilan so'raladi.
| Yo'l | Huquq | Filtrlar |
|---|---|---|
| `GET /api/export/employees.xlsx` | `view_employee` | `organization` (majburiy), `region`, `department`, `directorate`, `division`, `name` |
| `GET /api/export/technics.xlsx` | `view_technics` | texnika ro'yxatidagi filtrlar (`group`, `category`, `status`, `employee`, `search`, ...) |
| `GET /api/export/materials.xlsx` | `view_material` | material ro'yxatidagi filtrlar (`employee`, `category`, `unit`, `search`) |
| `GET /api/export/material-report.xlsx` | `view_material` | `employee`, `date1`, `date2` (majburiy), `name` — "Umumiy" va "Harakatlar" varaqlari |

Texnika va materiallar eksporti **API ro'yxatlaridagi ko'rish doirasi** (tashkilot/hudud/xodim) bilan beriladi.

## 9. Hujjatlar — `/api/deeds/`

Hujjatni **ishtirokchilar** ko'radi (yaratuvchi, imzolovchi `sender`, qabul qiluvchi `receiver`, kelishuvchilar); `all_organization` hammasini.
`status` (turi): `document`, `svod`, `reestr`, `act`, `petition`, `service`. Imzo holatlari: `viewed` (kutilmoqda), `approved`, `rejected`.
Hujjat **o'chirilmaydi**.

**Ro'yxat:** `?role=` — `created` (yuborganlarim, faol), `created_archive`, `to_sign` (menga kelgan imzo), `signed` (imzolaganlarim/rad etganlarim),
`to_agree` (kelishuvim kutilayotgan), `agreed` (kelishganlarim). Berilmasa — o'zim ishtirok etganlar. Filtr: `organization`, `sender`, `receiver`, `user`, `status`.

Javobdagi tayyor bayroqlar (interfeys uchun): `can_edit`, `can_reject`, `can_manage_consents`, `can_add_consents`, `my_consent_id`
(kelishuvim kutilayotgan bo'lsa — kelishuv yozuvi `id`si).

- **Yaratish** `POST` (`multipart`; `add_deed` kerak): `status`, `organization`, `sender` majburiy; `file` (PDF) **yoki** `body` (matn — PDF serverda yaratiladi);
  `receiver` faqat `status=document` uchun va faqat "worker" tashkilot xodimi; `attachments` (10 tagacha), `agreements` (kelishuvchi xodimlar ID ro'yxati).
  Yaratuvchi — doim so'rov egasi.
- **Tahrirlash** `PATCH` (`sender`, `receiver`, `body`, `agreements`): faqat yaratuvchi, `user_edit` yoqilgan va hali hech kim javob bermagan paytda; PDF qayta yaratiladi.
- **Rad etish** `POST /{id}/reject/ {"message"}` — imzolovchi/qabul qiluvchi. (Tasdiqlash/imzolash — keyingi bosqich, Face ID.)
- **Kelishuvchilar:** `POST /{id}/consents/ {"employees": [id]}` qo'shish; `GET /{id}/consent-candidates/?search=` nomzodlar;
  `DELETE /api/deed-consents/{id}/` olib tashlash (faqat yaratuvchi, faqat javob bermaganini); kelishuvchi javobi:
  `POST /api/deed-consents/{id}/approve/` yoki `/reject/` (rad etishda `message` majburiy).
  `POST /{id}/signer-consent/{sender|receiver}/ {"enabled": true}` — imzolovchi ham kelishuvchi qo'sha olsinmi (faqat yaratuvchi).
  Hujjat rad etilgan yoki to'liq imzolangan bo'lsa kelishuvchilarni o'zgartirib bo'lmaydi.
- `POST /{id}/toggle-user-edit/` — yaratuvchiga tahrirlash ruxsatini almashtirish (`change_deed`).
- `GET /{id}/attachments/download/` — ilovalar (bitta fayl yoki ZIP).

### 9.1 Hujjatlar reyestri — `/api/deed-registry/`

Saytdagi "Hujjatlar" (`files`) sahifasi: **filtr bilan hamma hujjat** (kirgan har bir xodim ko'ra oladi; ishtirokchi bo'lish shart emas). Faqat o'qish.
- `GET /api/deed-registry/` — **kamida bitta filtr shart** (aks holda 400): `name` (hujjat kodi, ishtirokchining F.I.O si yoki ariza raqami), `organization`,
  `region` (yaratuvchi hududi), `status` (hujjat turi), `date1`, `date2` (`YYYY-MM-DD`, yaratilgan sana).
- `GET /api/deed-registry/{id}/` — bitta hujjat; `GET /api/deed-registry/{id}/attachments/download/` — ilovalar (fayl yoki ZIP).
- Hujjat matni (`body`) va amal bayroqlari (`can_*`) berilmaydi; imzo/kelishuvchi holatlari va PDF (`file`) beriladi.

## 10. Arizalar — `/api/orders/`

Ikki xil ariza. Qaysi biri ekani **ariza turi (`goal`) tashkilotining turiga** bog'liq.

### 10.1 ATM (texnik xizmat) arizasi — mijoz yuboradi, ATM vakili bajaradi
Holatlar: `viewed` (yangi) → `process` (jarayonda) → `finished` (bajarildi) → `accepted` (qabul qilindi, baho bilan) yoki `canceled`.

**Yuboruvchi (har qanday xodim):**
- `POST /api/orders/` `{"goal": <send_goals dan>, "message_sender": "..."}`. **Materiallarni yuborib bo'lmaydi** — ularni bajaruvchi biriktiradi.
  `add_order` huquqi bilan `{"sender": <xodim id>}` — boshqa xodim nomidan.
- Ro'yxatlar: `?role=sender` (yangi/jarayonda/bajarilgan), `?role=sender_archive`, `?role=sender_user` (nomidan yuborganlarim).
- Baho bilan qabul: `POST /{id}/decide/ {"action": "accepted", "rating": 1..5}` (faqat bajarilgan ariza). Bekor: `{"action": "canceled"}`.

**Bajaruvchi (ATM vakili, `change_order`; mijoz tashkiloti xodimi bajara olmaydi):**
- `?role=receiver_new` — o'z hududi va o'ziga ruxsat etilgan turlar (`execute_goals`) bo'yicha yangi arizalar; `?role=receiver_active` — qabul qilganlari;
  `?role=receiver_archive` — arxiv.
- Qabul qilish: `POST /{id}/accept/` (superuser `{"receiver": id}` bilan ijrochini tanlaydi; nomzodlar: `GET /{id}/assignees/`).
- Yakunlash: `GET /available-materials/?search=` (unga biriktirilgan xodimlarning materiallari) dan tanlab,
  `POST /{id}/finish/ {"technics_id": id?, "materials": [{"material_id", "number"}]}` — materiallar ombordan ayriladi.
  Faqat arizani qabul qilgan xodim.

### 10.2 Material arizasi (omborxonaga) — mijoz o'z tashkiloti omborxonasiga yuboradi
Ilova **savatni o'zi (qurilmada)** saqlaydi va bitta so'rovda yuboradi:
1. `GET /api/orders/selectable-materials/?search=` — o'z tashkilotining faol materiallari, faqat unga ruxsat etilgan kategoriyalar bo'yicha.
2. `POST /api/orders/` `{"goal": <material_goals dan>, "message_sender": "...", "materials": [{"material_id", "number"}]}`.
   Savat bo'sh bo'lmasligi, material takrorlanmasligi, soni >=1, ariza turi — **o'z tashkilotingiz omborxonasi** bo'lishi shart. ATM xodimi yubora olmaydi.
   Ombordan hali ayirilmaydi.
**Omborxona tomoni** (ariza turi shu tashkilotniki). Holatlar: `viewed` → `process` (omborxonachi qabul qildi) yoki `rejected`;
`process` → `finished` (materiallar berildi) → `approved` (tasdiqlovchi) yoki `rejected` (materiallar omborga qaytadi) → `accepted` (yuboruvchi, akt yaratiladi);
yuboruvchi `viewed/process/finished` da `canceled` qila oladi.

- **Yuboruvchi** (mijoz): `?role=barn_sender` (faol), `?role=barn_sender_archive`. `POST /{id}/decide/ {"action": "accepted"}` — faqat tasdiqlangan (`approved`) arizani;
  qabul qilinganda **akt (hujjat) avtomatik yaratiladi** (arizadagi `deeds` maydonida), xato bo'lsa javobda `warning` keladi. `{"action": "canceled"}` — bekor qilish.
- **Omborxonachi** (`change_order`, ATM emas): `?role=barn_receiver_new` — o'z tashkiloti, hududi va ruxsat etilgan turlar bo'yicha yangi arizalar;
  `?role=barn_receiver_active`, `?role=barn_receiver_archive`.
  - Qabul: `POST /{id}/accept/` (→ `process`); rad etish: `POST /{id}/reject/` (→ `rejected`).
  - Materiallarni berish: `POST /{id}/finish/ {"items": [{"ordermaterial_id": id, "given": n}], "date": "2026-10-10T09:30"}`
    (`ordermaterial_id` — arizadagi `materials[].id`; `given` >= 1, ombordan ayriladi; qayta chaqirilsa farq hisoblanadi; `date` — olib ketish vaqti, ixtiyoriy).
- **Tasdiqlovchi** (`confirm_order`): `?role=barn_agrement` (bajarilgan, tasdiqlash kutayotganlar — o'z tashkiloti va hududi), `?role=barn_agrement_archive`.
  `POST /{id}/confirm/ {"action": "approved", "items": [{"ordermaterial_id", "given"}]}` (sonlarni tuzatish mumkin, 0 ham mumkin) yoki `{"action": "rejected"}` —
  berilgan materiallar omborga qaytariladi.
- Arizadagi materiallar alohida tahrirlanmaydi: `GET /api/order-materials/` faqat ko'rish uchun.

### 10.3 Belgilar
`GET /api/orders/badges/` → `{"notifications": n, "receiver_pending": m}` (saytdagi qizil raqamlar); `POST /api/orders/mark-seen/` — belgilarni o'chirish.

## 11. Chat — `/api/chat/...` va WebSocket

Saytdagi chat bilan bir xil: shaxsiy suhbat, guruh, "AI yordamchi", "Saqlangan xabarlar". Barcha so'rovlar `Bearer` token bilan.
Xatolar `{"detail": "..."}` ko'rinishida. Xabar yuborish va tahrirlash **HTTP orqali** bo'ladi; WebSocket faqat serverdan jonli hodisalar uchun.

### 11.1 REST
| Metod va yo'l | Vazifasi |
|---|---|
| `GET /api/chat/conversations/` | Suhbatlar: `id`, `kind` (`direct`, `group`, `ai`, `saved`), `title`, `last_message`, `last_message_at`, `unread_count`, `online`, `last_seen`, guruhda `member_count`, `is_admin` |
| `GET /api/chat/contacts/?q=` | Yangi suhbat uchun xodimlar (o'z tashkiloti, `all_organization` bo'lsa hammasi; 50 tagacha) |
| `POST /api/chat/open/` `{"target": <xodim id> \| "ai" \| "saved"}` | Suhbat ochish/topish → `{"conversation_id"}` |
| `POST /api/chat/groups/` `{"name", "members": [id,...]}` | Guruh yaratish (o'zingizdan tashqari kamida 2 a'zo; faqat o'z tashkilotingiz xodimlari) |
| `GET /api/chat/conversations/{id}/messages/?page=1` | Xabarlar, 30 tadan. `page=1` — eng yangilari; sahifa ichida eskidan yangiga. `has_next_page` — yana eskilari bor. Ochilganda o'qilmaganlar "o'qildi" bo'ladi |
| `POST /api/chat/conversations/{id}/send/` `{"body": "..."}` yoki `multipart` (`body`, `attachment`) | Xabar yuborish → `{"message": {...}}`. Matn 4000 belgigacha; fayl: jpg/png, pdf, word, excel, 15 MB gacha |
| `POST /api/chat/messages/{id}/edit/` `{"body"}` | Faqat o'z xabarini tahrirlash |
| `POST /api/chat/messages/{id}/delete/` | Faqat o'z xabarini o'chirish (matn va fayl o'chiriladi) |
| `POST /api/chat/conversations/{id}/hide/` | Suhbatni faqat o'zim uchun yashirish (qarshi tomon yozsa qaytadi) |
| `GET /api/chat/conversations/{id}/members/` | Guruh a'zolari: `is_admin`, `is_creator`, `is_me`; `am_admin`, `am_creator` |
| `POST /api/chat/conversations/{id}/members/add/` `{"members": [id]}` | A'zo qo'shish (guruh admini) |
| `POST /api/chat/conversations/{id}/members/{member_id}/remove/` | Chiqarish: o'zi chiqishi mumkin; admin faqat oddiy a'zoni; yaratuvchi adminlarni ham; yaratuvchini hech kim |
| `POST /api/chat/conversations/{id}/members/{member_id}/admin/` `{"is_admin": true}` | Admin tayinlash/olish (faqat yaratuvchi) |
| `GET /api/chat/unread-count/` | `{"unread_count": n}` — barcha suhbatlar bo'yicha o'qilmagan xabarlar |
| `POST /api/chat/ping/` | "Onlayn" holatini yangilash (`204`); WebSocket ulanmagan paytda har ~30 soniyada |

Xabar ko'rinishi: `{"id", "conversation_id", "sender_id", "sender_name", "is_ai", "body", "attachment_url" (to'liq URL yoki null), "attachment_name", "is_image", "is_edited", "is_deleted", "read_at", "date_creat"}`.
Suhbatda ishtirok etmasangiz — `403`.

### 11.2 WebSocket (jonli hodisalar)
`wss://<server>/ws/chat/?token=<access>` — `access` token so'rov parametrida beriladi.
- Token yaroqsiz yoki eskirgan bo'lsa ulanish **4401** kodi bilan yopiladi: tokenni yangilab (`/api/token/refresh/`) qayta ulaning.
  Access 1 soatda tugagani uchun uzoq ulanishda ham shunday qiling.
- Ulangach "onlayn" holati yangilanadi; ulanishni tirik tutish va onlaynni yangilash uchun har ~30 soniyada `{"type": "ping"}` yuboring.
- Serverdan keladigan hodisalar (JSON):
  - `{"type": "message", "message": {...}}` — yangi xabar (o'zingiz yuborganingiz ham keladi);
  - `{"type": "edit", "message": {...}}` — tahrirlandi; `{"type": "delete", "message": {...}}` — o'chirildi;
  - `{"type": "read", "conversation_id", "reader_id", "message_ids": [...]}` — xabarlar o'qildi (✓✓);
  - `{"type": "group_update", "conversation_id"}` — guruh a'zolari/adminlari o'zgardi (suhbatlar ro'yxatini/a'zolarni qayta so'rang).
- Ulanish uzilsa, qayta ulangach `GET /conversations/` va ochiq suhbat xabarlarini qayta so'rab, o'tkazib yuborilganini oling.
- **Server tomonida:** WebSocket uchun ASGI server (daphne/uvicorn) kerak; faqat `gunicorn config.wsgi` bo'lsa WebSocket ishlamaydi (REST ishlayveradi).
- Ilova yopiq paytda yangi xabar haqida bildirishnoma — FCM orqali (12-bo'lim).

## 12. Push-xabarlar (FCM)

Server yangi ariza, ariza holati o'zgarishi, hujjat imzo/kelishuv kutayotgani va yangi chat xabari haqida xodimning
barcha Android qurilmalariga FCM orqali bildirishnoma yuboradi (saytdagi web-push va Telegram bilan bir xil hodisalar).

**Ilova tomonida:**
1. Bildirishnoma kanalini yarating: ID **`ivs_default`** (server shu kanalga yuboradi).
2. Kirgandan keyin FCM tokenni oling va yuboring: `POST /api/devices/ {"token": "<FCM token>", "device_name": "Pixel 7", "app_version": "1.0.3"}`
   (`201` yangi, `200` yangilandi). FCM token yangilanganda (`onNewToken`) yana yuboring. Qurilma boshqa xodimga o'tsa, token yangi xodimga ko'chiriladi.
3. Chiqishda: `POST /api/auth/logout/ {"refresh": "...", "fcm_token": "<FCM token>"}` — shu qurilmaga bildirishnoma kelmaydi.
   (Faqat tokenni o'chirish kerak bo'lsa: `POST /api/devices/unregister/ {"token": "..."}`.)
4. Ilova fonda yoki yopiq bo'lsa bildirishnomani tizim ko'rsatadi; ochiq bo'lsa `onMessageReceived` da o'zingiz ko'rsating.

**Xabar tarkibi:** `notification` (`title`, `body`) va navigatsiya uchun `data` (barcha qiymatlar satr):

| `data.type` | Qachon | Qo'shimcha maydon | Ochiladigan ekran |
|---|---|---|---|
| `order_new` | Bajaruvchiga yangi ariza keldi | `order_id` | Yangi arizalar (`?role=receiver_new` / `barn_receiver_new`) |
| `order_status` | Yuboruvchining arizasi holati o'zgardi | `order_id`, `status` | Ariza tafsiloti |
| `order_assign` | Sizga ariza biriktirildi | `order_id` | Faol arizalar |
| `deed_sign` | Hujjat imzolashga yuborildi | `deed_id` | Hujjat (`?role=to_sign`) |
| `deed_agree` | Hujjat kelishishga yuborildi | `deed_id` | Hujjat (`?role=to_agree`) |
| `chat` | Yangi chat xabari | `conversation_id` | Suhbat |
| `general` | Boshqa | — | — |

`data.url` — saytdagi manzil (ma'lumot uchun), `data.tag` — hodisaning unikal belgisi (bir xil `tag` bildirishnomani almashtiradi).
Bildirishnoma kelganda ma'lumotni `GET /api/orders/{id}/`, `/api/deeds/{id}/`, `/api/chat/conversations/` orqali yangilang.

**Server tomonida (administrator):** `.env` ga `FIREBASE_CREDENTIALS_FILE=/yo'l/firebase-service-account.json` (Firebase Console →
Project settings → Service accounts → Generate new private key), ixtiyoriy `FIREBASE_PROJECT_ID`; `pip install google-auth`;
`python manage.py migrate`; Celery worker'ni qayta ishga tushirish. Sozlanmasa FCM o'chiq turadi (xato bermaydi).

## 13. Hozircha API'da YO'Q narsalar

- Hujjatni **imzolash/tasdiqlash** (Face ID) — alohida integratsiya.
- Akt/Svod/Reestr/Talabnoma maxsus oqimlari (materiallarni avtomatik aniqlash). (Material arizasi qabul qilinganda akt avtomatik yaratiladi.)

---

## 14. Barcha endpointlar (Swagger'dan avtomatik)

| Metod | Yo'l | Tavsif |
|---|---|---|
| `GET` | `/api/v1/app/config/` | Ilova versiyasini tekshirish: majburiy yangilash, yangilanish mavjudligi, texnik ishlar holati. |
| `POST` | `/api/v1/auth/logout/` | POST /api/auth/logout/ {refresh, fcm_token?} — refresh tokenni bekor qiladi (va shu qurilmaning push tokenini o'chiradi). |
| `POST` | `/api/v1/auth/mobile/exchange/` | POST /api/auth/mobile/exchange/ {code, code_verifier} -> {access, refresh, employee} |
| `POST` | `/api/v1/auth/sso/token/` | SSO hujjatidagi standart oqim: ilova foydalanuvchini SSO sahifasiga (sso.mf.uz/oauth2/login) o'zi yo'naltiradi |
| `GET` | `/api/v1/categories/` | Categories list |
| `GET` | `/api/v1/categories/{id}/` | Categories read |
| `GET` | `/api/v1/chat/contacts/` | GET /api/chat/contacts/?q= — yangi suhbat uchun xodimlar (all_organization bo'lmasa faqat o'z tashkiloti, 50 tagacha). |
| `GET` | `/api/v1/chat/conversations/` | GET /api/chat/conversations/ — suhbatlar ro'yxati (oxirgi xabar, o'qilmaganlar soni, onlayn holati). |
| `POST` | `/api/v1/chat/conversations/{id}/hide/` | POST /api/chat/conversations/{id}/hide/ — suhbatni faqat o'zim uchun yashirish (qarshi tomon yozsa qaytadi). |
| `GET` | `/api/v1/chat/conversations/{id}/members/` | GET /api/chat/conversations/{id}/members/ — guruh a'zolari (admin/yaratuvchi belgilari bilan). |
| `POST` | `/api/v1/chat/conversations/{id}/members/add/` | POST /api/chat/conversations/{id}/members/add/ {"members": [id]} — faqat guruh admini. |
| `POST` | `/api/v1/chat/conversations/{id}/members/{member_id}/admin/` | POST /api/chat/conversations/{id}/members/{member_id}/admin/ {"is_admin": true/false} — faqat yaratuvchi. |
| `POST` | `/api/v1/chat/conversations/{id}/members/{member_id}/remove/` | POST /api/chat/conversations/{id}/members/{member_id}/remove/ — o'zi chiqishi mumkin; admin faqat oddiy |
| `GET` | `/api/v1/chat/conversations/{id}/messages/` | GET /api/chat/conversations/{id}/messages/?page=1 — xabarlar (30 tadan; page=1 — eng yangilari, |
| `POST` | `/api/v1/chat/conversations/{id}/send/` | POST /api/chat/conversations/{id}/send/ — {"body": "..."} yoki multipart (body, attachment: jpg/png/pdf/word/excel, 15 MB gacha). |
| `POST` | `/api/v1/chat/groups/` | POST /api/chat/groups/ {"name": "...", "members": [id, ...]} (o'zingizdan tashqari kamida 2 ta a'zo). |
| `POST` | `/api/v1/chat/messages/{id}/delete/` | POST /api/chat/messages/{id}/delete/ — faqat o'z xabari (matn va fayl o'chiriladi). |
| `POST` | `/api/v1/chat/messages/{id}/edit/` | POST /api/chat/messages/{id}/edit/ {"body": "..."} — faqat o'z xabari. |
| `POST` | `/api/v1/chat/open/` | POST /api/chat/open/ {"target": "ai" / "saved" / <xodim id>} -> {"conversation_id": id} |
| `POST` | `/api/v1/chat/ping/` | POST /api/chat/ping/ — "onlayn" holatini yangilash (WebSocket ulanmagan paytda; har 30 soniyada). |
| `GET` | `/api/v1/chat/unread-count/` | GET /api/chat/unread-count/ — barcha suhbatlar bo'yicha o'qilmagan xabarlar soni (qizil raqam). |
| `GET` | `/api/v1/contracts/` | Faqat KO'RISH: shartnomalar ro'yxati (saytda faqat ruxsatlar oynasida ko'rinadi). 'permission_employee' kerak. |
| `GET` | `/api/v1/contracts/{id}/` | Faqat KO'RISH: shartnomalar ro'yxati (saytda faqat ruxsatlar oynasida ko'rinadi). 'permission_employee' kerak. |
| `GET` | `/api/v1/deed-consents/` | Deed-consents list |
| `GET` | `/api/v1/deed-consents/{id}/` | Deed-consents read |
| `DELETE` | `/api/v1/deed-consents/{id}/` | Deed-consents delete |
| `POST` | `/api/v1/deed-consents/{id}/approve/` | Deed-consents approve |
| `POST` | `/api/v1/deed-consents/{id}/reject/` | Deed-consents reject |
| `GET` | `/api/v1/deed-files/` | Faqat KO'RISH (saytda ilovalar hujjat yaratilganda qo'shiladi, keyin o'zgarmaydi) — ko'rinadigan hujjatlar bo'yicha. |
| `GET` | `/api/v1/deed-files/{id}/` | Faqat KO'RISH (saytda ilovalar hujjat yaratilganda qo'shiladi, keyin o'zgarmaydi) — ko'rinadigan hujjatlar bo'yicha. |
| `GET` | `/api/v1/deed-registry/` | Deed-registry list |
| `GET` | `/api/v1/deed-registry/{id}/` | Deed-registry read |
| `GET` | `/api/v1/deed-registry/{id}/attachments/download/` | Deed-registry attachments attachments download |
| `GET` | `/api/v1/deeds/` | Deeds list |
| `POST` | `/api/v1/deeds/` | Deeds create |
| `GET` | `/api/v1/deeds/{id}/` | Deeds read |
| `PUT` | `/api/v1/deeds/{id}/` | Deeds update |
| `PATCH` | `/api/v1/deeds/{id}/` | Deeds partial update |
| `GET` | `/api/v1/deeds/{id}/attachments/download/` | Ilovalarni yuklab olish: bitta bo'lsa o'zi, bir nechta bo'lsa ZIP (saytdagi deed_attachments). |
| `GET` | `/api/v1/deeds/{id}/consent-candidates/` | Kelishuvchi qo'shish uchun xodimlar (qidiruv: ?search=, 20 tadan sahifalanadi). |
| `POST` | `/api/v1/deeds/{id}/consents/` | Kelishuvchi(lar) qo'shish: POST /api/deeds/{id}/consents/ {"employees": [id, ...]} |
| `POST` | `/api/v1/deeds/{id}/generate-pdf/` | PDF qayta yaratish (faqat tahrirlash mumkin bo'lgan paytda, yaratuvchi): POST /api/deeds/{id}/generate-pdf/ |
| `POST` | `/api/v1/deeds/{id}/reject/` | Deeds reject |
| `POST` | `/api/v1/deeds/{id}/signer-consent/{role}/` | Deeds signer consent |
| `POST` | `/api/v1/deeds/{id}/toggle-user-edit/` | Yaratuvchiga tahrirlashga ruxsatni yoqish/o'chirish ('change_deed' kerak). |
| `GET` | `/api/v1/departments/` | Departments list |
| `GET` | `/api/v1/departments/{id}/` | Departments read |
| `POST` | `/api/v1/devices/` | Android ilova kirgandan keyin (va FCM token yangilanganda — onNewToken) chaqiradi. |
| `POST` | `/api/v1/devices/unregister/` | POST /api/devices/unregister/ {"token": "..."} — shu qurilmaga bildirishnoma yuborishni to'xtatish (204). |
| `GET` | `/api/v1/directorates/` | Directorates list |
| `GET` | `/api/v1/directorates/{id}/` | Directorates read |
| `GET` | `/api/v1/divisions/` | Divisions list |
| `GET` | `/api/v1/divisions/{id}/` | Divisions read |
| `GET` | `/api/v1/employees/` | Employees list |
| `POST` | `/api/v1/employees/` | Employees create |
| `GET` | `/api/v1/employees/{id}/` | Employees read |
| `PUT` | `/api/v1/employees/{id}/` | Employees update |
| `PATCH` | `/api/v1/employees/{id}/` | Employees partial update |
| `DELETE` | `/api/v1/employees/{id}/` | Employees delete |
| `GET` | `/api/v1/employees/{id}/permissions/` | Xodim ruxsatlari (saytdagi "ruxsatlar" oynasi): GET — joriy holat va tanlash variantlari; |
| `PUT` | `/api/v1/employees/{id}/permissions/` | Xodim ruxsatlari (saytdagi "ruxsatlar" oynasi): GET — joriy holat va tanlash variantlari; |
| `GET` | `/api/v1/export/employees.xlsx` | GET /api/export/employees.xlsx?organization=&region=&department=&directorate=&division=&name= (view_employee; organization majburiy). |
| `GET` | `/api/v1/export/material-report.xlsx` | GET /api/export/material-report.xlsx?employee=&date1=&date2=&name= — kirim-chiqim hisoboti (view_material). |
| `GET` | `/api/v1/export/materials.xlsx` | GET /api/export/materials.xlsx — materiallar (view_material; ro'yxatdagi kabi ko'rish doirasi). Filtrlar: employee, category, unit, search. |
| `GET` | `/api/v1/export/technics.xlsx` | GET /api/export/technics.xlsx — texnikalar (view_technics; ro'yxatdagi kabi tashkilot/hudud doirasi). Filtrlar ro'yxatniki bilan bir xil. |
| `GET` | `/api/v1/goals/` | Faqat KO'RISH — 'all_organization' bo'lsa hammasi, aks holda faqat |
| `GET` | `/api/v1/goals/{id}/` | Faqat KO'RISH — 'all_organization' bo'lsa hammasi, aks holda faqat |
| `GET` | `/api/v1/groups/` | Groups list |
| `GET` | `/api/v1/groups/{id}/` | Groups read |
| `GET` | `/api/v1/liables/` | Faqat KO'RISH: xodimlarning texnika kategoriyasi va shartnoma bog'lanishlari. Saytda ular faqat ruxsatlar |
| `GET` | `/api/v1/liables/{id}/` | Faqat KO'RISH: xodimlarning texnika kategoriyasi va shartnoma bog'lanishlari. Saytda ular faqat ruxsatlar |
| `GET` | `/api/v1/material-categories/` | Faqat KO'RISH: material kategoriyalari — o'z tashkilotiniki (yoki umumiy); 'all_organization' bo'lsa hammasi. |
| `GET` | `/api/v1/material-categories/{id}/` | Faqat KO'RISH: material kategoriyalari — o'z tashkilotiniki (yoki umumiy); 'all_organization' bo'lsa hammasi. |
| `GET` | `/api/v1/material-employees/` | Faqat KO'RISH: xodimga ruxsat etilgan material kategoriyalari (saytda faqat ruxsatlar oynasida ko'rinadi). |
| `GET` | `/api/v1/material-employees/{id}/` | Faqat KO'RISH: xodimga ruxsat etilgan material kategoriyalari (saytda faqat ruxsatlar oynasida ko'rinadi). |
| `GET` | `/api/v1/material-movements/` | Faqat KO'RISH: material harakati jurnali ('view_material' kerak). Saytdagi hisobot kabi doira: o'z tashkiloti |
| `GET` | `/api/v1/material-movements/{id}/` | Faqat KO'RISH: material harakati jurnali ('view_material' kerak). Saytdagi hisobot kabi doira: o'z tashkiloti |
| `GET` | `/api/v1/material-users/` | Faqat KO'RISH: material delegatsiyasi (kim kimning materialini sarflay oladi). Saytda u faqat admin panelda |
| `GET` | `/api/v1/material-users/{id}/` | Faqat KO'RISH: material delegatsiyasi (kim kimning materialini sarflay oladi). Saytda u faqat admin panelda |
| `GET` | `/api/v1/materials/` | Materials list |
| `POST` | `/api/v1/materials/` | Materials create |
| `POST` | `/api/v1/materials/give/` | Bir nechta materialni bitta xodimga berish: POST /api/materials/give/ |
| `GET` | `/api/v1/materials/report/` | Material kirim-chiqim hisoboti (saytdagi mat_info): GET /api/materials/report/?employee=<id>&date1=&date2=&name= |
| `GET` | `/api/v1/materials/report/employees/` | Hisobotda tanlash mumkin bo'lgan xodimlar (saytdagi mat_info dropdown'i). |
| `POST` | `/api/v1/materials/service/` | Materialni sarflash: POST /api/materials/service/ {material_id, give_number, body} |
| `GET` | `/api/v1/materials/{id}/` | Materials read |
| `PUT` | `/api/v1/materials/{id}/` | Materials update |
| `PATCH` | `/api/v1/materials/{id}/` | Materials partial update |
| `DELETE` | `/api/v1/materials/{id}/` | Materials delete |
| `GET` | `/api/v1/me/` | GET /api/me/ — joriy foydalanuvchining xodim profili va Django |
| `GET` | `/api/v1/order-goals/` | Faqat KO'RISH: xodimlarning ruxsat etilgan ariza turlari. Saytda ular faqat ruxsatlar oynasida |
| `GET` | `/api/v1/order-goals/{id}/` | Faqat KO'RISH: xodimlarning ruxsat etilgan ariza turlari. Saytda ular faqat ruxsatlar oynasida |
| `GET` | `/api/v1/order-materials/` | Faqat KO'RISH — arizadagi materiallar ('view_order' bo'lsa tashkilot bo'yicha, bo'lmasa o'ziga aloqador |
| `GET` | `/api/v1/order-materials/{id}/` | Faqat KO'RISH — arizadagi materiallar ('view_order' bo'lsa tashkilot bo'yicha, bo'lmasa o'ziga aloqador |
| `GET` | `/api/v1/orders/` | Orders list |
| `POST` | `/api/v1/orders/` | Orders create |
| `GET` | `/api/v1/orders/available-materials/` | Bajaruvchi arizaga bera oladigan materiallar (unga MaterialUser orqali biriktirilgan xodimlarniki). |
| `GET` | `/api/v1/orders/badges/` | Belgilar soni (saytdagi qizil raqamlar): yangi bildirishnomalar va bajarish uchun kutayotganlar. |
| `POST` | `/api/v1/orders/mark-seen/` | Yangi ariza belgilarini o'chirish (saytdagi order_mark_seen). |
| `GET` | `/api/v1/orders/selectable-materials/` | Mijoz material arizasiga tanlay oladigan materiallar (saytdagi order_sender_material_barn): |
| `GET` | `/api/v1/orders/{id}/` | Orders read |
| `POST` | `/api/v1/orders/{id}/accept/` | ATM arizasini qabul qilish: POST /api/orders/{id}/accept/ ({"receiver": id} — faqat superuser) |
| `GET` | `/api/v1/orders/{id}/assignees/` | Superuser arizani biriktira oladigan xodimlar: GET /api/orders/{id}/assignees/ |
| `POST` | `/api/v1/orders/{id}/confirm/` | Tasdiqlovchi ('confirm_order'): POST /api/orders/{id}/confirm/ |
| `POST` | `/api/v1/orders/{id}/decide/` | ATM arizasi: POST /api/orders/{id}/decide/ {"action": "accepted", "rating": 1-5} yoki {"action": "canceled"} |
| `POST` | `/api/v1/orders/{id}/finish/` | ATM arizasini yakunlash: POST /api/orders/{id}/finish/ |
| `POST` | `/api/v1/orders/{id}/reject/` | Material arizasini rad etish (omborxonachi, change_order): POST /api/orders/{id}/reject/ |
| `GET` | `/api/v1/organizations/` | Organizations list |
| `GET` | `/api/v1/organizations/{id}/` | Organizations read |
| `GET` | `/api/v1/permissions/catalog/` | GET /api/permissions/catalog/ — ruxsatlar ro'yxati guruhlari (nomi bilan), bog'liqliklar va SUPER ruxsatlar ('permission_employee' kerak). |
| `GET` | `/api/v1/ranks/` | Ranks list |
| `GET` | `/api/v1/ranks/{id}/` | Ranks read |
| `GET` | `/api/v1/regions/` | Regions list |
| `GET` | `/api/v1/regions/{id}/` | Regions read |
| `GET` | `/api/v1/stats/employees/` | GET /api/stats/employees/?region=&date1=&date2= — bajaruvchi xodimlar bo'yicha arizalar statistikasi |
| `GET` | `/api/v1/stats/technics/` | GET /api/stats/technics/ — o'z tashkilotining faol texnikalari guruh va kategoriya bo'yicha (soni va foizi). |
| `GET` | `/api/v1/structure-categories/` | Structure-categories list |
| `GET` | `/api/v1/structure-categories/{id}/` | Structure-categories read |
| `GET` | `/api/v1/structures/` | Structures list |
| `POST` | `/api/v1/structures/` | Structures create |
| `GET` | `/api/v1/structures/{id}/` | Structures read |
| `PUT` | `/api/v1/structures/{id}/` | Structures update |
| `PATCH` | `/api/v1/structures/{id}/` | Structures partial update |
| `DELETE` | `/api/v1/structures/{id}/` | Structures delete |
| `POST` | `/api/v1/structures/{id}/assign/` | Qurilmani texnikaga biriktirish: POST /api/structures/{id}/assign/ {"technics": id} |
| `POST` | `/api/v1/structures/{id}/unassign/` | Qurilmani texnikadan ajratish: POST /api/structures/{id}/unassign/ ({"technics": id} ixtiyoriy) |
| `GET` | `/api/v1/technics/` | Technics list |
| `POST` | `/api/v1/technics/` | Technics create |
| `GET` | `/api/v1/technics/{id}/` | Technics read |
| `PUT` | `/api/v1/technics/{id}/` | Technics update |
| `PATCH` | `/api/v1/technics/{id}/` | Technics partial update |
| `DELETE` | `/api/v1/technics/{id}/` | Technics delete |
| `POST` | `/api/v1/technics/{id}/assign/` | Technics assign |
| `GET` | `/api/v1/technics/{id}/qr/` | QR kodni to'g'ridan-to'g'ri fayl sifatida qaytaradi: GET /api/technics/{id}/qr/ |
| `POST` | `/api/v1/technics/{id}/unassign/` | Bo'shatish: POST /api/technics/{id}/unassign/ - xodim va struktura olib tashlanadi, holat 'free'. |
| `POST` | `/api/v1/token/` | Takes a set of user credentials and returns an access and refresh JSON web |
| `POST` | `/api/v1/token/refresh/` | Takes a refresh type JSON web token and returns an access type JSON web |
| `GET` | `/api/v1/units/` | Units list |
| `GET` | `/api/v1/units/{id}/` | Units read |
