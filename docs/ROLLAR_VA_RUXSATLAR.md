# Rol, ruxsatlar va tizim funksiyalari — to'liq qo'llanma (mobil ilova uchun)

Bu hujjat uch savolga javob beradi:
1. Har bir ruxsat **qayerda ishlatiladi**, **kimga kerak** va **kim foydalana oladi**.
2. Tizimda **qanday funksiyalar bor** va ularning qaysilari mobil API'da bor.
3. Ilova ekran va tugmalarni qanday qurishi kerak.

Aniq endpoint maydonlari — `ANDROID_API.md` va Swagger (`/swagger/`).

---

## 1. Asosiy qoidalar

- Tizimda alohida "rol" modeli **yo'q**. Xodimga **ruxsatlar (permission)** to'plami beriladi. "Rol berish" oynasi — shu ruxsatlarni belgilash.
- Ilova ekranlarini `GET /api/v1/me/` javobiga qarab quradi: `organization_type`, `orders` bayroqlari, `permissions` ro'yxati (`main.view_material` ko'rinishida).
- `is_superuser: true` bo'lsa hamma narsa ochiq.
- **Ilovada yashirish — faqat qulaylik. Himoya serverda:** server har so'rovda ruxsatni o'zi tekshiradi (`403` — ruxsat yo'q, `404` — yozuv yo'q yoki sizga ko'rinmaydi).
- `/me/` ni ilova ochilganda va token yangilanganda qayta so'rang (ruxsatlar o'zgarishi mumkin).
- Ko'rish doirasini (tashkilot, hudud, ishtirokchilik) server o'zi cheklaydi. Ilova qo'shimcha filtr qilmaydi.

### Tashkilot turi (`organization_type`)

| Tur | Kim | Nima qiladi |
|---|---|---|
| `worker` | ATM vakili (xizmat ko'rsatuvchi tashkilot) | Arizalarni bajaradi, texnika, hujjat va hisobotlar bilan ishlaydi |
| `client` | Mijoz tashkilot | ATM'ga ariza yuboradi, o'z omborxonasiga material arizasi beradi, o'z materiallarini ko'radi |

Ayrim ruxsatlar faqat bir turdagi xodimga beriladi (quyida "Kimga beriladi").

### Bog'liqliklar

- `view_*` olib tashlansa, bog'liqlari ham olinadi:
  - `view_technics` → `add_technics`, `change_technics`, `delete_technics`
  - `view_material` → `add_material`, `change_material`, `delete_material`, `material_service`, `all_material_employee`
  - `view_employee` → `add_employee`, `change_employee`, `delete_employee`
  - `view_meeting` → `add_meeting`, `delete_meeting`
- **SUPER ruxsatlar** (`all_organization`, `all_region`, `permission_employee`, `all_material_employee`) — faqat o'zida shu ruxsat bor xodim bera oladi.

---

## 2. Ruxsat talab qilinmaydigan funksiyalar (hamma xodim)

Employee profili bo'lgan har bir kirgan xodim:
- Kirish, `/me/`, profil, bildirishnomalar markazi, push-qurilma ro'yxatdan o'tkazish.
- **ATM arizasi yuborish** va o'z arizalarini kuzatish (ariza turi `send_goals` da bo'lsa), baho bilan qabul qilish yoki bekor qilish.
- **Mijoz: omborxonaga material arizasi** (`can_create_material_order`, ariza turi `material_goals` da), savat, o'z arizalarini kuzatish, qabul qilish.
- Hujjatlarda: o'zi yaratgan, imzolovchi, qabul qiluvchi yoki kelishuvchi bo'lgan hujjatlarni ko'rish; rad etish; kelishuvchi sifatida `approve` / `reject`.
- **Hujjatlar reyestri** (`deed-registry`): kamida bitta filtr bilan hamma hujjatni ko'rish (faqat o'qish).
- "Texnikalarim": o'ziga biriktirilgan texnikalar. QR kartasi.
- Chat (shaxsiy, guruh, AI yordamchi, saqlangan xabarlar).
- Ma'lumotnomalar (tashkilotlar, hududlar, bo'limlar, lavozimlar va hokazo) — faqat o'qish.

