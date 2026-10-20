# IVS — yangi interfeys (React + AlignUI)

React 19 + Vite + TypeScript. Dizayn: Claude Design'dagi "AlignUI Design System"
(`src/ds/` — tokenlar, shriftlar va komponentlar to'plami o'zgarishsiz ko'chirilgan).
Sahifa yozish qoidalari: [CONVENTIONS.md](CONVENTIONS.md).

## Ishlab chiqish

```bash
# 1) Django (loyiha ildizida)
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

# 2) Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173/app/
```

Vite `/api`, `/sso`, `/media`, `/static`, `/ws` va admin manzillarini Django'ga proxy qiladi,
shuning uchun SPA Django sessiyasi (SSO) bilan ishlaydi. Lokal SSO sozlanmagan bo'lsa,
kirish sahifasidagi "admin hisobi bilan kirish" havolasidan foydalaning.

## Production

```bash
cd frontend && npm ci && npm run build     # → ../static/spa/ (git'da yo'q)
cd .. && python manage.py collectstatic --noinput
```

- Django yangi interfeysni `/app/` ostida beradi (`config/spa.py`), fayllar `/static/spa/` dan (WhiteNoise).
- `.env` da `SPA_ENABLED=1` — `/`, `/sso/login/` va SSO'dan keyingi yo'naltirish `/app/` ga boradi.
  O'chiq bo'lsa eski sahifalar asosiy bo'lib qoladi, `/app/` baribir ochiladi.
- Eski sahifalar o'z manzillarida ishlashda davom etadi (QR kodlar, PDF'lardagi havolalar ham).

## Tuzilma

- `src/ds/` — AlignUI dizayn tizimi (`import { Button, DataTable } from '../ds'`)
- `src/api/` — `/api/v1/` klienti va turlar; bo'limlarga xos qo'shimcha endpointlar — `api/spa/<bo'lim>.py`
- `src/layout/` — `Page` (AppShell + PageHeader), menyu (`nav.ts`, ruxsatlar `base.html` dagidek), nishonlar (`badges.ts`)
- `src/pages/<bo'lim>/` — sahifalar va `routes.tsx`; `App.tsx` ularni yig'adi
