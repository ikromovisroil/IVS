# IVS — React frontend

Bu — mavjud Django-shablon veb-interfeys va Telegram botga **qo'shimcha, parallel** ishlaydigan yangi mijoz. Django backend'ning `/api/` REST API'siga (JWT autentifikatsiya bilan) so'rov yuboradi. Django shablonlar va bot o'zgarishsiz, alohida ishlab turadi.

## Ishga tushirish

```bash
npm install
cp .env.example .env   # kerak bo'lsa VITE_API_BASE_URL manzilini o'zgartiring
npm run dev
```

Django backend alohida ishga tushirilishi kerak (loyihaning tub papkasidan):

```bash
python manage.py runserver
```

**Diqqat**: lokal ishlab chiqishda `.env` faylida (Django tomonda) `DEBUG=True` bo'lishi kerak — aks holda `config/settings.py`dagi CORS ro'yxati faqat production domenini o'z ichiga oladi va frontend `http://localhost:5173`dan API'ga murojaat qila olmaydi (CORS xatosi).

## Autentifikatsiya

JWT (`djangorestframework-simplejwt`), allaqachon Django tomonda tayyor:
- `POST /api/token/` — login (username, password) → `access` + `refresh`
- `POST /api/token/refresh/` — access tokenni yangilash

`access` token xotirada (memory) saqlanadi, `refresh` — `localStorage`da. Sahifa qayta yuklanganda `refresh` orqali avtomatik tiklanadi (`src/api/client.ts`).

## Qamrov — nima tayyor, nima YO'Q

**To'liq ishlaydi:**
- Kirish (login/logout, JWT + avtomatik yangilash)
- Navigatsiya (`/api/me/`dan kelgan Django ruxsatlariga qarab menyu elementlari ko'rsatiladi/yashiriladi)
- Materiallar — ro'yxat + qidiruv
- Texnikalar — ro'yxat + qidiruv
- Arizalar — ro'yxat, yangi ariza yaratish, qabul qilish/yakunlash/tasdiqlash-rad etish/yakuniy qabul
- **Akt (hujjat)** — ro'yxat, yangi Akt yaratish, PDF generatsiya qilish va yuklab olish, kelishuvchi sifatida tasdiqlash/rad etish — **boshidan oxirigacha**

**Keyingi bosqich sifatida QOLDIRILGAN** (backend API'da ham hali yo'q yoki frontendda ulanmagan):
- Svod, Reestr, Dalolatnoma (Document), Talabnoma (Petition), Sarf materiallar (Service) — qolgan 5 xil hujjat turi. Akt sahifasidagi naqsh (`src/pages/AktPage.tsx`) asosida tez qo'shish mumkin.
- Akt/Svod/Service'dagi "material avtomatik aniqlash" (Django web-UI'dagi `ajax_akt_materials` va sh.k. AJAX endpointlariga mos) — API'da hali maxsus endpoint sifatida ochilmagan, shu sabab Akt sahifasida hujjat matni qo'lda kiritiladi.
- Material "sarflash" (`material_service`) — API'da bu amal uchun alohida endpoint yo'q (faqat `give` — boshqa xodimga o'tkazish — bor).
- Xodimlarga rol berish (ruxsatlar) paneli.
- Statistika/Audit sahifalari.
- TinyMCE-ga o'xshash boy matn tahrirlagich (hozircha oddiy `<textarea>`).

## Fayl tuzilishi

```
src/
  api/client.ts       — axios instance, JWT refresh interceptor, login/logout
  api/types.ts        — TypeScript interfeyslari (backend serializerlariga mos)
  auth/                — AuthContext, LoginPage
  layout/AppLayout.tsx — chap menyu + asosiy joylashuv
  pages/               — har bir modul uchun sahifa
```
