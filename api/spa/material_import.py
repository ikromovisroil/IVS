"""
Materiallarni Excel'dan import qilish (faqat superuser) — /api/v1/spa/warehouse/materials/import/.

* GET  import/options/?organization=<id> — tashkilotlar va tanlangan tashkilot xodimlari (import oynasi uchun).
* GET  import/template/                   — namuna .xlsx.
* POST import/ (multipart: file, organization, employee, category [ixtiyoriy], unit_map [JSON {fayldagi nom: birlik id}], dry_run)
       dry_run=1 — hech narsa yozmaydi, faqat nima bo'lishini hisoblab ko'rsatadi; dry_run=0 — yozadi.

Excel formati ikki xil bo'lishi mumkin va ustunlar sarlavha matni bo'yicha topiladi (tartibi muhim emas):
  1) namuna: Nomi | O'lchov birligi | 1C kodi | Narxi | Soni (ixtiyoriy: Kategoriya ustuni)
  2) inventarizatsiya ro'yxati (ИНВЕНТАРИЗАЦИОННАЯ ОПИСЬ): "наименование", "единица измерения", "код", "цена",
     "фактическое наличие кол-во" — har varaq alohida o'qiladi.

O'lchov birligi ham YARATILMAYDI: bazadagi birlik nomi bo'yicha topiladi ("Штука"/"ед."/"dona" bir xil hisoblanadi),
topilmaganlari uchun import oynasi qaysi birlikka mos kelishini so'raydi (unit_map); javob berilmasa — birliksiz.
Kategoriya YARATILMAYDI: bazadagi mavjud kategoriya tanlanadi (hamma qatorga) yoki Excelning "Kategoriya" ustuni bo'yicha topiladi;
topilmasa, material kategoriyasiz yaratiladi va bu hisobotda ko'rsatiladi.
Jadval TO'LIQ import qilinadi: har qator alohida Material bo'ladi (nom, soni, narx, kod bir xil bo'lsa ham birlashtirilmaydi)
va miqdori bo'yicha "kirim" harakati yoziladi (hisobotdagi qoldiq to'g'ri chiqadi). Faqat noto'g'ri qatorlar (kasr/manfiy miqdor,
uzun nom/kod va h.k.) o'tkazib yuboriladi va hisobotda ko'rsatiladi.
Faylni ishonchsiz deb hisoblaymiz: faqat qiymatlar o'qiladi (makroslar bajarilmaydi), hajmi va qatorlar soni cheklangan.
"""
import io
import json
import re
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import Employee, Material, MaterialCategory, MaterialMovement, Organization, Unit

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_ISSUES = 100
ALLOWED_EXT = (".xlsx", ".xlsm")

_APOSTROPHES = re.compile(r"['‘’ʻʼ`´]")
_SKIP_ROW = re.compile(r"^(итого|jami|всего|количество наименований)", re.I)
# Ruscha birlik -> bazadagi lotincha birlik nomi (ikkalasi ham _norm dan keyin). Bazada shu nom bo'lsa, o'zi tanlanadi;
# bo'lmasa (yoki bu ro'yxatda yo'q birlik) — import oynasi qaysi birlikka mos kelishini so'raydi.
_UNIT_ALIASES = {
    "штука": "dona", "шт": "dona", "шт.": "dona", "ед": "dona", "ед.": "dona", "единица": "dona", "дона": "dona", "pcs": "dona",
    "пачка": "pachka", "упаковка": "oram", "упак": "oram", "упак.": "oram",
    "метр": "metr", "м": "metr", "метр квадрат": "kv. metr", "кв. метр": "kv. metr", "кв.м": "kv. metr", "м2": "kv. metr",
    "килограмм": "kilogramm", "кг": "kilogramm", "литр": "litr", "л": "litr", "мл": "ml", "км": "km",
    "комплект": "komplekt", "компл": "komplekt", "компл.": "komplekt", "пара": "juft", "рулон": "rulon",
    "коробка": "quti", "пучок": "quti", "баллон": "ballon", "банка": "shisha", "гкал": "gkal",
}