---

## 3. Ruxsatlar: qayerda ishlatiladi, kimga kerak, kim foydalana oladi

Har bir ruxsat uchun: **Nima** — ma'nosi; **Qayerda** — sayt ekrani va API; **Kimga kerak** — odatda qaysi lavozim; **Kimga beriladi** — tashkilot turi bo'yicha cheklov.

### 3.1 Ariza

**`add_order` — Ariza yaratish**
- **Nima:** boshqa xodim nomidan ariza yuborish.
- **Qayerda:** `POST /orders/` da `sender` maydoni; `orders.can_create_on_behalf`; "nomidan yuborganlarim" ro'yxati (`?role=sender_user`).
- **Kimga kerak:** operator, kotib — boshqa xodimlar nomidan ariza kiritadiganlar.
- **Kimga beriladi:** faqat `worker`. Oddiy ariza yuborish uchun bu ruxsat kerak emas.

**`change_order` — Ariza bajarish**
- **Nima:** kelgan arizani qabul qilib bajarish.
- **Qayerda:**
  - ATM arizasi (`worker`): yangi arizalar (`?role=receiver_new`), qabul qilish (`/accept/`), rad etish, yakunlash (`/finish/` — materiallarni ombordan ayirish), mavjud materiallar (`available-materials`), ijrochilar (`assignees`). Qaysi ariza turlarini bajarishi `execute_goals` (rol berishda "Ariza turlari").
  - Omborxona arizasi (mijoz tomonda omborxonachi): `?role=barn_receiver_new`, qabul/rad, materiallarni berish.
  - "Hisobotlar" menyusi va Akt hisoboti.
  - Material harakati: sarf hisoboti (`worker`) bilan bog'liq.
- **Kimga kerak:** ATM ijrochisi (texnik), omborxonachi.
- **Kimga beriladi:** hammaga. `execute_goals` bo'sh bo'lsa, ijro qiladigan tur yo'q.

**`confirm_order` — Arizani tasdiqlash**
- **Nima:** omborxonadan bajarilgan material arizasini tasdiqlash (berilgan sonlarni tuzatish yoki rad etish).
- **Qayerda:** `POST /orders/{id}/confirm/`; `?role=barn_agrement` va `barn_agrement_archive` ro'yxatlari; `orders.can_confirm`.
- **Kimga kerak:** mijoz tashkilotidagi tasdiqlovchi (rahbar yoki mas'ul).
- **Kimga beriladi:** faqat `client` (worker emas).

### 3.2 Hujjat (dalolatnoma)

**`add_deed` — Hujjat yaratish**
- **Nima:** hujjat (dalolatnoma, akt, svod, reestr, talabnoma, sarf) yaratib imzolashga yuborish.
- **Qayerda:** `POST /deeds/`; "Hisobotlar" ning "Dalolatnoma" bo'limi (xodimning kamida bitta shartnomasi ham bo'lishi kerak).
- **Kimga kerak:** hujjat tayyorlovchi ATM xodimi.
- **Kimga beriladi:** faqat `worker`.

**`change_deed` — Hujjatni tahrirlash**
- **Nima:** yaratuvchiga o'z hujjatini tahrirlash ruxsatini yoqish/o'chirish (`user_edit`).
- **Qayerda:** `POST /deeds/{id}/toggle-user-edit/`.
- **Kimga kerak:** hujjatlar bo'yicha mas'ul, rahbar.
- **Kimga beriladi:** faqat `worker`.

> Imzolash va kelishish uchun alohida ruxsat yo'q: hujjatda imzolovchi (`sender`/`receiver`) yoki kelishuvchi qilib tanlangan xodim o'zi javob beradi. Mobil API'da imzolash (Face ID) hozircha yo'q.

### 3.3 Ko'rish doirasi (SUPER)

