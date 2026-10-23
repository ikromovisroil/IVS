"""
Lokal ishlab chiqish uchun bazani test (demo) ma'lumotlari bilan to'ldiradi.

    python manage.py seed_demo

Yaratiladi: hududlar, xizmat ko'rsatuvchi (worker) va mijoz (client) tashkilotlar, bo'lim/boshqarma/bo'linmalar,
lavozimlar, turli ruxsatli xodimlar, texnika va qo'shimcha qurilmalar, shartnomalar, materiallar va ularning
harakati, ariza turlari, turli holatdagi arizalar, dalolatnomalar va kelishuvchilar.

Barcha demo foydalanuvchilar "demo_" bilan boshlanadi, paroli — DEMO_PASSWORD.
Faqat DEBUG=True da ishlaydi (production bazasiga tasodifan yozilmasligi uchun); qayta ishga tushirilsa hech narsa
qilmaydi.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from main.models import (
    Category, Contract, Deed, DeedConsent, Department, Directorate, Division, Employee, Goal, Group, Liable,
    Material, MaterialCategory, MaterialEmployee, MaterialMovement, MaterialUser, Order, OrderGoal, OrderMaterial,
    Organization, Rank, Region, Structure, StructureCategory, Technics, Unit,
)

DEMO_PASSWORD = "Demo12345!"
MARKER_ORG = "IVS Servis markazi (demo)"

# Ruxsatlar to'plamlari (app_label.codename)
ROLE_PERMS = {
    "boss": [
        "main.boss_employee", "main.status_employee", "main.report_employee", "main.permission_employee",
        "main.view_employee", "main.add_employee", "main.change_employee",
        "main.view_technics", "main.change_technics", "main.view_material",
        "main.add_order", "main.change_order", "main.add_deed", "main.change_deed",
        "main.all_organization", "main.all_region",
        "chat.add_meeting", "chat.view_meeting", "chat.delete_meeting",
    ],
    "usta": [
        "main.change_order", "main.view_technics", "main.view_material", "main.material_service",
        "main.add_deed", "main.report_employee", "chat.view_meeting",
    ],
    "ombor": [
        "main.view_material", "main.add_material", "main.change_material", "main.delete_material",
        "main.all_material_employee", "main.shop_employee", "main.material_service",
        "main.view_technics", "main.add_technics", "main.change_technics", "main.delete_technics",
    ],
    "mijoz_rahbar": ["main.confirm_order", "main.view_technics"],
    "mijoz": [],
}

# Juda kichik, lekin haqiqiy PDF (Deed.file uchun)
TINY_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)


class Command(BaseCommand):
    help = "Lokal bazani test (demo) ma'lumotlari bilan to'ldiradi (faqat DEBUG=True)."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42, help="Tasodifiy sonlar generatori uchun boshlang'ich qiymat")

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("seed_demo faqat DEBUG=True bo'lganda ishlaydi.")
        if Organization.objects.filter(name=MARKER_ORG).exists():
            self.stdout.write(self.style.WARNING("Demo ma'lumotlar allaqachon mavjud — hech narsa qilinmadi."))
            return

        self.rnd = random.Random(opts["seed"])
        self.now = timezone.now()
        self._pinfl = 30101900000000
        with transaction.atomic():
            self._seed()
        self._report()

    # ───────────────────────── yordamchilar ─────────────────────────

    def _perms(self, codes):
        out = []
        for code in codes:
            app, codename = code.split(".")
            p = Permission.objects.filter(content_type__app_label=app, codename=codename).first()
            if p:
                out.append(p)
            else:
                self.stdout.write(self.style.WARNING(f"  Ruxsat topilmadi: {code}"))
        return out

    def _employee(self, username, last, first, father, role, *, division, rank, region):
        user = User.objects.create_user(username=username, password=DEMO_PASSWORD, first_name=first, last_name=last)
        user.user_permissions.set(self._perms(ROLE_PERMS[role]))
        emp = user.employee  # main/signals.py: create_employee
        self._pinfl += 1
        emp.last_name, emp.first_name, emp.father_name = last, first, father
        emp.division, emp.rank, emp.region = division, rank, region
        emp.phone = f"+99890{self.rnd.randint(1000000, 9999999)}"
        emp.pinfl = str(self._pinfl)
        emp.save()
        return emp

    def _ago(self, days_max, days_min=0):
        return self.now - timedelta(days=self.rnd.randint(days_min, days_max), hours=self.rnd.randint(0, 9))

    def _structure(self, org, region, dep_name, dir_name, div_names):
        dep = Department.objects.create(organization=org, region=region, name=dep_name, code=str(self.rnd.randint(100, 999)))
        dr = Directorate.objects.create(department=dep, name=dir_name, code=str(self.rnd.randint(100, 999)))
        return [Division.objects.create(directorate=dr, name=n, code=str(self.rnd.randint(100, 999))) for n in div_names]

    # ───────────────────────── ma'lumotlar ─────────────────────────

    def _seed(self):
        rnd = self.rnd
        R = {n: Region.objects.create(name=n) for n in ["Toshkent shahri", "Toshkent viloyati", "Samarqand viloyati", "Andijon viloyati"]}
        tosh, samq = R["Toshkent shahri"], R["Samarqand viloyati"]

        ranks = {n: Rank.objects.create(name=n, code=str(i)) for i, n in enumerate(
            ["Boshliq", "Bosh mutaxassis", "Yetakchi mutaxassis", "Muhandis", "Omborchi"], start=1)}

        # Tashkilotlar
        worker = Organization.objects.create(name=MARKER_ORG, type="worker", inn="301234567", contract="SH-2026/01")
        client1 = Organization.objects.create(name="G'aznachilik boshqarmasi (demo)", type="client", inn="302345678")
        client2 = Organization.objects.create(name="Soliq inspeksiyasi (demo)", type="client", inn="303456789")

        w_tosh = self._structure(worker, tosh, "Toshkent filiali", "Texnik xizmat boshqarmasi", ["1-servis bo'limi", "Ombor"])
        w_samq = self._structure(worker, samq, "Samarqand filiali", "Texnik xizmat boshqarmasi", ["2-servis bo'limi"])
        c1_tosh = self._structure(client1, tosh, "Toshkent shahar g'aznachiligi", "Hisob boshqarmasi", ["Buxgalteriya", "Kassa bo'limi"])
        c1_samq = self._structure(client1, samq, "Samarqand viloyat g'aznachiligi", "Hisob boshqarmasi", ["Buxgalteriya"])
        c2_tosh = self._structure(client2, tosh, "Yunusobod tuman DSI", "Nazorat boshqarmasi", ["Kameral nazorat", "Hisobga olish"])

        # Xodimlar
        E = self._employee
        boss = E("demo_boss", "Karimov", "Jasur", "Akmalovich", "boss", division=w_tosh[0], rank=ranks["Boshliq"], region=tosh)
        usta1 = E("demo_usta1", "Rahimov", "Sardor", "Ilhomovich", "usta", division=w_tosh[0], rank=ranks["Muhandis"], region=tosh)
        usta2 = E("demo_usta2", "Tursunov", "Bekzod", "Olimovich", "usta", division=w_tosh[0], rank=ranks["Muhandis"], region=tosh)
        usta3 = E("demo_usta3", "Nazarov", "Otabek", "Rustamovich", "usta", division=w_samq[0], rank=ranks["Muhandis"], region=samq)
        ombor = E("demo_ombor", "Saidova", "Malika", "Baxtiyorovna", "ombor", division=w_tosh[1], rank=ranks["Omborchi"], region=tosh)
        clients = [
            E("demo_mijoz_rahbar", "Abdullayev", "Rustam", "Karimovich", "mijoz_rahbar", division=c1_tosh[0], rank=ranks["Boshliq"], region=tosh),
            E("demo_mijoz1", "Yusupova", "Dilnoza", "Anvarovna", "mijoz", division=c1_tosh[0], rank=ranks["Bosh mutaxassis"], region=tosh),
            E("demo_mijoz2", "Ergashev", "Aziz", "Shavkatovich", "mijoz", division=c1_tosh[1], rank=ranks["Yetakchi mutaxassis"], region=tosh),
            E("demo_mijoz3", "Qodirova", "Nigora", "Farhodovna", "mijoz", division=c1_samq[0], rank=ranks["Bosh mutaxassis"], region=samq),
            E("demo_mijoz4", "Mirzayev", "Javlon", "Ulug'bekovich", "mijoz", division=c2_tosh[0], rank=ranks["Bosh mutaxassis"], region=tosh),
            E("demo_mijoz5", "Hasanova", "Shahlo", "Ravshanovna", "mijoz", division=c2_tosh[1], rank=ranks["Yetakchi mutaxassis"], region=tosh),
        ]
        ustalar = {tosh.id: [usta1, usta2], samq.id: [usta3]}

        # Texnika turlari, kategoriyalar, shartnomalar
        G = {n: Group.objects.create(name=n) for n in ["Kompyuter texnikasi", "Printer va MFU", "Tarmoq uskunalari"]}
        C = {
            "Tizim bloki": G["Kompyuter texnikasi"], "Monitor": G["Kompyuter texnikasi"], "Noutbuk": G["Kompyuter texnikasi"],
            "A4 printer": G["Printer va MFU"], "MFU": G["Printer va MFU"],
            "Switch": G["Tarmoq uskunalari"], "Router": G["Tarmoq uskunalari"],
        }
        cats = {n: Category.objects.create(name=n, group=g) for n, g in C.items()}
        con_pc = Contract.objects.create(name="Kompyuter texnikasiga xizmat ko'rsatish", unit="dona", price=Decimal("85000"))
        con_pc.categories.set([cats["Tizim bloki"], cats["Monitor"], cats["Noutbuk"]])
        con_pr = Contract.objects.create(name="Printer va MFUlarga xizmat ko'rsatish", unit="dona", price=Decimal("65000"))
        con_pr.categories.set([cats["A4 printer"], cats["MFU"]])
        con_net = Contract.objects.create(name="Tarmoq uskunalariga xizmat ko'rsatish", unit="dona", price=Decimal("120000"))
        con_net.categories.set([cats["Switch"], cats["Router"]])
        for emp in (boss, usta1, usta2, usta3, ombor, clients[0]):
            liable = Liable.objects.create(employee=emp)
            liable.categorys.set(cats.values())
            liable.contracts.set([con_pc, con_pr, con_net])

        # Texnikalar (mijoz xodimlariga biriktirilgan va bo'sh)
        models_by_cat = {
            "Tizim bloki": ["HP ProDesk 400 G7", "Dell OptiPlex 3080", "Lenovo ThinkCentre M70"],
            "Monitor": ["Samsung S24F350", "Dell P2422H", "LG 24MK430"],
            "Noutbuk": ["Lenovo ThinkPad E14", "HP ProBook 450"],
            "A4 printer": ["HP LaserJet Pro M404", "Canon i-SENSYS LBP6030"],
            "MFU": ["Canon MF445dw", "Kyocera ECOSYS M2040dn"],
            "Switch": ["Cisco SG110-24"], "Router": ["MikroTik hEX S"],
        }
        technics = []
        n = 0
        for emp in clients + [boss, usta1, usta2, usta3, ombor]:
            for cat_name in ["Tizim bloki", "Monitor", rnd.choice(["A4 printer", "MFU"]), rnd.choice(["Noutbuk", "Monitor"])]:
                n += 1
                technics.append(Technics.objects.create(
                    group=C[cat_name], category=cats[cat_name], region=emp.region, employee=emp,
                    status=rnd.choices(["active", "repair", "defect"], weights=[85, 10, 5])[0],
                    name=rnd.choice(models_by_cat[cat_name]), inventory=f"INV-{2026_0000 + n}",
                    serial=f"SN{rnd.randint(10**7, 10**8 - 1)}", price=Decimal(rnd.randint(15, 120) * 100000),
                    year=str(rnd.randint(2018, 2025)), ip=f"10.10.{rnd.randint(1, 20)}.{rnd.randint(2, 250)}",
                ))
        for cat_name in ["Switch", "Router", "Tizim bloki", "MFU"]:
            n += 1
            technics.append(Technics.objects.create(
                group=C[cat_name], category=cats[cat_name], region=tosh, organization=client1, status="free",
                name=rnd.choice(models_by_cat[cat_name]), inventory=f"INV-{2026_0000 + n}",
                serial=f"SN{rnd.randint(10**7, 10**8 - 1)}", price=Decimal(rnd.randint(15, 120) * 100000), year="2024",
            ))

        # Qo'shimcha qurilmalar
        sc = {k: StructureCategory.objects.create(name=k) for k in ["Klaviatura", "Sichqoncha", "UPS", "Veb-kamera"]}
        for i in range(10):
            cat_name = rnd.choice(list(sc))
            tex = rnd.choice(technics[:12]) if i < 6 else None
            Structure.objects.create(
                category=sc[cat_name], organization=client1, region=tosh, technics=tex,
                status="active" if tex else "free", name=f"{cat_name} #{i + 1}",
                inventory=f"QQ-{1000 + i}", serial=f"S{rnd.randint(10**5, 10**6 - 1)}", price=Decimal(rnd.randint(1, 15) * 50000),
            )

        # Materiallar
        units = {k: Unit.objects.create(name=k) for k in ["dona", "metr", "quti"]}
        mcats = {k: MaterialCategory.objects.create(organization=worker, name=k) for k in
                 ["Kartridjlar", "Kabel va ulagichlar", "Ehtiyot qismlar"]}
        me = MaterialEmployee.objects.create(employee=ombor)
        me.category.set(mcats.values())
        mu = MaterialUser.objects.create(sender=ombor)
        mu.receiver.set([usta1, usta2, usta3])
        mat_specs = [
            ("HP 59A kartridj", "Kartridjlar", "dona", 320000), ("Canon 737 kartridj", "Kartridjlar", "dona", 280000),
            ("Toner 1 kg", "Kartridjlar", "quti", 150000), ("UTP Cat6 kabel", "Kabel va ulagichlar", "metr", 4500),
            ("RJ-45 ulagich", "Kabel va ulagichlar", "dona", 1200), ("HDMI kabel 1.5 m", "Kabel va ulagichlar", "dona", 35000),
            ("Blok pitaniya 450W", "Ehtiyot qismlar", "dona", 290000), ("SSD 256 GB", "Ehtiyot qismlar", "dona", 410000),
            ("Operativ xotira 8 GB", "Ehtiyot qismlar", "dona", 330000), ("Termopasta", "Ehtiyot qismlar", "dona", 25000),
        ]
        materials = []
        for i, (name, cat, unit, price) in enumerate(mat_specs):
            for holder in (ombor, rnd.choice([usta1, usta2, usta3])):
                m = Material.objects.create(
                    category=mcats[cat], organization=worker, employee=holder, unit=units[unit], name=name,
                    number=rnd.randint(5, 60) if holder == ombor else rnd.randint(1, 8),
                    code=f"M{100 + i}", price=Decimal(price), year="2026",
                )
                MaterialMovement.objects.create(user=ombor, material=m, employee=holder, income=m.number,
                                                status="created" if holder == ombor else "assigned")
                materials.append(m)

        # Ariza turlari (worker tashkilotiniki) va kim bajara oladi
        goals = [Goal.objects.create(organization=worker, name=g) for g in
                 ["Kompyuter ta'miri", "Printer ta'miri", "Kartridj almashtirish", "Tarmoq muammosi", "Dastur o'rnatish"]]
        for emp in (boss, usta1, usta2, usta3):
            og = OrderGoal.objects.create(employee=emp)
            og.goal.set(goals)

        # Arizalar
        texts = [
            "Kompyuter yoqilmayapti", "Printer qog'ozni tortmayapti", "Kartridj tugadi, almashtirish kerak",
            "Internet ishlamayapti", "1C dasturini o'rnatib berish kerak", "Monitor miltillayapti",
            "Kompyuter juda sekin ishlayapti", "Skaner ishlamayapti", "Elektron pochta ochilmayapti",
        ]
        statuses = ["viewed"] * 5 + ["process"] * 6 + ["finished"] * 5 + ["accepted"] * 9 + ["canceled"] * 2 + ["rejected"] * 2
        orders = []
        for status in statuses:
            sender = rnd.choice(clients[1:])
            tex = rnd.choice([t for t in technics if t.employee_id == sender.id] or [None])
            created = self._ago(60, 1)
            receiver = rnd.choice(ustalar[sender.region_id]) if status != "viewed" else None
            o = Order.objects.create(
                goal=rnd.choice(goals), sender=sender, message_sender=rnd.choice(texts), technics=tex,
                receiver=receiver, status=status,
                message_receiver="Bajarildi" if status in ("finished", "accepted") else (
                    "Ariza noto'g'ri yuborilgan" if status == "rejected" else None),
                rating=rnd.randint(3, 5) if status == "accepted" else None,
                user=clients[0] if status == "accepted" else None,
            )
            # Sanalarni o'tmishga yoyish (dashboard va hisobotlar uchun); holatgacha bo'lgan bosqichlar to'ldiriladi
            step = timedelta(hours=rnd.randint(2, 30))
            path = {
                "viewed": [], "process": ["date_process"], "finished": ["date_process", "date_finished"],
                "accepted": ["date_process", "date_finished", "date_accepted"],
                "canceled": ["date_canceled"], "rejected": ["date_rejected"],
            }[status]
            dates = {"date_creat": created}
            dates.update({field: created + step * (i + 1) for i, field in enumerate(path)})
            Order.objects.filter(pk=o.pk).update(**dates)
            if status in ("finished", "accepted"):
                own = [m for m in materials if m.employee_id == receiver.id]
                for m in rnd.sample(own, k=min(len(own), rnd.randint(1, 2))):
                    OrderMaterial.objects.create(order=o, user=receiver, material=m, number=1, given=1)
                    MaterialMovement.objects.create(user=receiver, material=m, employee=receiver, outcome=1, status="order",
                                                    body=f"Ariza #{o.pk}")
            orders.append(o)

        # Dalolatnomalar (aktlar)
        done = [o for o in orders if o.status == "accepted"]
        deed_specs = [
            (usta1, clients[0], "approved", "approved", "Tasdiqlangan akt"),
            (usta1, clients[0], "approved", "viewed", "Mijoz imzosini kutayotgan akt"),
            (usta2, clients[0], "viewed", "viewed", "Yangi yaratilgan akt"),
            (usta2, clients[0], "approved", "rejected", "Mijoz rad etgan akt"),
        ]
        for i, (author, receiver, st_s, st_r, note) in enumerate(deed_specs):
            d = Deed(
                organization=receiver.organization, user=author, sender=boss, receiver=receiver,
                status_sender=st_s, status_receiver=st_r, status="act", message_user=note,
                body=f"<p>{note}: bajarilgan ishlar dalolatnomasi.</p>",
                message_receiver="Hisob-kitobda xato bor" if st_r == "rejected" else None,
                date_sender=self.now - timedelta(days=5 - i) if st_s != "viewed" else None,
                date_receiver=self.now - timedelta(days=4 - i) if st_r != "viewed" else None,
            )
            d.file.save(f"demo_akt_{i + 1}.pdf", ContentFile(TINY_PDF), save=False)
            d.save()
            d.orders.set(done[i * 2:i * 2 + 2])
            DeedConsent.objects.create(deed=d, employee=clients[1], status="approved" if st_r == "approved" else "viewed")

    def _report(self):
        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar yaratildi."))
        for model in (Region, Organization, Employee, Technics, Structure, Material, MaterialMovement, Order, Deed):
            self.stdout.write(f"  {model.__name__}: {model.objects.count()}")
        self.stdout.write("Foydalanuvchilar (parol: seed_demo.py dagi DEMO_PASSWORD):")
        for u in User.objects.filter(username__startswith="demo_").order_by("id"):
            self.stdout.write(f"  {u.username}")