def _norm(text):
    return _APOSTROPHES.sub("", re.sub(r"\s+", " ", str(text or "")).strip().lower())


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _find_columns(ws):
    """Sarlavha qatorlari (birinchi 8 qator) bo'yicha ustunlarni topadi: {name, unit, code, price, qty, category}."""
    heads = {}
    for row in ws.iter_rows(min_row=1, max_row=8, values_only=True):
        for idx, value in enumerate(row):
            if isinstance(value, str):
                heads[idx] = (heads.get(idx, "") + " " + _norm(value)).strip()

    def first(keywords, exclude=()):
        for idx in sorted(heads):
            if idx in exclude:
                continue
            if any(k in heads[idx] for k in keywords):
                return idx
        return None

    cols = {}
    cols["unit"] = first(("единица", "olchov", "birlik", "unit"))
    used = {cols["unit"]} if cols["unit"] is not None else set()
    cols["code"] = first(("1c", "код", "kod"), used)
    used |= {cols["code"]} if cols["code"] is not None else set()
    cols["price"] = first(("цена", "narx", "price"), used)
    used |= {cols["price"]} if cols["price"] is not None else set()
    cols["qty"] = first(("фактическ", "miqdor", "soni", "кол-во", "количество", "qty"), used)
    used |= {cols["qty"]} if cols["qty"] is not None else set()
    cols["category"] = first(("категор", "kategor"), used)
    used |= {cols["category"]} if cols["category"] is not None else set()
    cols["name"] = first(("наименование", "nomi", "название", "товарно", "material", "name"), used)
    return cols