**`all_organization` — Barcha tashkilotlarni ko'rish**
- **Nima:** o'z tashkilotidan tashqari boshqa tashkilot ma'lumotini ko'rish.
- **Qayerda:** xodimlar, texnika, materiallar, arizalar, hujjatlar, statistika, tashkilot ma'lumotnomalari, rol berish (boshqa tashkilot xodimiga).
- **Kimga kerak:** bosh rahbariyat, markaziy mas'ullar.
- **Kimga beriladi:** faqat `worker`; faqat o'zida bor odam bera oladi. Bosh sahifada "Barcha tashkilotlar" tugmasi faqat superuserga chiqadi.

**`all_region` — Barcha hududlarni ko'rish**
- **Nima:** o'z hududidan tashqari hududlarni ko'rish.
- **Qayerda:** shu ro'yxatlar, statistika va hisobotlarda hudud filtri.
- **Kimga kerak:** respublika miqyosidagi rahbarlar.
- **Kimga beriladi:** faqat `worker`.

> Ikkalasi ham bo'lmasa, server natijani xodimning o'z tashkiloti va hududi bilan cheklaydi.

### 3.4 Texnika

**`view_technics` — Texnikalarni ko'rish**
- **Nima:** texnikalar ro'yxati va kartasi.
- **Qayerda:** "Texnika va uskunalar" menyusi (`GET /technics/`), QR, Excel eksport, bosh sahifadagi texnika bloki. Faqat xodimga biriktirilgan texnika kategoriyalari ko'rinadi (rol berishda "Texnika kategoriyasi").
- **Kimga kerak:** texnik xodim, ombor mas'uli.
- **Kimga beriladi:** hammaga.

**`add_technics`, `change_technics`, `delete_technics` — qo'shish, tahrirlash, o'chirish**
- **Qayerda:** `POST /technics/` (qo'shish); `PATCH` va `assign`/`unassign` (tahrirlash, xodimga biriktirish va bo'shatish); `DELETE` (arxivlash). **Qo'shimcha qurilmalar** (`/structures/`) ham shu ruxsatlar bilan: ko'rish/tahrirlash — `change_technics`, qo'shish — `add_technics`, o'chirish — `delete_technics`.
- **Kimga kerak:** texnika bo'yicha mas'ul.
- **Kimga beriladi:** hammaga; `view_technics` bo'lishi shart.

### 3.5 Material

**`view_material` — Materiallarni ko'rish**
- **Nima:** materiallar ro'yxati, summa, harakatlar jurnali, material hisoboti.
- **Qayerda:** "Materiallar" menyusi, `GET /materials/`, `material-movements`, `materials/report/`, Excel eksport, bosh sahifadagi materiallar bloki, mijoz uchun omborxona.
- **Kimga kerak:** omborxonachi, material mas'uli.
- **Kimga beriladi:** hammaga. Ko'rinish doirasi: o'z tashkiloti, o'zining va biriktirilgan xodimlarning materiallari.

