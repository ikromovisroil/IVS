# IVC API — mobil ilovalar (Android va iOS) uchun qo'llanma

Bu hujjat **mobil ilovaga kiradigan funksiyalar** uchun. Android va iOS uchun **bir xil API**; farqli joylar 13-bo'limda.
Interaktiv hujjat: `https://<server>/swagger/` (saytga kirgan holatda ochiladi). Ruxsatlarning to'liq tavsifi: `ROLLAR_VA_RUXSATLAR.md`.

Asosiy manzil: **`https://<server>/api/v1/`**. Quyida qisqalik uchun `/api/...` yoziladi — ularni `/api/v1/...` deb o'qing.
So'rov va javoblar JSON (fayllar — `multipart/form-data`), vaqtlar — ISO 8601.

---

## 1. Mobilda nima bor, nima yo'q

### 1.1 Mobilda bor (1-versiya)

| № | Bo'lim | Nima qila oladi | Bo'lim |
|---|---|---|---|
| 1 | Kirish va profil | SSO (OneID), o'z ma'lumoti, ruxsatlari | 3, 4 |
| 2 | Arizalar: ATM arizasi | O'z nomidan yuborish; bajaruvchi: qabul qilish, **texnika va material biriktirib yakunlash**; yuboruvchi: baho bilan qabul qilish yoki bekor qilish | 7 |
| 3 | **Omborxona** (mijoz tashkilotida) | Mijoz: **material tanlab omborxonaga ariza berish**, kuzatish, qabul qilish, bekor qilish. **Omborxonachi:** arizani qabul qilish, rad etish, materiallarni berish. **Tasdiqlovchi:** berilgan materiallarni tasdiqlash yoki rad etish | 7.4, 7.5, 7.6 |
| 4 | Xabarlar (hujjatlar) | Ro'yxat, PDF ko'rish, **FaceID bilan imzolash**, kelishish, rad etish; **hujjatlarni qidirish (reyestr)** | 8 |
| 5 | Ombor | **Texnikalar, qurilmalar va materiallar: ko'rish, qo'shish, tahrirlash, o'chirish**; texnikani biriktirish va bo'shatish; **materialni xodimga berish va sarflash**; "Texnikalarim" | 9 |
| 6 | **QR skaner** | Texnika QR'i: kartani ko'rish; huquq bo'lsa **tahrirlash, xodimga biriktirish va bo'shatish**. Hujjat QR'i: hujjat holatini ko'rish | 9.4 |
| 7 | Xodimlar | Ro'yxat, qidiruv, filtr, tafsilot (ikkala telefon raqami bilan); **qo'shish** (PINFL bo'yicha yoki qo'lda), **tahrirlash, o'chirish** | 10 |
| 8 | Chat | Xabarlar, fayl, real vaqt (WebSocket) | 11 |
| 9 | Bildirishnomalar va push | Tarix, o'qilmaganlar soni, push | 12 |

### 1.2 Mobilda yo'q (veb'da qoladi)

| Nima | Izoh |
|---|---|
| Boshqa xodim nomidan ariza berish | `sender` maydonini yubormang, `sender_user` ro'yxati ham yo'q |
| Hujjat yaratish va tahrirlash | `POST`/`PATCH /deeds/`, hisobotdan hujjat yaratish |
| Hujjatda kelishuvchilarni boshqarish | qo'shish/olib tashlash, `signer-consent`, `toggle-user-edit` |
| E-IMZO | mobilda faqat FaceID |
| Statistika va dashboard | `/stats/...`, `/spa/stats/...` |
| Hisobotlar | Svod, Reestr, Akt, Sarf, Dalolatnoma; Excel eksport (`/export/...`); material kirim-chiqim hisoboti |
| Xodimga ruxsat (rol) berish | veb'da (`/employees/{id}/permissions/`, `permission_employee`) |
| Zoom uchrashuvlari | 2-versiya |

Server tomonida bu endpointlar o'z holicha qoladi (veb ishlatadi); mobil ularni **chaqirmaydi**.

### 1.3 Pastki menyu (bottom navigation)

Ilovaning pastki paneli 5 ta bo'limdan iborat. **O'rtadagi tugma — QR skaner** (avval "Yangi ariza" edi).