def _to_decimal(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = _clean(value).replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_workbook(fileobj):
    """Qatorlarni o'qiydi: [{sheet, row, name, unit, code, price, qty, category, error}]. Xato bo'lsa — ValidationError."""
    from openpyxl import load_workbook
    try:
        wb = load_workbook(fileobj, read_only=True, data_only=True)
    except Exception:
        raise ValidationError({"file": "Fayl Excel (.xlsx / .xlsm) sifatida o'qilmadi."})
    rows, sheets_seen = [], 0
    for ws in wb.worksheets:
        cols = _find_columns(ws)
        if cols["name"] is None or cols["qty"] is None:
            continue
        sheets_seen += 1
        for number, row in enumerate(ws.iter_rows(values_only=True), start=1):
            def cell(key):
                idx = cols.get(key)
                return row[idx] if idx is not None and idx < len(row) else None

            name = cell("name")
            qty_raw, price_raw = cell("qty"), cell("price")
            # ma'lumot qatori: nom — matn, miqdor yoki narx — son (sarlavha va 1,2,3 raqamlash qatorlari tushib qoladi)
            if not isinstance(name, str) or not _clean(name) or _SKIP_ROW.match(_clean(name)):
                continue
            if _to_decimal(qty_raw) is None and _to_decimal(price_raw) is None:
                continue
            if len(rows) >= MAX_ROWS:
                raise ValidationError({"file": f"Qatorlar soni {MAX_ROWS} dan oshmasligi kerak."})
            rows.append({
                "sheet": ws.title, "row": number, "name": _clean(name), "unit": _clean(cell("unit")),
                "code": _clean(cell("code")), "price": _to_decimal(price_raw), "qty": _to_decimal(qty_raw),
                "category": _clean(cell("category")),
            })
    wb.close()
    if not sheets_seen:
        raise ValidationError({"file": "Sarlavhalar topilmadi: 'Nomi' va 'Soni' (yoki 'наименование' va 'кол-во') ustunlari kerak."})
    return rows


def _categories_of(org_id):
    """Tashkilotning o'z kategoriyalari va umumiylari (tashkilotsiz)."""
    return MaterialCategory.objects.filter(Q(organization_id=org_id) | Q(organization__isnull=True))


class _DryRun(Exception):
    pass


class _Importer:
    def __init__(self, organization, employee, importer, filename, category=None, unit_map=None):
        self.org, self.owner, self.importer = organization, employee, importer
        self.filename, self.fixed_category = filename, category
        self.units = {_norm(u.name): u for u in Unit.objects.all()}
        by_id = {u.id: u for u in self.units.values()}
        self.unit_map = {_norm(name): by_id[uid] for name, uid in (unit_map or {}).items() if uid in by_id}
        self.unmatched_units = {}
        self.categories = {
            _norm(c.name): c for c in _categories_of(organization.id)
        }
        self.unmatched_categories = []
        self.stats = {"created": 0, "skipped": 0, "quantity": 0, "sum": Decimal("0")}
        self.issues = []

    def issue(self, row, message):
        self.stats["skipped"] += 1
        if len(self.issues) < MAX_ISSUES:
            self.issues.append({"sheet": row["sheet"], "row": row["row"], "name": row["name"][:60], "message": message})

    def unit_for(self, text):
        if not text:
            return None
        key = _norm(text)
        if key in self.units:
            return self.units[key]
        alias = _UNIT_ALIASES.get(key)
        if alias and alias in self.units:
            return self.units[alias]
        if key in self.unit_map:
            return self.unit_map[key]
        # bazada yo'q: yangi birlik yaratilmaydi — import oynasi qaysi birlikka mos kelishini so'raydi
        self.unmatched_units[text] = self.unmatched_units.get(text, 0) + 1
        return None

    def category_for(self, text):
        """Faqat bazadagi mavjud kategoriya; yangisi yaratilmaydi. Topilmasa None (va hisobotda ko'rsatiladi)."""
        if self.fixed_category:
            return self.fixed_category
        if not text:
            return None
        found = self.categories.get(_norm(text))
        if found is None and text not in self.unmatched_categories:
            self.unmatched_categories.append(text)
        return found

    def process(self, row):
        qty, price = row["qty"], row["price"]
        if qty is None or qty <= 0:
            return self.issue(row, "Miqdor (Soni) musbat son bo'lishi kerak")
        if qty != qty.to_integral_value():
            return self.issue(row, f"Kasr miqdor ({qty.normalize()}): tizimda soni butun bo'lishi kerak, faylda tuzating")
        if price is not None and price < 0:
            return self.issue(row, "Narx manfiy bo'lishi mumkin emas")
        if price is not None and price >= Decimal("10000000000"):
            return self.issue(row, "Narx juda katta")
        if len(row["name"]) > 300:
            return self.issue(row, "Nomi 300 belgidan uzun")
        if len(row["code"]) > 20:
            return self.issue(row, "Kod 20 belgidan uzun")
        qty = int(qty)
        price = (price or Decimal("0")).quantize(Decimal("0.01"))

        body = f"Excel import: {self.filename} ({row['sheet']}, {row['row']}-qator)"
        material = Material.objects.create(
            organization=self.org, employee=self.owner, category=self.category_for(row["category"]),
            unit=self.unit_for(row["unit"]), name=row["name"], code=row["code"] or None, price=price, number=qty,
        )
        MaterialMovement.objects.create(material=material, user=self.importer, employee=self.owner,
                                        status="created", income=qty, body=body)
        self.stats["created"] += 1
        self.stats["quantity"] += qty
        self.stats["sum"] += price * qty


def run_import(rows, organization, employee, importer, filename, dry_run, category=None, unit_map=None):
    summary = {}
    try:
        with transaction.atomic():
            imp = _Importer(organization, employee, importer, filename, category, unit_map)
            per_sheet = {}
            for row in rows:
                before = (imp.stats["created"], imp.stats["skipped"])
                imp.process(row)
                sheet = per_sheet.setdefault(row["sheet"], {"name": row["sheet"], "rows": 0, "created": 0, "skipped": 0})
                sheet["rows"] += 1
                sheet["created"] += imp.stats["created"] - before[0]
                sheet["skipped"] += imp.stats["skipped"] - before[1]
            summary = {
                "rows": len(rows), "created": imp.stats["created"],
                "skipped": imp.stats["skipped"], "quantity": imp.stats["quantity"], "sum": str(imp.stats["sum"]),
                "sheets": list(per_sheet.values()), "unmatched_units": [{"name": n, "count": c} for n, c in imp.unmatched_units.items()], "unmatched_categories": imp.unmatched_categories,
                "issues": imp.issues, "issues_truncated": imp.stats["skipped"] > len(imp.issues),
            }
            if dry_run:
                raise _DryRun
    except _DryRun:
        pass
    return summary


class SuperuserOnly(permissions.BasePermission):
    message = "Excel import faqat superuser uchun."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class MaterialImportOptionsView(APIView):
    permission_classes = [SuperuserOnly]

    def get(self, request):
        orgs = [{"id": o.id, "name": o.name} for o in Organization.objects.order_by("name")]
        org = request.query_params.get("organization")
        employees, categories = [], []
        units = [{"id": u.id, "name": u.name} for u in Unit.objects.order_by("name")]
        if org and org.isdigit():
            categories = [{"id": c.id, "name": c.name} for c in _categories_of(int(org)).order_by("name")]
            for e in Employee.objects.filter(organization_id=int(org)).select_related("rank").order_by(
                    "last_name", "first_name"):
                employees.append({"id": e.id, "full_name": e.full_name, "rank": e.rank.name if e.rank_id else ""})
        return Response({"organizations": orgs, "employees": employees, "categories": categories, "units": units})


class MaterialImportView(APIView):
    permission_classes = [SuperuserOnly]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            raise ValidationError({"file": "Fayl tanlanmagan."})
        if not upload.name.lower().endswith(ALLOWED_EXT):
            raise ValidationError({"file": "Faqat .xlsx yoki .xlsm fayl yuklash mumkin."})
        if upload.size > MAX_FILE_SIZE:
            raise ValidationError({"file": "Fayl hajmi 5 MB dan oshmasligi kerak."})
        org_id, emp_id = request.data.get("organization"), request.data.get("employee")
        try:
            organization = Organization.objects.get(pk=int(org_id))
        except (TypeError, ValueError, Organization.DoesNotExist):
            raise ValidationError({"organization": "Tashkilot tanlanmagan."})
        try:
            employee = Employee.objects.get(pk=int(emp_id), organization=organization)
        except (TypeError, ValueError, Employee.DoesNotExist):
            raise ValidationError({"employee": "Moddiy-javobgar xodim tanlanmagan yoki bu tashkilotniki emas."})

        def flag(key, default):
            return str(request.data.get(key, default)).lower() in ("1", "true", "on", "yes")

        category = None
        if str(request.data.get("category") or "").isdigit():
            category = _categories_of(organization.id).filter(pk=int(request.data["category"])).first()
            if category is None:
                raise ValidationError({"category": "Kategoriya topilmadi yoki bu tashkilotniki emas."})

        try:
            raw_map = json.loads(request.data.get("unit_map") or "{}")
            unit_map = {str(k): int(v) for k, v in raw_map.items() if v not in (None, "")}
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({"unit_map": "O'lchov birliklari moslamasi noto'g'ri."})

        dry_run = flag("dry_run", "1")      # standart: faqat tekshirish, yozmaydi
        rows = parse_workbook(io.BytesIO(upload.read()))
        summary = run_import(
            rows, organization, employee, getattr(request.user, "employee", None), upload.name,
            dry_run=dry_run, category=category, unit_map=unit_map,
        )
        summary["dry_run"] = dry_run
        return Response(summary)


class MaterialImportTemplateView(APIView):
    permission_classes = [SuperuserOnly]

    def get(self, request):
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "Materiallar"
        ws.append(["Nomi", "O'lchov birligi", "1C kodi", "Narxi", "Soni"])
        ws.append(["Ruchka kanselyariya", "dona", None, 5000, 100])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for col, width in zip("ABCDE", (46, 18, 14, 14, 10)):
            ws.column_dimensions[col].width = width
        out = io.BytesIO()
        wb.save(out)
        response = HttpResponse(out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="material-import-namuna.xlsx"'
        return response