**`add_material`, `change_material`, `delete_material`**
- **Qayerda:** `POST /materials/` (qo'shish, rasm bilan), `PATCH` (tahrirlash, harakat jurnali yoziladi), `give` (materialni xodimga berish — `change_material` bilan), `DELETE` (arxivlash).
- **Kimga kerak:** omborxonachi.
- **Kimga beriladi:** hammaga; `view_material` bo'lishi shart.

**`material_service` — Materiallarni sarflash**
- **Nima:** materialni sarflash (ombordan chiqim).
- **Qayerda:** `POST /materials/service/`; "Sarf" hisoboti; "Hisobotlar" menyusi.
- **Kimga kerak:** materialni ishlatadigan ATM xodimi.
- **Kimga beriladi:** faqat `worker` (mijozga berilmaydi).

**`all_material_employee` — Barcha xodimlarning materialini ko'rish (SUPER)**
- **Nima:** o'z tashkilotidagi "materialga javobgar" (`shop_employee`) xodimlarning materiallarini ham ko'rish.
- **Qayerda:** materiallar ro'yxati, xodim filtri, material hisoboti, sarflash (boshqa javobgarning materiali).
- **Kimga kerak:** omborxona mudiri, material bo'yicha rahbar.
- **Kimga beriladi:** hammaga; o'zida bor odam bera oladi; `view_material` kerak.

### 3.6 Zoom (uchrashuvlar)

**`view_meeting` — Hamma uchrashuvlarni ko'rish**
- **Qayerda:** "Zoom" menyusi, `GET /meetings/` (barcha uchrashuvlar, faqat ko'rish).
- **Kimga kerak:** rahbar — jadvalni kuzatuvchi.
- **Kimga beriladi:** faqat `worker`.

**`add_meeting` — Uchrashuv yaratish**
- **Qayerda:** `POST /meetings/`; boshlash (`start_url`), tugatish, taklif matni — faqat yaratgan xodimda.
- **Kimga beriladi:** faqat `worker`.

**`delete_meeting` — Uchrashuvni o'chirish**
- **Qayerda:** `POST /meetings/{id}/cancel/` (faqat yaratgan xodim va shu ruxsat bilan).
- **Kimga beriladi:** faqat `worker`.

### 3.7 Xodimlar

**`view_employee` — Xodimlarni ko'rish**
- **Qayerda:** "Xodimlar" menyusi, `GET /employees/`, Excel eksport, PINFL bo'yicha qidirish. Doira — o'z tashkiloti (`all_organization` bilan hammasi).
- **Kimga kerak:** kadrlar bo'limi, rahbarlar.
- **Kimga beriladi:** hammaga.

**`add_employee`, `change_employee`, `delete_employee`**
- **Qayerda:** `POST /employees/` (qo'shish), `PATCH` (ism, lavozim, bo'lim, telefon), `DELETE` (faolsizlantirish) va `activate` (qayta faollashtirish).
- **Kimga kerak:** kadrlar bo'limi.
- **Kimga beriladi:** hammaga; `view_employee` bo'lishi shart.

### 3.8 Maxsus ruxsatlar

**`boss_employee` — Departament rahbari**
- **Nima:** o'z departamentidagi texnikalar va texnikasi yo'q xodimlarni ko'rish.
- **Qayerda:** "Texnikalarim" sahifasi (`technics/mine`).
- **Kimga kerak:** departament boshlig'i.
- **Kimga beriladi:** rolni beruvchi `worker` bo'lishi kerak.

**`shop_employee` — Materialga javobgar shaxs**
- **Nima:** tashkilotda materiallar uchun mas'ul xodim belgisi.
- **Qayerda:** materiallar ko'rinishi (o'z tashkilotidagi va o'zining materiallari), `all_material_employee` bilan "javobgar xodimlar" ro'yxati, Svod va Reestr hisobotlari, "Hisobotlar" menyusi.
- **Kimga kerak:** omborxonachi, moddiy javobgar.
- **Kimga beriladi:** rolni beruvchi `worker` bo'lishi kerak.

**`status_employee` — Statistikani ko'rish**
- **Nima:** statistika va bosh sahifa.
- **Qayerda:** "Bosh sahifa" va "Statistika" menyusi; `/stats/employees/`, `/stats/technics/`; `spa/dashboard/overview/`. Doira — xodimning tashkiloti va hududi (superuser faqat bosh sahifada "Barcha tashkilotlar" ni ko'ra oladi).
- **Kimga kerak:** rahbariyat.
- **Kimga beriladi:** rolni beruvchi `worker` bo'lishi kerak; mijozga ham berish mumkin (omborxona arizalari va materiallar bo'yicha).

**`permission_employee` — Xodimlarga rol berish (SUPER)**
- **Nima:** boshqa xodimlarga ruxsat berish va olish.
- **Qayerda:** "Xodimlarga rol berish" oynasi, `GET`/`PUT /employees/{id}/permissions/`, `permissions/catalog/`, rol bilan bog'liq ma'lumotnomalar (`order-goals`, `liables`, `material-users`, `material-employees`, `contracts`).
- **Kimga kerak:** administrator, kadrlar rahbari.
- **Kimga beriladi:** rolni beruvchi `worker` bo'lishi kerak. Faqat o'z tashkiloti xodimlariga (`all_organization` bilan hammasiga).

**`report_employee` — Hisobotlarni ko'rish**
- **Nima:** Svod va Reestr hisobotlari (rol berishda qaysi shartnomalar bo'yicha ekani tanlanadi).
- **Qayerda:** "Hisobotlar" menyusi, `spa/reports/`.
- **Kimga kerak:** hisobot tayyorlovchi.
- **Kimga beriladi:** faqat `worker`.

---

## 4. "Hisobotlar" kim uchun

Faqat `worker` tashkilot xodimiga (mijozga `403`):

| Hisobot | Shart |
|---|---|
| Dalolatnoma (`document`) | `worker` va kamida bitta shartnoma |
| Svod (`svod`) | `shop_employee` yoki `report_employee` |
| Reestr (`reestr`) | `shop_employee` yoki `report_employee` |
| Akt (`akt`) | `change_order` |
| Sarf (`service`) | `material_service` |

---

## 5. Tizimdagi barcha funksiyalar

Belgilar: **✅** mobil API'da bor, **⚠️** qisman, **❌** hozircha yo'q.

| # | Funksiya | Kimga | Ruxsat | Mobil API |
|---|---|---|---|---|
| 1 | Kirish (SSO, login/parol, token yangilash, chiqish) | hamma | — | ✅ |
| 2 | Profil va ruxsatlar (`/me/`) | hamma | — | ✅ |
| 3 | **ATM arizasi:** yuborish, kuzatish, baho bilan qabul qilish, bekor qilish | hamma | — | ✅ |
| 4 | **ATM arizasi:** qabul qilish, yakunlash (material va texnika bilan) | ATM ijrochisi | `change_order` | ✅ |
| 5 | **Omborxona arizasi:** materiallar tanlab yuborish, savat, kuzatish, qabul qilish | mijoz xodimi | — | ✅ |
| 6 | **Omborxona:** arizani qabul qilish, rad etish, materiallarni berish | omborxonachi | `change_order` | ✅ |
| 7 | **Omborxona:** tasdiqlash yoki rad etish | tasdiqlovchi | `confirm_order` | ✅ |
| 8 | Texnikalar ro'yxati, kartasi, QR | texnik xodim | `view_technics` | ✅ |
| 9 | Texnika qo'shish, tahrirlash, biriktirish, bo'shatish, o'chirish | texnik xodim | `add_/change_/delete_technics` | ✅ |
| 10 | Texnikalarim (o'zining, departament) | hamma / `boss_employee` | — / `boss_employee` | ✅ |
| 11 | Qo'shimcha qurilmalar | texnik xodim | texnika ruxsatlari | ✅ |
| 12 | Materiallar: ko'rish, qo'shish, tahrirlash, berish, sarflash, o'chirish | omborxonachi | `view_/add_/change_/delete_material`, `material_service` | ✅ |
| 13 | Material kirim-chiqim hisoboti va harakatlar | omborxonachi | `view_material` | ✅ |
| 14 | Excel eksport (xodimlar, texnika, material, hisobot) | tegishli ruxsat bilan | `view_*` | ✅ |
| 15 | Hujjatlar: yaratish, ro'yxat, rad etish, kelishuvchilar, ilovalar | hammaga (yaratish — `add_deed`) | `add_deed`, `change_deed` | ⚠️ imzolash/tasdiqlash yo'q |
| 16 | Hujjatni **imzolash** (Face ID / E-imzo) | imzolovchi | — | ❌ alohida integratsiya |
| 17 | Hujjatlar reyestri (filtr bilan hammasini qidirish) | hamma | — | ✅ |
| 18 | Hisobotlar: Dalolatnoma, Svod, Reestr, Akt, Sarf | `worker` | 4-bo'limdagi shartlar | ⚠️ matnni ilova yig'adi, PDF va yuborish serverda |
| 19 | Statistika (xodimlar, texnika) | rahbar | `status_employee` | ✅ |
| 20 | Bosh sahifa (statistika paneli) | rahbar | `status_employee` | ⚠️ `spa/dashboard/overview/` (veb uchun yozilgan) |
| 21 | Xodimlar: ko'rish, qo'shish, tahrirlash, o'chirish | kadrlar | `*_employee` | ✅ |
| 22 | Xodimga rol (ruxsat) berish | administrator | `permission_employee` | ✅ |
| 23 | Chat: shaxsiy, guruh, saqlangan xabarlar, fayl | hamma | — | ✅ (REST + WebSocket) |
| 24 | AI yordamchi (chatda) | hamma | — | ⚠️ hozir tayyor matn qaytaradi, haqiqiy AI ulanmagan |
| 25 | Zoom uchrashuvlari | `worker` | `add_/view_/delete_meeting` | ✅ |
| 26 | Bildirishnomalar markazi | hamma | — | ✅ |
| 27 | Push (FCM): ariza, hujjat, chat | hamma | — | ✅ |
| 28 | Ma'lumotnomalar (tashkilot, hudud, lavozim, ariza turlari, birliklar...) | hamma | — | ✅ faqat o'qish |
| 29 | Telegram bot (bildirishnomalar) | hamma | — | tashqi (mobilga aloqasi yo'q) |
| 30 | Texnik ishlar rejimi va ilova versiyasi | hamma | — | ✅ (`app/config/`) |

---

## 6. Odatiy rollar (ruxsatlar to'plami namunasi)

Bular tayyor paket emas, qo'lda yig'iladigan to'plamlar:

| Odatiy lavozim | Tashkilot | Ruxsatlar |
|---|---|---|
| Oddiy mijoz xodimi | `client` | (ruxsatsiz) — ariza va omborxona arizasi yuboradi |
| Mijoz tasdiqlovchisi | `client` | `confirm_order` |
| Mijoz omborxonachisi | `client` | `change_order`, `shop_employee`, `view_material`, `add_material`, `change_material` |
| Mijoz rahbari (statistika) | `client` | `status_employee`, `view_material`, `all_material_employee` |
| ATM ijrochisi | `worker` | `change_order` (+ ariza turlari `execute_goals`) |
| ATM texnigi | `worker` | `view_technics`, `add_technics`, `change_technics`, `change_order` |
| ATM omborxonachisi | `worker` | `view_material`, `add_material`, `change_material`, `material_service`, `shop_employee`, `change_order` |
| Hujjat tayyorlovchi | `worker` | `add_deed`, `report_employee` + shartnoma |
| Kadrlar bo'limi | `worker` | `view_employee`, `add_employee`, `change_employee` |
| Rahbar | `worker` | `status_employee`, `view_employee`, `boss_employee`, `all_region` |
| Administrator | `worker` | `permission_employee`, `all_organization`, `all_region` |

---

## 7. Ilova uchun amaliy qoidalar

1. Kirgach `/me/` ni chaqiring: ekranlar `organization_type`, `orders.*` va `permissions` ga qarab quriladi.
2. Arizalar bo'limi: `can_create` → "Ariza yuborish"; `can_create_material_order` → "Omborxonaga ariza"; `can_execute` → "Yangi arizalar"; `can_confirm` → "Tasdiqlash".
3. Menyu: Texnika (`view_technics`), Materiallar (`view_material`), Xodimlar (`view_employee`), Statistika (`status_employee`), Zoom (`add_meeting` yoki `view_meeting`), Hisobotlar (4-bo'limdagi shartlar). Arizalar, Hujjatlar, Chat va Texnikalarim hammaga ochiq.
4. Tugmalar: yozish amallari (qo'shish, tahrirlash, o'chirish) uchun tegishli `add_*`, `change_*`, `delete_*` bo'yicha ko'rsating yoki yashiring.
5. Rol berish oynasida `editable=false` katakchalarni yashiring; `PUT` javobidagi `ignored` ni foydalanuvchiga ko'rsating.
6. `403` kelsa "Ruxsat yo'q" deb ko'rsating, `401` bo'lsa tokenni yangilang.
7. Mijoz va ATM xodimining ko'rinishi turlicha: mijozga `add_order`, `material_service`, Zoom, hisobotlar ko'rsatilmaydi.