| № | Tugma | Nima ochadi | API | Ruxsat |
|---|---|---|---|---|
| 1 | Bosh sahifa | Bosh ekran (qisqa ko'rinish: faol arizalar, kutayotgan hujjatlar) | 7, 8 | — |
| 2 | Arizalar | Yuqorida bo'lim tablari (1.4) + **"+" tugmasi (Yangi ariza)** | 7 | tablar `organization_type` va ruxsatga qarab |
| 3 | **Skaner** (o'rtada, ajratib ko'rsatiladi) | Kamera ochiladi, QR o'qiladi | `POST /api/scan/` (9.4) | kerak emas |
| 4 | Xabarlar | Hujjatlar (imzolash, kelishish, reyestr) | 8 | — |
| 5 | Menyu | Qolgan bo'limlar: Ombor, Xodimlar, Chat, Bildirishnomalar, Profil | 9, 10, 11, 12, 4 | ruxsatga qarab |

**"Yangi ariza" qayerda.** Pastki menyudan olib tashlandi, lekin yo'qolmaydi:
- Arizalar ekranining o'ng pastki burchagida suzuvchi **"+"** tugmasi;
- Arizalar ro'yxati bo'sh bo'lsa — markazda "Ariza yaratish" tugmasi.
"+" **ochiq tabga qarab** ishlaydi: "ATMga ariza" tabida — ATM arizasi (`POST /api/orders/`, 7.1; turlari `/me/` dagi `orders.send_goals`); "Omborxona" tabida — material arizasi (7.4; turlari `orders.material_goals`). Alohida tur tanlash oynasi kerak emas.

**Skaner tugmasi:**
- Ruxsat talab qilinmaydi: texnika kartasini va hujjat holatini hamma kirgan xodim ko'radi. Tahrirlash, biriktirish va bo'shatish tugmalari faqat javobda `can_edit: true` bo'lganda chiqadi (9.4).
- Birinchi bosishda Android `CAMERA` ruxsati so'raladi. Rad etilsa — tushuntirish va "Sozlamalarga o'tish" tugmasi.
- Bitta QR o'qilgach kamera to'xtaydi (server chegarasi — daqiqasiga 60 ta so'rov).
- Natijalar: texnika → texnika kartasi; hujjat → hujjat holati (`can_open: true` bo'lsa to'liq ochiladi); `400 unknown` → "Bu IVC QR kodi emas"; `404` → "Topilmadi".
- Qora fon ustida chiroq (fonar) tugmasi va "Galereyadan tanlash" bo'lishi tavsiya etiladi (ixtiyoriy).

**Qizil raqamlar (badge):**
- Xabarlar — o'qilmagan bildirishnomalar (`GET /api/notifications/unread-count/`, 12.1);
- Menyu → Chat — `GET /api/chat/unread-count/`;
- Arizalar — `GET /api/orders/badges/` (7.3).

Tugmalar **bir odamga bir nechta ruxsat** berilganda ham o'zgarmaydi: 5 ta tugma hamma uchun bir xil, farq faqat ichki ekranlardagi bo'limlarda (2.5-bo'lim).

### 1.4 "Arizalar" ekrani: tablar (vebdagidek)

Ekran tepasida tablar. Qaysilari ko'rinishi vebdagi "Arizalar" bo'limi bilan bir xil (`frontend/src/pages/orders/tabs.ts`); shart — `/me/` dagi `organization_type` va ruxsatlar:

| Tab | Kimga ko'rinadi | Nima |
|---|---|---|
| **ATMga ariza** | hammaga (ATM xodimi ham, mijoz ham) | O'z arizalari: yuborish, kuzatish, baho bilan qabul qilish, bekor qilish (7.1) |
| **Omborxona** | faqat `organization_type = "client"` | Material tanlab omborxonaga ariza berish va kuzatish (7.4) |
| **Arizalar holati** (ATM) | `worker` va `change_order` | Yangi, qabul qilingan, arxiv — bajarish (7.2) |
| **Arizalar holati** (omborxona) | `client` va `change_order` | Omborxonachi: arizani qabul qilish, rad etish, material berish (7.5) |
| **Tasdiqlash** | `client` va `confirm_order` | Berilgan materiallarni tasdiqlash (7.6) |

Natija:
- **ATM xodimi** (`worker`): "ATMga ariza" (+ ruxsati bo'lsa "Arizalar holati"). **Omborxona tabi yo'q.**
- **Mijoz xodimi** (`client`): "ATMga ariza" **va** "Omborxona" (+ ruxsatiga qarab "Arizalar holati", "Tasdiqlash").
- Tab bitta bo'lsa, tab paneli ko'rsatilmaydi — to'g'ridan-to'g'ri ro'yxat ochiladi.
- Omborxona tabi `organization_type` bo'yicha chiqadi. Agar `orders.material_goals` bo'sh bo'lsa (tashkilotga ariza turi biriktirilmagan), tab ko'rinadi, lekin "+" o'rniga "Ariza turlari sozlanmagan, administratorga murojaat qiling" yozuvi chiqadi.

### 1.5 "Menyu" ekrani (ruxsatga qarab)

"Menyu" da faqat **mobilda mavjud** bo'limlar chiqadi, har biri ruxsatiga qarab (`/me/` → `permissions`, `main.<nom>`). Ruxsati yo'q bo'limni **yashiring**; server baribir `403` qaytaradi.

| Element | Ko'rinish sharti | Bo'lim |
|---|---|---|
| Texnikalarim | hammaga | 9.1 |
| Texnikalar (ombor) | `view_technics` | 9.1 |
| Qurilmalar | `change_technics` | 9.2 |
| Materiallar | `view_material` | 9.3 |
| Xodimlar | `view_employee` | 10 |
| Chat | hammaga | 11 |
| Bildirishnomalar | hammaga | 12.1 |
| Profil, Chiqish | hammaga | 4, 3 |

Menyu'da **yo'q** (boshqa joyda): Hujjatlar — "Xabarlar" tabida; Arizalar va Omborxona — "Arizalar" tabida (1.4); QR skaner — pastki menyu o'rtasida (1.3). Statistika, hisobotlar va ruxsat berish mobilda umuman yo'q (1.2).

Ichki ekranlardagi amallar ham ruxsatga qarab: "+" tugmasi (`add_*`), tahrirlash (`change_*`), o'chirish (`delete_*`) — 2.5-bo'lim. Ruxsati kam xodimda Menyu qisqa bo'ladi (Texnikalarim, Chat, Bildirishnomalar, Profil) — bu normal.

---

## 2. Kim nimani ko'radi

Ilova ekranlarini ikki narsa belgilaydi: **tashkilot turi** (`organization_type` — `client` mijoz, `worker` xizmatchi/ATM vakili) va xodimga berilgan **ruxsatlar** (`permissions`).
Ilova tugmalarni `/me/` dagi bayroq va ruxsatlarga qarab ko'rsatadi; server har so'rovda o'zi tekshiradi (`403`).

### 2.1 Ikkalasiga ham bir xil

| Bo'lim | Nima |
|---|---|
| Kirish, profil, chat, push, bildirishnomalar | hamma xodim |
| Ariza yuborish | o'z nomidan; o'z arizalarini kuzatish, baho bilan qabul qilish, bekor qilish |
| Xabarlar | faqat o'zi ishtirokchi bo'lgan hujjatlar: imzolash (FaceID), kelishish, rad etish |
| Texnikalarim | o'ziga biriktirilgan texnikalar (ruxsatsiz) |
| QR skaner | texnika kartasi va hujjat holati (9.4) |

### 2.2 Mijoz xodimi (`client`)

| Bo'lim | Holat |
|---|---|
| Ariza yuborish | bor (`orders.can_create`, tur `send_goals` dan) |
| Arizani bajarish | **yo'q** — mijoz bajara olmaydi (`403`) |
| **Omborxonaga material arizasi** | bor (`orders.can_create_material_order`, tur `material_goals` dan), ruxsat kerak emas (7.4) |
| **Omborxonachi** (arizani qabul qilish, rad etish, materiallarni berish) | `change_order` bo'lsa (7.5) |
| **Tasdiqlovchi** (berilgan materiallarni tasdiqlash) | `confirm_order` bo'lsa (7.6) |
| Texnikalar, qurilmalar, materiallar (ombor) | faqat o'z tashkiloti; ko'rish — `view_technics` / `view_material`; boshqarish — `add_`/`change_`/`delete_technics` va `add_`/`change_`/`delete_material` bo'lsa (mijoz omborxonachisida material ruxsatlari bo'ladi). Materialni sarflash (`material_service`) mijozda yo'q |
| Xodimlar | `view_employee` bo'lsa o'z tashkiloti; qo'shish, tahrirlash, o'chirish — `add_`/`change_`/`delete_employee` bo'lsa |

Mijozga berilmaydi: `add_order`, `add_deed`, `all_organization`, `all_region`, `material_service`, hisobotlar, Zoom.
Mijozda `change_order` (omborxonachi) va `confirm_order` (tasdiqlovchi) bo'lishi mumkin: ular mobilda **omborxona** bo'limida ishlaydi (7.5, 7.6).

### 2.3 Xizmatchi (ATM, `worker`)

| Bo'lim | Holat |
|---|---|
| Ariza yuborish | bor |
| **Arizani bajarish** (`change_order`) | bor: yangi, qabul qilganlari, arxiv; **faqat o'z hududi va ruxsat etilgan turlar** (`execute_goals`) |
| Yakunlash | texnika va material biriktirib (`finish`) |
| Texnikalar, qurilmalar, materiallar (ombor) | ko'rish `view_technics` / `view_material`; boshqarish `add_`/`change_`/`delete_technics`, `add_`/`change_`/`delete_material`; materialni sarflash `material_service`; doira — tashkilot va hudud (`all_organization`, `all_region` bo'lsa kengroq) |
| Xodimlar | `view_employee`; qo'shish, tahrirlash, o'chirish — `add_`/`change_`/`delete_employee` |

### 2.4 Odatiy lavozimlar

| Lavozim | Tashkilot | Mobilda qo'shimcha ko'radi |
|---|---|---|
| Oddiy mijoz xodimi | `client` | ariza yuborish, **omborxonaga material arizasi**, Texnikalarim, hujjatlar (ishtirokchi bo'lsa), chat |
| Mijoz omborxonachisi | `client` | + material arizalarini qabul qilish, rad etish, materiallarni berish (`change_order`, 7.5); materiallarni ko'rish, qo'shish, tahrirlash, xodimga berish (`view_`/`add_`/`change_material`) |
| Mijoz tasdiqlovchisi | `client` | + berilgan materiallarni tasdiqlash yoki rad etish (`confirm_order`, 7.6) |
| Mijoz rahbari | `client` | + materiallar (`view_material`), xodimlar (ruxsat bo'lsa) |
| ATM ijrochisi | `worker` | + arizalarni bajarish (`change_order`) |
| ATM texnigi | `worker` | + texnika va qurilmalarni ko'rish va boshqarish (`view_`/`add_`/`change_technics`), QR skaner, arizalarni bajarish |
| ATM omborxonachisi | `worker` | + materiallar (`view_material`), arizalarni bajarish |
| Kadrlar bo'limi | `worker` | + xodimlarni ko'rish, **qo'shish, tahrirlash, o'chirish** (`view_`/`add_`/`change_`/`delete_employee`) |
| Rahbar | `worker` | + xodimlar, kengroq doira (`all_region`) |

### 2.5 Mobilda ishlatiladigan ruxsatlar

Tizimda alohida "rol" yo'q: xodimga **ruxsatlar (permission)** to'plami beriladi (veb'dagi "Xodimlarga rol berish" oynasida; mobilda bu oyna yo'q).
Ruxsatlar `GET /me/` → `permissions` ro'yxatida `main.<nom>` ko'rinishida keladi. Mobilda **faqat quyidagilar** ishlatiladi:

| Ruxsat | Mobilda nimaga kerak | Kimga beriladi | Odatda kim ishlatadi |
|---|---|---|---|
| `change_order` | **ATM xodimida:** arizani bajarish (yangi arizalar, qabul qilish, texnika va material biriktirib yakunlash; turlari `execute_goals`). **Mijoz xodimida:** omborxonachi — material arizasini qabul qilish, rad etish, materiallarni berish (7.5) | hammaga beriladi; ATM arizasini **faqat `worker`** bajara oladi (mijozda `403`), material arizasini esa **mijoz** omborxonachisi qabul qiladi | ATM ijrochisi, texnik, ATM omborxonachisi; mijoz omborxonachisi |
| `confirm_order` | Berilgan materiallarni **tasdiqlash yoki rad etish** (7.6) | faqat `client` (worker emas) | mijoz tashkilotidagi tasdiqlovchi (rahbar yoki mas'ul) |
| `view_technics` | Texnikalar ro'yxati va tafsiloti (ombor). Faqat xodimga biriktirilgan texnika kategoriyalari ko'rinadi (rol berishda "Texnika kategoriyasi") | hammaga | texnik xodim, ombor mas'uli |
| `add_technics` | Texnikani va qurilmani **qo'shish** (9.1, 9.2). `view_technics` bo'lishi shart | hammaga | texnika bo'yicha mas'ul |
| `change_technics` | Texnika va qurilmani **tahrirlash, xodimga/texnikaga biriktirish, bo'shatish/ajratish**; QR skanerda `can_edit`; alohida **"Qurilmalar"** ro'yxatini ko'rish. `view_technics` bo'lishi shart | hammaga | texnika bo'yicha mas'ul, ATM texnigi |
| `delete_technics` | Texnika va qurilmani **o'chirish** (arxivlash). `view_technics` bo'lishi shart | hammaga | texnika bo'yicha mas'ul, rahbar |
| `view_material` | Materiallar ro'yxati va tafsiloti (ombor) | hammaga | omborxonachi, material mas'uli |
| `add_material` | Material **qo'shish** (rasm bilan). `view_material` shart | hammaga | omborxonachi |
| `change_material` | Materialni **tahrirlash** va **xodimga berish** (`give`). `view_material` shart | hammaga | omborxonachi |
| `delete_material` | Materialni **o'chirish** (arxivlash). `view_material` shart | hammaga | omborxonachi, material mas'uli |
| `material_service` | Materialni **sarflash** (`service`). `view_material` shart | faqat `worker` (mijozga berilmaydi) | materialni ishlatadigan ATM xodimi |
| `shop_employee` | "Materialga javobgar" belgisi: shu xodim o'z tashkilotidagi materiallarni ko'radi | rolni beruvchi `worker` bo'lishi kerak | omborxonachi, moddiy javobgar |
| `all_material_employee` | Materiallar ro'yxatida boshqa javobgar xodimlarning materiallari ham ko'rinadi. `view_material` shart | hammaga; faqat o'zida bor odam bera oladi (SUPER) | omborxona mudiri, material bo'yicha rahbar |
| `boss_employee` | "Texnikalarim" da o'z departamentidagi **hamma texnika** va texnikasi yo'q xodimlar | rolni beruvchi `worker` bo'lishi kerak | departament boshlig'i |
| `view_employee` | Xodimlar ro'yxati, qidiruv, tafsilot | hammaga | kadrlar bo'limi, rahbarlar |
| `add_employee` | Xodim **qo'shish** (PINFL bo'yicha yoki qo'lda). `view_employee` shart | hammaga | kadrlar bo'limi |
| `change_employee` | Xodimni **tahrirlash**. `view_employee` shart | hammaga | kadrlar bo'limi |
| `delete_employee` | Xodimni **o'chirish** (faolsizlantirish). `view_employee` shart | hammaga | kadrlar bo'limi |
| `all_organization` | **Ko'rish doirasini kengaytiradi:** boshqa tashkilotlar xodimlari, texnikalari, materiallari; shuningdek QR orqali har qanday hujjatni to'liq ochish | faqat `worker`; faqat o'zida bor odam bera oladi (SUPER) | bosh rahbariyat, markaziy mas'ullar |
| `all_region` | Ko'rish doirasini boshqa hududlarga kengaytiradi | faqat `worker` | respublika miqyosidagi rahbarlar |

Bog'liqlik: `view_*` olib tashlansa, unga bog'liq ruxsatlar ham olinadi (`view_technics` → `change_technics`; `view_material` → `all_material_employee`;
`view_employee` → `add_employee`, `change_employee`, `delete_employee`). Ikkalasi ham (`all_organization`, `all_region`) bo'lmasa, server natijani xodimning **o'z tashkiloti va hududi** bilan cheklaydi.

### 2.6 Ruxsat talab qilinmaydigan funksiyalar (hamma kirgan xodim)

| Funksiya | Shart |
|---|---|
| Kirish, profil (`/me/`), versiya tekshiruvi | — |
| **Ariza yuborish**, o'z arizalarini kuzatish, baho bilan qabul qilish, bekor qilish | ariza turi `/me/` dagi `orders.send_goals` ro'yxatida bo'lishi kerak |
| **Omborxonaga material arizasi** (faqat mijoz): materiallarni tanlab yuborish, kuzatish, qabul qilish | ariza turi `orders.material_goals` ro'yxatida; ATM xodimiga yo'q |
| **Hujjatlarni qidirish** (reyestr, faqat o'qish): filtr bilan, imzolovchisi/kelishuvchisi o'z tashkilotidan bo'lgan hujjatlar | kamida bitta filtr kerak; ishtirokchi bo'lish shart emas; `all_organization` — hamma tashkilot (8.5) |
| **Hujjatlar:** o'zi ishtirok etganini ko'rish, **FaceID bilan imzolash**, **kelishish**, rad etish | faqat o'zi yaratuvchi, imzolovchi, qabul qiluvchi yoki kelishuvchi bo'lgan hujjat |
| **Texnikalarim** (`GET /spa/warehouse/technics/mine/`) | o'ziga biriktirilgan texnikalar (`boss_employee` bo'lsa kengroq) |
| **QR skaner:** texnika kartasi va hujjat holati | hujjat PDF'i va to'liq ochish faqat ishtirokchiga |
| Chat, bildirishnomalar markazi, push-qurilmani ro'yxatdan o'tkazish | — |
| Ma'lumotnomalar (tashkilot, hudud, bo'lim, lavozim, guruh, kategoriya) — faqat o'qish | doirani server cheklaydi |

Imzolash va kelishish uchun alohida ruxsat yo'q: hujjatda imzolovchi (`sender`/`receiver`) yoki kelishuvchi qilib tanlangan xodim o'zi javob beradi.

### 2.7 Mobilda ishlatilmaydigan ruxsatlar (veb'da bor)

Bular serverda ishlaydi, lekin mobil ilovada ularga bog'liq ekran **yo'q** (ilova ularni e'tiborsiz qoldiradi):

| Ruxsat | Veb'da nima uchun | Nega mobilda yo'q |
|---|---|---|
| `add_order` | boshqa xodim nomidan ariza berish | mobilda ariza faqat o'z nomidan |
| `add_deed`, `change_deed` | hujjat yaratish, tahrirlash ruxsatini almashtirish | mobil hujjat yaratmaydi |
| `report_employee`, `shop_employee` (hisobotlar uchun) | Svod, Reestr, Dalolatnoma hisobotlari | hisobotlar mobilda yo'q |
| `status_employee` | statistika va bosh sahifa | statistika mobilda yo'q |
| `permission_employee` | xodimlarga ruxsat (rol) berish | mobilda bunday oyna yo'q (veb'da) |
| `view_meeting`, `add_meeting`, `delete_meeting` | Zoom uchrashuvlari | 2-versiya |

---

## 3. Kirish (SSO) va tokenlar

Ilovada parol yo'q — kirish SSO (`sso.mf.uz`, OAuth 2.0 + PKCE) orqali. `client-secret` ilovada **bo'lmaydi**.

### A variant — SSO bilan to'g'ridan-to'g'ri (tavsiya)
**Shart:** ilovaning `redirect_uri` si (deep link / universal link) SSO clientida ro'yxatdan o'tgan va serverda `MOBILE_SSO_REDIRECT_URIS` ga qo'shilgan bo'lishi kerak, aks holda `/api/auth/sso/token/` `503` beradi.
1. `code_verifier` (43–128 belgi) va `code_challenge = BASE64URL(SHA256(code_verifier))` (paddingsiz) yaratiladi.
2. Foydalanuvchi SSO sahifasiga yuboriladi:
   `https://sso.mf.uz/oauth2/login?clientId=<CLIENT_ID>&redirectUri=<REDIRECT_URI>&codeChallenge=<code_challenge>`
3. Kirgach SSO ilovaning `redirect_uri` iga `code` qaytaradi.
4. `POST /api/auth/sso/token/` `{"code", "code_verifier", "redirect_uri"}` → `{"access", "refresh", "employee"}`.

### B variant — serverning mobil kirish manzili orqali
1. Ilova `code_verifier` va `code_challenge` yaratadi (yuqoridagidek).
2. Brauzerni ochadi (Android — Chrome Custom Tab, iOS — `ASWebAuthenticationSession`):
   `GET /api/auth/mobile/start/?code_challenge=<code_challenge>`. Foydalanuvchi SSO'dan o'tadi.
3. Brauzer ilovaning deep link'iga qaytadi: `ivsapp://auth?code=<code>` (kod **2 daqiqa** amal qiladi; sxema `MOBILE_APP_REDIRECT` sozlamasida).
4. `POST /api/auth/mobile/exchange/` `{"code", "code_verifier"}` → `{"access", "refresh", "employee"}` (daqiqasiga 20 ta so'rov).

### Tokenlar
- Keyingi so'rovlar: `Authorization: Bearer <access>`. Access **1 soat**, refresh **30 kun**.
- Yangilash: `POST /api/token/refresh/` `{"refresh"}` → `{"access", "refresh"}`. **Har safar yangi `refresh` qaytadi, eskisi bekor bo'ladi — yangisini darhol saqlang.**
  `401` kelsa refresh bilan yangilang; refresh ham yaroqsiz bo'lsa — qaytadan kirish.
- Chiqish: `POST /api/auth/logout/` `{"refresh", "fcm_token"?}` (Bearer bilan) → `204`.
- Tokenlarni **xavfsiz saqlashda** saqlang (Android — Keystore/EncryptedSharedPreferences, iOS — Keychain).
- Kirish natijalari: tizimda yo'q foydalanuvchi — brauzerda `403` ("Siz tizimda ro'yxatda yo'qsiz"); bloklangan — token berilmaydi.

---

## 4. Foydalanuvchi kimligi — `GET /api/me/`

Kirgandan keyin darhol, keyin ilova ochilganda va token yangilanganda chaqiriladi.

```json
{
  "username": "...", "is_superuser": false,
  "employee": {"id": 1, "full_name": "...", "organization": 2, "organization_name": "...", "rank_name": "..."},
  "organization_type": "client",
  "orders": {
    "can_create": true, "can_execute": false,
    "send_goals": [{"id": 5, "name": "Kompyuter ta'miri", "organization": 1}],
    "execute_goals": []
  },
  "permissions": ["main.view_employee", "main.change_order", "..."]
}
```

- `organization_type`: `worker` — ATM vakili, `client` — mijoz.
- `orders.can_create` — ariza yubora oladimi; `send_goals` — yuborish mumkin bo'lgan ariza turlari.
- `orders.can_execute` — arizalarni qabul qilish/yakunlash (ATM + `change_order`); `execute_goals` — qaysi turlarni bajarishi mumkin.
- `permissions` — Django ruxsatlari (`app.codename`). Tugma va menyularni shu ro'yxat bilan ko'rsating/yashiring.
- `orders.can_create_material_order` — mijoz omborxonaga material arizasi yubora oladimi; `orders.material_goals` — shu arizaning turlari (7.4). ATM xodimida bo'sh.
- `orders.can_confirm` — tasdiqlovchi (`confirm_order`): "Omborxona" ichida tasdiqlash bo'limini ko'rsatadi (7.6).
- **Mobilda e'tibor bermaydigan maydonlar:** `can_create_on_behalf`, `can_assign` (1-versiyada ishlatilmaydi).
- **Ilovadagi yashirish faqat qulaylik** — server har so'rovda tekshiradi va ruxsatsiz amalga `403` qaytaradi.

---

## 5. Umumiy qoidalar

- **Sahifalash:** ro'yxatlar 20 tadan: `?page=2`, `?page_size=50` (eng ko'pi 100). Javob: `{"count", "next", "previous", "results": [...]}`.
- **Qidiruv va filtr:** `?search=...` va resursga xos filtrlar (Swagger'da).
- **Xatolar:** `400` — tekshiruv xatosi (`{"maydon": ["xabar"]}` yoki `{"detail": "xabar"}`) — xabarni foydalanuvchiga ko'rsating;
  `401` — token yo'q yoki eskirgan (refresh bilan yangilang); `403` — ruxsat yo'q; `404` — topilmadi yoki sizga ko'rinmaydi; `405` — bu amal yo'q;
  `429` — so'rov ko'p (`Retry-After` ni kuting).
- **Ko'rish doirasi:** server tashkilot, hudud va ishtirokchilik bo'yicha o'zi cheklaydi.
- **Fayllar:** hujjat PDF — 10 MB gacha; chat fayli — 15 MB gacha; ilovalar — PDF/Word/Excel, 10 MB gacha.
- Ko'rsatiladigan nomlar `*_name` va `*_display` maydonlarida keladi (masalan `status_display`).
- So'rovlar chegarasi: foydalanuvchi uchun 1200 so'rov/daqiqa; login — 30 urinish/daqiqa.

### 5.1 Ilova versiyasi va texnik ishlar
- **Ilova ochilganda (kirishdan oldin)** `GET /api/v1/app/config/?platform=android|ios&version=1.0.3` (token kerak emas):
  `{"api_version", "server_time", "app": {"current_version", "latest_version", "min_version", "update_available", "force_update", "update_url", "message"}, "maintenance": {"enabled", "message"}}`.
  `force_update: true` — ilova ishlashni to'xtatib, `update_url` ga yo'naltirsin; `update_available` — yangilash tavsiya etiladi.
- Har so'rovga `X-App-Version: 1.0.3` sarlavhasini qo'shing. Versiya `min_version` dan eski bo'lsa server **426** `{"code": "upgrade_required", "detail", "min_version", "update_url"}` qaytaradi.
- Texnik ishlar paytida so'rovlar **503** `{"code": "maintenance", "detail"}` (+ `Retry-After`) qaytaradi.
- Barcha javoblarda `X-API-Version: 1` bor.

---

## 6. Ma'lumotnomalar (faqat o'qish)

Mobilda kerakli: `organizations`, `regions`, `departments`, `directorates`, `divisions`, `ranks`, `groups`, `categories`.
Nom bo'yicha tartiblangan va sahifalangan. Ketma-ket tanlash:
`departments?organization=X&region=Y` → `directorates?department=Z` → `divisions?directorate=W`.
Ko'rinish tashkilot va hududga bog'liq (`all_organization` / `all_region` bo'lmasa faqat o'zinikilar).

---

## 7. Arizalar — `/api/orders/` (ATM arizasi)

Holatlar: `viewed` (yangi) → `process` (jarayonda) → `finished` (bajarildi) → `accepted` (qabul qilindi, baho bilan) yoki `canceled`.
Mijoz yuboradi, ATM vakili bajaradi.

### 7.1 Yuboruvchi (har qanday xodim)
- **Yuborish:** `POST /api/orders/` `{"goal": <send_goals dan>, "message_sender": "..."}`.
  Materiallar va texnika yuborishda **berilmaydi** — ularni bajaruvchi yakunlashda biriktiradi. `sender` maydonini yubormang.
- **Ro'yxatlar:** `?role=sender` (yangi, jarayonda, bajarilgan), `?role=sender_archive`.
- **Baho bilan qabul qilish:** `POST /api/orders/{id}/decide/ {"action": "accepted", "rating": 1..5}` (faqat `finished` ariza).
- **Bekor qilish:** `POST /api/orders/{id}/decide/ {"action": "canceled"}`.

### 7.2 Bajaruvchi (ATM xodimi, `change_order`)
Mijoz tashkiloti xodimi bajara olmaydi. Ko'rish doirasi: o'z hududi va `execute_goals` dagi turlar.
- **Ro'yxatlar:** `?role=receiver_new` (yangi), `?role=receiver_active` (qabul qilganlari), `?role=receiver_archive`.
- **Qabul qilish:** `POST /api/orders/{id}/accept/` → `process`.
- **Yakunlash** (faqat arizani qabul qilgan xodim):
  1. `GET /api/orders/available-materials/?search=` — unga biriktirilgan materiallar.
  2. `POST /api/orders/{id}/finish/ {"technics_id": 12, "materials": [{"material_id": 3, "number": 2}]}` — texnika (ixtiyoriy) va materiallar biriktiriladi; materiallar ombordan ayriladi → `finished`.

### 7.3 Belgilar
`GET /api/orders/badges/` → `{"notifications": n, "receiver_pending": m}` (qizil raqamlar); `POST /api/orders/mark-seen/` — belgilarni o'chirish.

### 7.4 Material arizasi (mijoz → o'z omborxonasi)

**Faqat mijoz (`client`) xodimi uchun.** Mijoz o'z tashkilotining omborxonasidan material so'raydi: materiallarni tanlab ariza yuboradi, holatini kuzatadi, olgach qabul qiladi.
Ilova bu bo'limni ("Arizalar" ekranidagi "Omborxona" tabi, 1.4) `organization_type = "client"` bo'lganda ko'rsatadi (vebdagidek); ATM xodimida u yo'q. Ariza **yuborish** uchun `orders.can_create_material_order: true` (ya'ni `material_goals` bo'sh emas) bo'lishi kerak.

**Ariza yuborish** — savatni ilova **qurilmada o'zi saqlaydi** va bitta so'rovda yuboradi:
1. `GET /api/orders/selectable-materials/?search=` — o'z tashkilotining faol materiallari (faqat unga ruxsat etilgan kategoriyalar).
2. `POST /api/orders/` `{"goal": <material_goals dan>, "message_sender": "...", "materials": [{"material_id": 3, "number": 2}]}`.
   Qoidalar: savat bo'sh bo'lmasin, material takrorlanmasin, soni 1 dan kam bo'lmasin; `goal` — `/me/` dagi `orders.material_goals` ro'yxatidan. Ombordan hali ayirilmaydi.
   ATM xodimi yubora olmaydi.

**Holatlar:** `viewed` (yangi) → `process` (omborxonachi qabul qildi) yoki `rejected` (rad etildi);
`process` → `finished` (materiallar berildi) → `approved` (tasdiqlovchi tasdiqladi) yoki `rejected` (materiallar omborga qaytadi) → `accepted` (siz qabul qildingiz).

**Mijoz (yuboruvchi) mobilda:**
- **Ro'yxatlar:** `GET /api/orders/?role=barn_sender` (faol), `?role=barn_sender_archive` (arxiv). Arizadagi materiallar va berilgan sonlar javobda (`materials[]`).
- **Qabul qilish:** `POST /api/orders/{id}/decide/ {"action": "accepted"}` — faqat tasdiqlangan (`approved`) arizani. Qabul qilinganda **akt (hujjat) avtomatik yaratiladi**
  (arizadagi `deeds` maydonida); xato bo'lsa javobda `warning` keladi — foydalanuvchiga ko'rsating.
- **Bekor qilish:** `POST /api/orders/{id}/decide/ {"action": "canceled"}` — `viewed`, `process`, `finished` holatlarida.
- Arizadagi materiallar alohida tahrirlanmaydi (`GET /api/order-materials/` faqat ko'rish uchun).
- Holat o'zgarganda `order_status` push keladi; qizil raqamlar — `GET /orders/badges/`.

### 7.5 Omborxonachi (material arizasini qabul qiluvchi tomon)

Mijoz tashkilotidagi omborxonachi — o'z tashkilotiga kelgan material arizalarini ko'rib chiqadi va materiallarni beradi.
**Ruxsat:** `change_order`. Qaysi ariza turlarini ko'rishi rol berishda "Ariza turlari" bilan belgilanadi (`/me/` dagi `orders.execute_goals`). Ariza **o'z tashkiloti, o'z hududi** va shu turlar bo'yicha keladi.
Ilova "Omborxona" ichida bu bo'limni `/me/` dagi `main.change_order` va mijoz tashkiloti (`organization_type: client`) bo'lsagina ko'rsatsin.

- **Ro'yxatlar:** `GET /api/orders/?role=barn_receiver_new` (yangi, `viewed`), `?role=barn_receiver_active` (o'zi qabul qilgan, `process` va `finished`),
  `?role=barn_receiver_archive` (`approved`, `accepted`, `canceled`, `rejected`).
- **Qabul qilish:** `POST /api/orders/{id}/accept/` → `process`.
- **Rad etish:** `POST /api/orders/{id}/reject/ {"message": "sabab (ixtiyoriy)"}` → `rejected`.
- **Materiallarni berish:** `POST /api/orders/{id}/finish/ {"items": [{"ordermaterial_id": 11, "given": 2}], "date": "2026-10-10T09:30"}` → `finished`.
  `ordermaterial_id` — arizadagi `materials[].id`; `given` kamida 1, ombordan ayriladi; qayta chaqirilsa farq hisoblanadi; `date` — olib ketish vaqti (ixtiyoriy).
  Berilgan sonni ekranda har material uchun kiritish oynasi bilan oling.
- Yangi ariza kelganda `order_new` push keladi.

### 7.6 Tasdiqlovchi (berilgan materiallarni tasdiqlovchi)

Omborxonachi materiallarni bergach (`finished`), mijoz tashkilotidagi tasdiqlovchi sonlarni tekshirib tasdiqlaydi yoki rad etadi.
**Ruxsat:** `confirm_order` (faqat `client` tashkilot xodimiga beriladi). Ilova bo'limni `/me/` dagi `orders.can_confirm: true` bo'lsagina ko'rsatsin.

- **Ro'yxatlar:** `GET /api/orders/?role=barn_agrement` (tasdiq kutayotganlar: `finished`, o'z tashkiloti va hududi), `?role=barn_agrement_archive` (o'zi ko'rib chiqqanlar).
- **Tasdiqlash:** `POST /api/orders/{id}/confirm/ {"action": "approved", "items": [{"ordermaterial_id": 11, "given": 2}]}` → `approved`.
  Tasdiqlovchi sonlarni **tuzatishi mumkin** (`given` 0 ham bo'lishi mumkin); tuzatilmasa omborxonachi bergan sonlar qoladi.
- **Rad etish:** `POST /api/orders/{id}/confirm/ {"action": "rejected"}` → `rejected`; berilgan materiallar **omborga qaytariladi**. Rad etishdan oldin tasdiq oynasi bo'lsin.
- Tasdiqlangach mijoz arizani `accepted` qiladi (7.4), akt avtomatik yaratiladi.

**To'liq zanjir (kim nima qiladi):**

| Holat | Kim | Amal |
|---|---|---|
| `viewed` | mijoz xodimi | ariza yuboradi (7.4) |
| `viewed` → `process` yoki `rejected` | omborxonachi | qabul qiladi yoki rad etadi (7.5) |
| `process` → `finished` | omborxonachi | materiallarni beradi (7.5) |
| `finished` → `approved` yoki `rejected` | tasdiqlovchi | sonlarni tasdiqlaydi yoki rad etadi (7.6); rad etilsa materiallar omborga qaytadi |
| `approved` → `accepted` | mijoz xodimi | qabul qiladi, akt yaratiladi (7.4) |
| `viewed`, `process`, `finished` → `canceled` | mijoz xodimi | bekor qiladi (7.4) |

---

## 8. Xabarlar (hujjatlar) — `/api/deeds/`

Hujjatni **ishtirokchilar** ko'radi: yaratuvchi, imzolovchi `sender`, qabul qiluvchi `receiver`, kelishuvchilar.
Turi (`status`): `document`, `svod`, `reestr`, `act`, `petition`, `service`. Imzo holatlari: `viewed` (kutilmoqda), `approved`, `rejected`.
Mobil hujjat **yaratmaydi va tahrirlamaydi**.

### 8.1 Ko'rish
- **Ro'yxat:** `GET /api/deeds/?role=` — `created`, `created_archive`, `to_sign` (menga kelgan imzo), `signed` (imzolaganlarim/rad etganlarim),
  `to_agree` (kelishuvim kutilayotgan), `agreed` (kelishganlarim). Berilmasa — o'zim ishtirok etganlar.
- **Bitta hujjat:** `GET /api/deeds/{id}/` — PDF (`file`), imzo va kelishuv holatlari, tayyor bayroqlar (`can_reject`, `my_consent_id`).
- **Ilovalar:** `GET /api/deeds/{id}/attachments/download/` — bitta fayl yoki ZIP.

### 8.2 Imzolash — FaceID (imzolovchi va qabul qiluvchi)
Imzolovchi (`sender`) yoki qabul qiluvchi (`receiver`) hujjatni **yuz tekshiruvi (FaceID)** bilan tasdiqlaydi. Yuzni suratga olish ilovadagi
**FaceID SDK** ishi; server natijani tekshirib hujjatni tasdiqlaydi. `client_secret` va boshqa kalitlar ilovada bo'lmaydi.

1. `GET /api/faceid/config/` → `{"enabled": true|false}` — `false` bo'lsa FaceID tugmasini ko'rsatmang.
2. `POST /api/faceid/sessions/` `{"deed_id": 12, "message": "izoh (ixtiyoriy)"}` → `201`:
   `{"id", "session_id", "sdk_token", "nonce", "challenges": [...], "expires_at"}` — buni **o'zgartirmasdan SDK'ga bering**.
   Shartlar: xodim shu hujjatning imzolovchisi yoki qabul qiluvchisi, uning holati `viewed`; xodimda PINFL va tug'ilgan sana bor
   (SSO orqali kirganda o'zi to'ladi, aks holda `400`). Xatolar: `503` (FaceID yoqilmagan), `404 IDENTITY_NOT_FOUND`, `429`, `502`. Daqiqasiga 10 ta.
3. SDK yuzni tekshiradi. Ilova holatni so'raydi: `GET /api/faceid/sessions/<id>/` (har 2–3 soniyada) →
   `{"status": "pending|processing|approved|failed|expired", "failure_reason", "message", "retry", "deed": {"status_sender", "status_receiver"}}`.
   - `approved` — hujjat tasdiqlandi; `GET /deeds/{id}/` ni qayta yuklang.
   - `failed` / `expired` — `message` ni ko'rsating; `retry: true` bo'lsa yangi sessiya bilan qayta urinish mumkin.
     `retry: false` bo'lsa FaceID bilan bo'lmaydi — foydalanuvchini veb'da (E-IMZO) imzolashga yo'naltiring.
   - Sessiya 10 daqiqa amal qiladi, SDK 3 martagacha urinadi.
4. **Qaror faqat serverda:** ilova "o'tdi" desa ham, hujjat shu bilan tasdiqlanmaydi.

### 8.3 Kelishish (kelishuvchi)
Kelishuvchi uchun imzo emas, oddiy **kelishish** (veb'da ham tasdiq oynasi, E-IMZO/FaceID kerak emas):
- `POST /api/deed-consents/{id}/approve/` — kelishdim (`id` — hujjatdagi `my_consent_id`).
- `POST /api/deed-consents/{id}/reject/ {"message": "..."}` — rad etish (`message` majburiy).

### 8.4 Rad etish (imzolovchi / qabul qiluvchi)
`POST /api/deeds/{id}/reject/ {"message": "..."}`.

### 8.5 Hujjatlarni qidirish (reyestr) — `/api/deed-registry/`
Veb'dagi **"Hujjatlar"** sahifasi ("Dalolatnoma, akt, reestr va hisobotlarni qidirish"). Ro'yxatdan farqi: bu yerda **ishtirokchi bo'lish shart emas**,
lekin faqat **imzolovchisi, qabul qiluvchisi yoki kelishuvchisi xodimning o'z tashkilotidan** bo'lgan hujjatlar chiqadi.
`all_organization` ruxsati bor xodim hamma tashkilotning hujjatlarini ko'radi. Faqat o'qish.
- **Tanlov ro'yxatlari:** tashkilot — `GET /api/organizations/` (o'z tashkiloti, `all_organization` bo'lsa hammasi); hudud — `GET /api/regions/` (o'z hududi, `all_region` bo'lsa hammasi).
- Ruxsat etilmagan hujjat `GET /api/deed-registry/{id}/` va ilovalarda `404` beradi.
- `GET /api/deed-registry/` — **kamida bitta filtr shart** (aks holda `400`):
  - `name` — hujjat kodi, ishtirokchining F.I.O si (bir necha so'z mumkin) yoki ariza raqami;
  - `organization` — tashkilot ID; `region` — yaratuvchi hududi ID;
  - `status` — hujjat turi (`document`, `svod`, `reestr`, `act`, `petition`, `service`);
  - `date1`, `date2` — yaratilgan sana oralig'i (`YYYY-MM-DD`).
- Javob sahifalangan (20 tadan), yangilari birinchi. Har hujjatda: kod, turi, yaratuvchi, imzolovchi va qabul qiluvchi holati, kelishuvchilar, PDF (`file`).
  Hujjat matni (`body`) va amal bayroqlari (`can_*`) **berilmaydi**.
- `GET /api/deed-registry/{id}/` — bitta hujjat; `GET /api/deed-registry/{id}/attachments/download/` — ilovalar (fayl yoki ZIP).
- Imzolash, kelishish va rad etish bu yerdan emas: hujjat xodimning o'ziga tegishli bo'lsa, ro'yxat/tafsilot (8.1) orqali.
- Ekran: qidiruv maydoni (`name`) va filtrlar (tashkilot, hudud, tur, sana); natijalar ro'yxati; filtr bo'sh bo'lsa "Qidirish uchun filtr tanlang" deb ko'rsating.

---

## 9. Ombor — texnikalar, qurilmalar va materiallar (ko'rish va boshqarish)

### 9.1 Texnikalar — `/api/technics/`
Umumiy ro'yxat uchun ruxsat: `view_technics`. Doira: tashkilot va hudud (`all_organization` / `all_region`). Xodimga texnika kategoriyalari biriktirilgan bo'lsa, faqat shular ko'rinadi.
- `GET /api/technics/` — ro'yxat; filtr: `group`, `category`, `region`, `organization`, `department`, `directorate`, `division`, `employee`, `status`;
  qidiruv: nom, inventar, seriya, MAC, IP.
- `status`: `free` (bo'sh), `active`, `repair`, `defect`. Javobda `extra_devices` — biriktirilgan qo'shimcha qurilmalar.
- **Texnikalarim** (ruxsatsiz, hamma xodim): `GET /api/spa/warehouse/technics/mine/` → `{"count", "is_boss", "results": [...], "employees_without_technics": [...]}`, 20 tadan (`?page=`).
  Oddiy xodimda — o'ziga biriktirilgan texnikalar; `boss_employee` bo'lsa — o'z departamentidagi hamma texnika va texnikasi yo'q xodimlar.
  Bu ro'yxat `view_technics` talab qilmaydi (umumiy `GET /api/technics/` talab qiladi).
- `GET /api/technics/{id}/` — tafsilot.

**Texnikani boshqarish** (mobilda bor; har amalga o'z ruxsati kerak, server doirani ham tekshiradi — tashkilot va hudud):

| Amal | So'rov | Ruxsat |
|---|---|---|
| **Qo'shish** | `POST /api/technics/` — majburiy: `group`, `category`, `organization`, `name`; ixtiyoriy: `parametr`, `inventory`, `serial`, `mac`, `ip`, `year`, `price`, `address`, `is_online` | `add_technics` |
| **Tahrirlash** | `PATCH /api/technics/{id}/` — `category`, `organization`, `name`, `parametr`, `inventory`, `serial`, `mac`, `ip`, `year`, `price`, `address`, `status`, `is_online` (guruh va hudud o'zgarmaydi) | `change_technics` |
| **Xodimga biriktirish** | `POST /api/technics/{id}/assign/ {"employee": <id>}` — bo'lim, boshqarma, bo'linma xodimdan olinadi, holat `active` | `change_technics` |
| **Strukturaga biriktirish** | `POST /api/technics/{id}/assign/ {"department": id, "directorate": id, "division": id}` (butun zanjirni yuboring) | `change_technics` |
| **Bo'shatish** | `POST /api/technics/{id}/unassign/` — xodim va struktura olib tashlanadi, holat `free` | `change_technics` |
| **O'chirish** | `DELETE /api/technics/{id}/` — bazadan o'chirilmaydi, **arxivlanadi** (ro'yxatda ko'rinmaydi) | `delete_technics` |
| QR rasm | `GET /api/technics/{id}/qr/` — PNG | `view_technics` |

- Hudud yangi texnikaga **xodimdan olinadi**. `all_organization` bo'lmasa faqat o'z tashkilotiga qo'sha oladi.
- Bir tashkilotda faol seriya takrorlanmaydi (`B/N` bundan mustasno) — `400`; xabarni ko'rsating.
- Xodimga biriktirish uchun xodimlar ro'yxati: `GET /api/spa/warehouse/employees/?organization=<id>&region=<id>` → `{"results": [{"id", "text"}]}`.
- Qo'shish oynasidagi ro'yxatlar (6-bo'lim): `groups`, `categories`, `organizations`.
- O'chirish va bo'shatishdan oldin **tasdiq oynasi** bo'lsin. Har amaldan keyin javobda yangilangan texnika qaytadi.
- Texnikani **QR skaner** orqali ham ochib shu amallarni bajarish mumkin (9.4).

### 9.2 Qurilmalar (qo'shimcha qurilmalar) — `/api/structures/`
Veb'dagi "Qurilmalar" sahifasi. Qurilma — texnikaga biriktiriladigan qo'shimcha uskuna (monitor, printer va hokazo).
- **Ikki joyda ko'rinadi:**
  1. **Texnika kartasi ichida** (`extra_devices`) — texnikani ko'ra oladigan hamma xodimga, ruxsat kerak emas.
  2. **Alohida "Qurilmalar" ro'yxati** (`GET /api/structures/`) — faqat **`change_technics`** ruxsati bor xodimga. Faqat `view_technics` yetmaydi (`403`).
     Ilova "Qurilmalar" bo'limini `/me/` dagi `main.change_technics` bo'lsagina ko'rsatsin.
- Filtr: `category`, `organization`, `region`, `technics`, `status`; qidiruv `search` (nom, inventar, seriya, yil). Javobda: nomi, kategoriya, inventar, seriya, holat (`status_display`), biriktirilgan texnika (`technics`, `technics_name`).
  Texnika egasi (`technics_employee_name`) kerak bo'lsa — veb ishlatadigan `GET /api/spa/warehouse/structures/` (ruxsat va filtrlar shunday).

**Qurilmalarni boshqarish** (mobilda bor; ruxsatlar texnika ruxsatlari bilan):

| Amal | So'rov | Ruxsat |
|---|---|---|
| **Qo'shish** | `POST /api/structures/` — majburiy: `category`, `organization`, `name`; ixtiyoriy: `parametr`, `inventory`, `serial`, `price` (>= 0), `year` | `add_technics` |
| **Tahrirlash** | `PATCH /api/structures/{id}/` | `change_technics` |
| **Texnikaga biriktirish** | `POST /api/structures/{id}/assign/ {"technics": <id>}` — texnika sizning doirangizda, bir tashkilotdan va qurilma bo'sh bo'lishi kerak | `change_technics` |
| **Texnikadan ajratish** | `POST /api/structures/{id}/unassign/` (`{"technics": id}` ixtiyoriy); allaqachon bo'sh bo'lsa `400` | `change_technics` |
| **O'chirish** | `DELETE /api/structures/{id}/` — arxivlanadi; texnikaga biriktirilgan bo'lsa avval ajratiladi | `delete_technics` |

- Seriya tashkilot ichida takrorlanmaydi. Hudud xodimdan olinadi.
- Qo'shish oynasidagi ro'yxatlar: `structure-categories` (qurilma kategoriyasi), `organizations`.
- Ilova "Qurilmalar" bo'limini va tugmalarni `/me/` dagi ruxsatlarga qarab ko'rsatadi: ro'yxat va tahrirlash — `change_technics`, qo'shish — `add_technics`, o'chirish — `delete_technics`.
- Doira — tashkilot va hudud (`all_organization` / `all_region` bilan kengayadi).

### 9.3 Materiallar — `/api/materials/`
Ruxsat: `view_material`. Ko'rinish: o'z tashkilotining faol, soni 0 dan ko'p materiallari; `all_material_employee` bo'lsa moddiy javobgar xodimlarniki,
aks holda o'zi va unga biriktirilgan xodimlarniki.
- `GET /api/materials/` — ro'yxat: nomi, kategoriya, soni (qoldiq), birlik, narxi, rasmi; filtr: `employee`, `category`, `unit`; `search` — nomi, kodi yoki narxi bo'yicha (narx boshidan: `1500`, `1500,50`).
- `GET /api/materials/{id}/` — tafsilot.

**Materialni boshqarish** (mobilda bor; har amalga o'z ruxsati kerak):

| Amal | So'rov | Ruxsat |
|---|---|---|
| **Qo'shish** | `POST /api/materials/` (`multipart`) — majburiy: `name`; ixtiyoriy: `category`, `unit`, `number`, `code`, `price` (>= 0), `year`, `image` (JPG/PNG, 5 MB gacha). Kategoriya o'z tashkilotiniki bo'lishi kerak | `add_material` |
| **Tahrirlash** | `PATCH /api/materials/{id}/` (rasm bilan `multipart`) — o'zgarishlar harakat jurnaliga yoziladi | `change_material` |
| **Xodimga berish** | `POST /api/materials/give/ {"employee_id": 5, "items": [{"material_id": 3, "number": 2}]}` — bir tranzaksiya: biror material xato bersa hech biri saqlanmaydi | `change_material` |
| **Sarflash** | `POST /api/materials/service/ {"material_id": 3, "give_number": 1, "body": "izoh"}` — soni kamayadi, jurnalga yoziladi | `material_service` |
| **O'chirish** | `DELETE /api/materials/{id}/` — bazadan o'chirilmaydi, **arxivlanadi** (jurnalga yoziladi) | `delete_material` |

- **Berish qoidalari:** xodim **bir tashkilotdan** bo'lishi kerak (`400`); material xodimning o'ziga allaqachon tegishli bo'lmasin; omborda yetarli son bo'lsin (xato matnida "bor: N" keladi — ko'rsating).
  Xodimlar ro'yxati: `GET /api/spa/warehouse/employees/?organization=<id>&region=<id>` → `{"results": [{"id", "text"}]}`.
- **Sarflash qoidalari:** faqat o'z tashkiloti; material egasi, unga biriktirilgan xodim yoki `all_material_employee` bo'lgan xodim sarflay oladi. `material_service` ruxsati **faqat `worker`** xodimiga beriladi (mijozda yo'q).
- Qo'shish oynasidagi ro'yxatlar (6-bo'lim): `material-categories`, `units`. O'chirishdan oldin **tasdiq oynasi** bo'lsin.

### 9.4 QR skaner — `POST /api/scan/`

Skaner ilovaning pastki menyusida **o'rtadagi tugma** (1.3).

Ilova kamera bilan QR'ni o'qiydi va **matnini** yuboradi: `{"text": "https://<server>/technics/12/"}`. Server matnni tanib, tegishli ma'lumotni qaytaradi
(saytdagi QR sahifalari bilan bir xil ma'lumot). Faqat o'z domenimizdagi havolalar qabul qilinadi. Daqiqasiga 60 ta so'rov.

| QR | Qayerda | Matn | `type` |
|---|---|---|---|
| Texnika | qurilmaga yopishtirilgan QR | `https://<server>/technics/<id>/` | `technics` |
| Hujjat | hujjat PDF'ining pastidagi QR | `https://<server>/deed/status/<kod>/<id>/` | `deed` |

Boshqa QR (begona domen, boshqa matn) — `400 {"detail": "Bu QR kod IVC tizimiga tegishli emas", "type": "unknown"}`: ilova "Bu IVC QR kodi emas" deb ko'rsatsin.
Topilmasa (o'chirilgan texnika, noto'g'ri kod) — `404`.

**Texnika** — kartani **har qanday kirgan xodim** ko'ra oladi:
```json
{"type": "technics",
 "technics": {"id": 12, "name": "Kompyuter", "category_name": "...", "parametr": "...", "inventory": "INV-7", "serial": "SN-1",
              "mac": "...", "ip": "...", "employee": 5, "employee_name": "...", "status": "active", "status_display": "Aktiv",
              "qr_code": "/media/qk/technics_12.png", "extra_devices": [{"id": 3, "name": "Monitor", "...": "..."}]},
 "can_edit": true,
 "detail": {"id": 12, "organization": 2, "region": 4, "...": "..."}}
```
- `can_edit` — xodimda `change_technics` ruxsati bor **va** texnika uning tashkiloti va hududi doirasida. Tahrirlash, biriktirish va bo'shatish tugmalarini faqat shunda ko'rsating.
- `detail` — to'liq ma'lumot (`GET /technics/{id}/` bilan bir xil), faqat `can_edit: true` bo'lganda keladi; tahrirlash oynasini to'ldirish uchun.

**`can_edit: true` bo'lganda skanerdan keyin mobilda mumkin bo'lgan amallar** (hammasi mavjud `/technics/` endpointlari, server ruxsatni qayta tekshiradi: `403`/`404`):
1. **Tahrirlash:** `PATCH /api/technics/{id}/` — `name`, `category`, `parametr`, `inventory`, `serial`, `mac`, `ip`, `year`, `price`, `address`, `status`, `is_online`
   (guruh va hudud o'zgarmaydi; bir tashkilotda faol seriya takrorlanmaydi, `B/N` bundan mustasno).
2. **Xodimga biriktirish:** avval xodimlar ro'yxati — `GET /api/spa/warehouse/employees/?organization=<detail.organization>&region=<detail.region>` → `{"results": [{"id", "text"}]}`;
   keyin `POST /api/technics/{id}/assign/ {"employee": <id>}` — bo'lim/boshqarma/bo'linma xodimdan olinadi, holat `active` bo'ladi.
   Strukturaga biriktirish: `{"department": id, "directorate": id, "division": id}` (butun zanjirni yuboring).
3. **Bo'shatish:** `POST /api/technics/{id}/unassign/` — xodim va struktura olib tashlanadi, holat `free` bo'ladi. Bo'shatishdan oldin tasdiq oynasi bo'lsin.
4. **O'chirish** (agar xodimda `delete_technics` ham bo'lsa): `DELETE /api/technics/{id}/` — texnika arxivlanadi (9.1). Tasdiq oynasi bo'lsin.

Har amaldan keyin javobda yangilangan texnika qaytadi — kartani shu bilan yangilang.

**Hujjat** — QR orqali **tekshirish** hammaga ochiq (hujjat kodi taxmin qilib bo'lmaydigan, 10 belgi):
```json
{"type": "deed",
 "deed": {"id": 7, "code": "AB12CD34EF", "kind": "document", "kind_display": "Dalolatnoma", "date_creat": "...", "message_user": "...",
          "created_by": {"full_name": "...", "organization_name": "..."},
          "signers": [{"role": "sender", "person": {"full_name": "...", "organization_name": "..."}, "status": "approved",
                       "status_display": "Tasdiqlandi", "date": "...", "message": "..."}],
          "consents": [{"person": {"...": "..."}, "status": "viewed", "status_display": "Kutilmoqda", "date": null, "message": null}],
          "file": null},
 "can_open": false}
```
- Ilova ekranda hujjat kodi, turi, kim yaratgani, imzolovchilar va kelishuvchilar holatini ko'rsatadi.
- `can_open: true` — xodim hujjat ishtirokchisi (yoki `all_organization`): `file` (PDF) to'ldiriladi va ilova to'liq ochish uchun `GET /api/deeds/{id}/` ga o'tadi
  (imzolash va kelishish — 8-bo'lim). Ishtirokchi bo'lmaganga PDF **berilmaydi**, faqat holat.

> QR matnidagi domen serverdagi `SITE_BASE_URL` dan olinadi. Domen almashsa, **yangi QR'lar** yangi domen bilan chiqadi; eski qog'ozdagi QR'lar
> eski domenga ishora qiladi — eski domen serverda `ALLOWED_HOSTS` da qolsa, skaner ularni ham taniydi.

---

## 10. Xodimlar — `/api/employees/`

Ruxsatlar: ko'rish `view_employee`, qo'shish `add_employee`, tahrirlash `change_employee`, o'chirish `delete_employee`.
Faqat o'z tashkiloti (`all_organization` bo'lsa hammasi). Hudud — `all_region` bo'lmasa faqat o'z hududi.

- **Ro'yxat:** `GET /api/employees/` — filtr: `organization`, `department`, `directorate`, `division`, `region`, `rank`; qidiruv: F.I.O yoki PINFL.
  Javobda: `full_name`, `rank_name`, `organization_name`, `department_name`, `phone` (ichki raqam), `sso_phone` (OneID'dan kelgan raqam), `pinfl`.
  **PINFL'ni ekranda ko'rsatmaslikni tavsiya qilamiz** (shaxsiy ma'lumot); qidiruv PINFL bo'yicha ishlayveradi.
  `sso_phone` xodim SSO bilan kirgandan keyin to'ladi, shuning uchun bo'sh bo'lishi mumkin. Ro'yxatda tepada `phone`, pastda `sso_phone` ko'rsatish qabul qilingan.
- **Tafsilot:** `GET /api/employees/{id}/`.
- O'chirilgan (faolsizlantirilgan) xodimlar ro'yxatda chiqmaydi.

**Qo'shish** (`add_employee`) — ikki usul, veb'dagi shaklda ham ikkalasi bor:
1. **PINFL bo'yicha (tavsiya):** `POST /api/spa/people/employees/gateway-create/ {"pinfl": "<14 xonali>"}` → `201 {"detail": "..."}`.
   Server Gateway'dan F.I.O va ish joyini oladi, tashkilot va bo'limni o'zi topadi, xodimni yaratadi. Foydalanuvchi parolsiz, kirish SSO orqali.
   Xatolar `400 {"detail": "..."}` (matnni ko'rsating): "Bu PINFL allaqachon ro'yxatda bor", "Gatewayda ish joyi topilmadi", "Tizimda tashkilot topilmadi"; Gateway ishlamasa `502`.
2. **Qo'lda:** `POST /api/employees/` — majburiy: `first_name`, `last_name`, `organization`; ixtiyoriy: `pinfl` (takrorlanmaydi), `father_name`, `department`, `directorate`,
   `division`, `rank`, `phone`. Javobda `id`, `username`. Bo'lim/boshqarma/bo'linma zanjiri va tashkilotga mosligi tekshiriladi.

**Tahrirlash** (`change_employee`) — `PATCH /api/employees/{id}/`: `first_name`, `last_name`, `father_name`, `pinfl` (14 xonali, takrorlanmaydi), `department`, `directorate`, `division`, `rank`, `phone`.
Tashkilot o'zgarmaydi. Zanjir mosligi tekshiriladi. Joylashuv o'zgarsa xodimdagi texnikalar uchun `technics_action`: `release` (standart — bo'shatiladi), `with` (birga ko'chadi), `stay` (eski joyda qoladi).
**Ilova bu tanlovni foydalanuvchiga ko'rsatishi kerak**, aks holda texnikali xodimni ko'chirish noaniq qoladi.

**O'chirish** (`delete_employee`) — `DELETE /api/employees/{id}/` → `204`: xodim yozuvi o'chirilmaydi, faqat **faolsizlantiriladi** (kirish, bot va push to'xtaydi;
tashkilot, bo'lim, boshqarma, bo'linma, lavozim va hudud tozalanadi; arizalari, hujjatlari, materiallari saqlanadi). **O'zini o'chirib bo'lmaydi** (`400`) —
o'z qatorida "O'chirish" tugmasini ko'rsatmang. O'chirishdan oldin **tasdiq oynasi** bo'lsin.

**Mobilda yo'q:** xodimga **ruxsat (rol) berish** (`/employees/{id}/permissions/`, `permission_employee`) va Excel eksport — veb'da.

---

## 11. Chat — `/api/chat/...` va WebSocket

Saytdagi chat bilan bir xil: shaxsiy suhbat, guruh, "AI yordamchi", "Saqlangan xabarlar". Barcha so'rovlar `Bearer` token bilan; xatolar `{"detail": "..."}`.
Xabar yuborish va tahrirlash **HTTP orqali**; WebSocket faqat serverdan jonli hodisalar uchun.

### 11.1 REST
| Metod va yo'l | Vazifasi |
|---|---|
| `GET /api/chat/conversations/` | Suhbatlar: `id`, `kind` (`direct`, `group`, `ai`, `saved`), `title`, `last_message`, `last_message_at`, `unread_count`, `online`, `last_seen`, guruhda `member_count`, `is_admin` |
| `GET /api/chat/contacts/?q=` | Yangi suhbat uchun xodimlar (istalgan tashkilotning faol xodimlari; 50 tagacha) |
| `POST /api/chat/open/` `{"target": <xodim id> \| "ai" \| "saved"}` | Suhbat ochish/topish → `{"conversation_id"}` |
| `POST /api/chat/groups/` `{"name", "members": [id,...]}` | Guruh yaratish (o'zingizdan tashqari kamida 2 a'zo) |
| `GET /api/chat/conversations/{id}/messages/?page=1` | Xabarlar, 30 tadan. `page=1` — eng yangilari; sahifa ichida eskidan yangiga. `has_next_page` — yana eskilari bor. Ochilganda o'qilmaganlar "o'qildi" bo'ladi |
| `POST /api/chat/conversations/{id}/send/` `{"body": "..."}` yoki `multipart` (`body`, `attachment`) | Xabar yuborish → `{"message": {...}}`. Matn 4000 belgigacha; fayl: jpg/png, pdf, word, excel, 15 MB gacha |
| `POST /api/chat/messages/{id}/edit/` `{"body"}` | Faqat o'z xabarini tahrirlash |
| `POST /api/chat/messages/{id}/delete/` | Faqat o'z xabarini o'chirish (`is_deleted: true`, `body: ""`) |
| `POST /api/chat/conversations/{id}/hide/` | Suhbatni faqat o'zim uchun yashirish |
| `GET /api/chat/conversations/{id}/members/` | Guruh a'zolari: `is_admin`, `is_creator`, `is_me`; `am_admin`, `am_creator` |
| `POST /api/chat/conversations/{id}/members/add/` `{"members": [id]}` | A'zo qo'shish (guruh admini) |
| `POST /api/chat/conversations/{id}/members/{member_id}/remove/` | Chiqarish (o'zi chiqishi mumkin; admin oddiy a'zoni; yaratuvchi adminlarni) |
| `POST /api/chat/conversations/{id}/members/{member_id}/admin/` `{"is_admin": true}` | Admin tayinlash/olish (faqat yaratuvchi) |
| `GET /api/chat/unread-count/` | `{"unread_count": n}` |
| `POST /api/chat/ping/` | "Onlayn" holatini yangilash (`204`); WebSocket ulanmagan paytda har ~30 soniyada |

Xabar ko'rinishi: `{"id", "conversation_id", "sender_id", "sender_name", "is_ai", "body", "attachment_url", "attachment_name", "is_image", "is_edited", "is_deleted", "read_at", "date_creat"}`.
Suhbatda ishtirok etmasangiz — `403`.

### 11.2 WebSocket (jonli hodisalar)
`wss://<server>/ws/chat/?token=<access>` — `access` token so'rov parametrida.
- Token yaroqsiz yoki eskirgan bo'lsa ulanish **4401** kodi bilan yopiladi: tokenni yangilab (`/api/token/refresh/`) qayta ulaning. Access 1 soatda tugaydi, uzoq ulanishda ham shunday qiling.
- Ulanishni tirik tutish uchun har ~30 soniyada `{"type": "ping"}` yuboring.
- Serverdan keladigan hodisalar:
  - `{"type": "message", "message": {...}}` — yangi xabar (o'zingiz yuborganingiz ham keladi);
  - `{"type": "edit", "message": {...}}` va `{"type": "delete", "message": {...}}`;
  - `{"type": "read", "conversation_id", "reader_id", "message_ids": [...]}` — o'qildi (✓✓);
  - `{"type": "group_update", "conversation_id"}` — guruh a'zolari/adminlari o'zgardi (ro'yxatni qayta so'rang).
- Ulanish uzilsa, qayta ulangach `GET /conversations/` va ochiq suhbat xabarlarini qayta so'rang.
- Ilova yopiq paytda yangi xabar haqida bildirishnoma — push orqali (12-bo'lim).

---

## 12. Bildirishnomalar va push

### 12.1 Bildirishnomalar markazi — `/api/notifications/`
Xodimga yuborilgan hamma voqealar (ariza, hujjat, chat) tarixi. Bir suhbatdagi bir nechta o'qilmagan chat xabari **bitta qatorga** guruhlanadi (`count`). 3 oydan eskilari tozalanadi.
- `GET /api/notifications/?kind=order|deed|meeting|chat|system&unread=1&page=` — ro'yxat (20 tadan); javobda `unread` — jami o'qilmagan.
- `GET /api/notifications/unread-count/` → `{"unread": N}` (qo'ng'iroq belgisi uchun).
- `POST /api/notifications/{id}/read/` — bittasini o'qilgan qilish.
- `POST /api/notifications/read-all/` `{"kind"?: "order"}` → `{"updated": N, "unread": 0}`.

Bildirishnoma: `{id, kind, title, body, url, count, is_read, date_creat}`. `url` — saytdagi yo'l; mobil uni o'z ekraniga moslaydi.

### 12.2 Push
Server yangi ariza, ariza holati, hujjat imzo/kelishuv kutayotgani va yangi chat xabari haqida xodimning qurilmalariga push yuboradi.

**Ilova tomonida:**
1. Kirgandan keyin push tokenini oling va yuboring: `POST /api/devices/ {"token": "<token>", "device_name": "Pixel 7", "app_version": "1.0.3"}`
   (`201` yangi, `200` yangilandi). Token yangilanganda yana yuboring. Qurilma boshqa xodimga o'tsa, token yangi xodimga ko'chiriladi.
2. Chiqishda: `POST /api/auth/logout/ {"refresh": "...", "fcm_token": "<token>"}` (yoki faqat tokenni o'chirish: `POST /api/devices/unregister/ {"token": "..."}`).
3. Bildirishnoma kelganda ma'lumotni `GET /api/orders/{id}/`, `/api/deeds/{id}/`, `/api/chat/conversations/` orqali yangilang.

**Xabar tarkibi:** `notification` (`title`, `body`) va navigatsiya uchun `data` (barcha qiymatlar satr):

| `data.type` | Qachon | Qo'shimcha maydon | Ochiladigan ekran |
|---|---|---|---|
| `order_new` | Bajaruvchiga (ATM) yoki omborxonachiga yangi ariza keldi | `order_id` | Yangi arizalar (`?role=receiver_new` / `barn_receiver_new`) |
| `order_status` | Yuboruvchining arizasi holati o'zgardi | `order_id`, `status` | Ariza tafsiloti |
| `order_assign` | Sizga ariza biriktirildi | `order_id` | Faol arizalar |
| `deed_sign` | Hujjat imzolashga yuborildi | `deed_id` | Hujjat (`?role=to_sign`) |
| `deed_agree` | Hujjat kelishishga yuborildi | `deed_id` | Hujjat (`?role=to_agree`) |
| `chat` | Yangi chat xabari | `conversation_id` | Suhbat |
| `general` | Boshqa | — | — |

`data.url` — saytdagi manzil (ma'lumot uchun), `data.tag` — hodisaning unikal belgisi (bir xil `tag` bildirishnomani almashtiradi).

---

## 13. Android va iOS farqlari

| Mavzu | Android | iOS |
|---|---|---|
| Brauzer orqali kirish (B variant) | Chrome Custom Tab, `intent-filter` (`ivsapp://auth`) | `ASWebAuthenticationSession`, URL scheme `ivsapp` |
| Tokenlarni saqlash | Keystore / EncryptedSharedPreferences | Keychain |
| Push | FCM; bildirishnoma kanali ID **`ivs_default`** (server shu kanalga yuboradi) | FCM orqali APNs (Firebase iOS SDK); **serverda iOS sozlamalari hali yo'q — 14-bo'limga qarang** |
| FaceID SDK | FaceID jamoasining Android SDK'si | iOS SDK'si hali chiqmagan (FaceID jamoasi bilan kelishiladi) |
| `app/config` | `platform=android` | `platform=ios` |

---

## 14. Hali bajarilishi kerak bo'lgan ishlar

**Server tomonida (iOS chiqishidan oldin):**
1. **Push — iOS:** server FCM xabariga hozir faqat `android` bloki (`channel_id`) qo'shadi. iOS uchun `apns` bloki (ovoz, badge, ustuvorlik) kerak; Firebase'da APNs kaliti ulanishi shart. Qurilmalar jadvalida `platform` maydoni yo'q — iOS/Android ajratish uchun qo'shish tavsiya etiladi.
2. **Ilova versiyasi:** `ANDROID_MIN_VERSION`, `ANDROID_LATEST_VERSION`, `ANDROID_UPDATE_URL` sozlamalari **bitta** to'plam; iOS uchun alohida versiya va App Store havolasi hozircha yo'q.

**FaceID:**
3. Mobil SDK tafsilotlari (Android va iOS) FaceID jamoasidan olinishi kerak; iOS ilovasi hali chiqmagan.
4. Hujjatni FaceID bilan imzolashning **yuridik kuchi** E-IMZO bilan teng ekani tasdiqlanishi kerak.
5. FaceID webhook manzili internetdan ochiq bo'lishi kerak (`/api/v1/faceid/webhook/`; brauzerda `GET` qilsangiz `405` chiqishi normal).

**2-versiya (hozircha mobilda yo'q):** Zoom uchrashuvlari.

**QR skaner:** kamera orqali o'qishni ilovaning o'zi qiladi (Android — CameraX/ML Kit, iOS — AVFoundation/VisionKit); server faqat QR **matnini** qabul qiladi (9.4).
