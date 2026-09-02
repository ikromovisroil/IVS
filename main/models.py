from django.contrib.auth.models import User
from .validators import *
from django.utils import timezone
import random
import string
import qrcode
from io import BytesIO
from django.core.files import File
from django.db import models,transaction
from django.urls import reverse


# Organizator.
class Organization(models.Model):
    name = models.CharField(max_length=500)
    contract = models.CharField(max_length=200, null=True, blank=True)
    inn = models.CharField(max_length=20, null=True, blank=True)

    type = models.CharField(max_length=10, choices=[
        ("worker", "(xizmat ko'rsatuvchi)"),
        ("client", "Mijoz tashkilot"),
    ], default="client", db_index=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        db_table = 'organization'
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        permissions = [
            ("all_organization", "Barcha tashkilotni ko'rish"),
        ]


# viloyat.
class Region(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'region'
        verbose_name = "Xudud"
        verbose_name_plural = "Xududlar"
        permissions = [
            ("all_region", "Barcha Xududlarni ko'rish"),
        ]


# Departament.
class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    code = models.CharField(max_length=20, null=True, blank=True)
    inn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'department'
        verbose_name = "Departament"
        verbose_name_plural = "Departamentlar"


# Boshqarma.
class Directorate(models.Model):
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    code = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'directorate'
        verbose_name = "Boshqarma"
        verbose_name_plural = "Boshqarmalar"


# Bo'lim.
class Division(models.Model):
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    code = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'division'
        verbose_name = "Bo'lim"
        verbose_name_plural = "Bo'limlar"


# Lavozim.
class Rank(models.Model):
    code = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'rank'
        verbose_name = "Lavozim"
        verbose_name_plural = "Lavozim"


# Xodim.
class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=False, blank=True, related_name='employee', db_index=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=100, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    pinfl = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    telegram_chat = models.BigIntegerField(
        null=True, blank=True, unique=True, db_index=True,
        verbose_name="Telegram chat ID",
    )
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):

        if self.division and self.division.directorate:
            self.directorate = self.division.directorate

        if self.directorate and self.directorate.department:
            self.department = self.directorate.department

        if self.department and self.department.organization:
            self.organization = self.department.organization

            old_dep_id = None
            if self.pk:
                old_dep_id = (
                    Employee.objects.filter(pk=self.pk)
                    .values_list("department_id", flat=True)
                    .first()
                )
            if not self.pk or old_dep_id != self.department_id:
                self.region = self.department.region

        super().save(*args, **kwargs)

    def __str__(self):
        parts = [self.last_name, self.first_name, self.father_name]
        return " ".join(p for p in parts if p) or f"Xodim #{self.pk}"

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.father_name]
        return " ".join(p for p in parts if p) or self.user.username

    class Meta:
        db_table = 'employee'
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"
        permissions = [
            ("boss_employee", "Departamentiga tegishli texnikalarni ko'rish"),
            ("shop_employee", "Materialga javobgar shaxs"),
            ("status_employee", "Statistikani ko'rish"),
            ("permission_employee", "Xodimlarga ruxsatlarni berish"),
            ("report_employee", "Hisobotlarni ko'rish"),
        ]


class Group(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'group'
        verbose_name = "Uskuna turi"
        verbose_name_plural = "Uskuna turlari"


class Contract(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    unit = models.CharField(max_length=100, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'contract'
        verbose_name = "Shartnoma"
        verbose_name_plural = "Shartnomalar"


class Category(models.Model):
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'category'
        verbose_name = "Uskuna kategoriyasi"
        verbose_name_plural = "Uskuna kategoriyalari"


class Technics(models.Model):
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('free', "Bo'sh"),
        ('active', 'Aktiv'),
        ('repair', 'Ta’mirda'),
        ('defect', 'Yaroqsiz')
    ], default='free', db_index=True)
    name = models.CharField(max_length=100)
    parametr = models.CharField(max_length=100, null=True, blank=True)
    inventory = models.CharField(max_length=50, null=True, blank=True)
    serial = models.CharField(max_length=50, null=True, blank=True)
    mac = models.CharField(max_length=50, null=True, blank=True)
    ip = models.CharField(max_length=50, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=True)
    qr_code = models.ImageField(upload_to='qk/', blank=True, null=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("technics_detail", args=[self.pk])

    def get_qr_data(self):
        return f"https://report.imv.uz{self.get_absolute_url()}"

    def generate_qr_code(self, save=True):
        qr_data = self.get_qr_data()

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")

        file_name = f"technics_{self.pk}.png"
        self.qr_code.save(file_name, File(buffer), save=False)
        buffer.close()

        if save:
            super().save(update_fields=["qr_code"])

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not self.serial or not self.serial.strip():
            self.serial = "B/N"

        if self.employee:
            self.organization_id = self.employee.organization_id
            self.department_id = self.employee.department_id
            self.directorate_id = self.employee.directorate_id
            self.division_id = self.employee.division_id

        if self.employee_id or self.department_id or self.directorate_id or self.division_id:
            self.status = 'active'
        else:
            self.status = 'free'

        super().save(*args, **kwargs)

        if is_new and not self.qr_code:
            self.generate_qr_code(save=True)

    class Meta:
        db_table = 'technics'
        verbose_name = "Uskuna"
        verbose_name_plural = "Uskunalar"


class StructureCategory(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'structurecategory'
        verbose_name = "Qurulma kategoriyasi"
        verbose_name_plural = "Qurulma kategoriyalari"


class Structure(models.Model):
    category = models.ForeignKey(StructureCategory, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('free', "Bo'sh"),
        ('active', 'Aktiv'),
        ('repair', 'Ta’mirda'),
        ('defect', 'Yaroqsiz')
    ], default='free', db_index=True)
    name = models.CharField(max_length=100)
    parametr = models.CharField(max_length=100, null=True, blank=True)
    inventory = models.CharField(max_length=50, null=True, blank=True)
    serial = models.CharField(max_length=50, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.status not in ('repair', 'defect'):
            self.status = 'active' if self.technics_id else 'free'
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'structure'
        verbose_name = "Qurulma"
        verbose_name_plural = "Qurulmalar"


class Unit(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'unit'
        verbose_name = "Material birligi"
        verbose_name_plural = "Material birliglari"


class MaterialCategory(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'materialcategory'
        verbose_name = "Material kategoriyasi"
        verbose_name_plural = "Material kategoriyalari"


class Material(models.Model):
    category = models.ForeignKey(MaterialCategory, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=300)
    number = models.PositiveIntegerField(default=1)
    code = models.CharField(max_length=15, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='material/', null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'material'
        verbose_name = "Material"
        verbose_name_plural = "Materiallar"
        permissions = [
            ("all_material_employee", "Barcha xodimlarni ko'rish"),
        ]


class MaterialEmployee(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    category = models.ForeignKey(MaterialCategory, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.employee} → {self.category}"

    class Meta:
        db_table = 'materialemployee'
        verbose_name = "Material Category Employee"
        verbose_name_plural = "Material Category Employee"


class Goal(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'goal'
        verbose_name = "Ariza kategoriyasi"
        verbose_name_plural = "Ariza kategoriyalari"


class Order(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)

    sender = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='order_sender', null=True, blank=True, db_index=True)
    message_sender = models.TextField(null=True, blank=True)
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    rating = models.PositiveIntegerField(null=True, blank=True)

    receiver = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='order_receiver', null=True, blank=True, db_index=True)
    message_receiver = models.TextField(null=True, blank=True)

    user = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='order_user', null=True, blank=True, db_index=True)
    message_user = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=[
        ('viewed', 'Yangi'),
        ('process', 'Jarayonda'),
        ('finished', 'Tayyorlandi'),
        ('approved', 'Tasdiqlandi'),
        ('accepted', 'Qabul qilindi'),
        ('canceled', 'Bekor qilindi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed', db_index=True)
    receiver_seen = models.BooleanField(default=False)
    sender_seen = models.BooleanField(default=False)
    user_seen = models.BooleanField(default=False)

    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    date_process = models.DateTimeField(null=True, blank=True)
    date_finished = models.DateTimeField(null=True, blank=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    date_accepted = models.DateTimeField(null=True, blank=True)
    date_canceled = models.DateTimeField(null=True, blank=True)
    date_rejected = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields", None)

        now = timezone.now()

        status_date_map = {
            "process": "date_process",
            "finished": "date_finished",
            "approved": "date_approved",
            "accepted": "date_accepted",
            "canceled": "date_canceled",
            "rejected": "date_rejected",
        }

        date_field = status_date_map.get(self.status)
        if date_field:
            setattr(self, date_field, now)
            if update_fields:
                update_fields.append(date_field)

        super().save(*args, **kwargs)

    @property
    def materials_all(self):
        return self.materials.select_related('material').all()

    def __str__(self):
        return f" # {self.id}"

    class Meta:
        db_table = 'order'
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        permissions = [
            ("confirm_order", "Arizani tasdiqlash"),
        ]


class OrderMaterial(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name="materials", db_index=True)
    user = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='ordermaterial_user', null=True, blank=True, db_index=True)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, null=True, blank=True, db_index=True)
    number = models.PositiveIntegerField(default=1)
    given = models.PositiveIntegerField(null=True, blank=True)

    @property
    def given_summa(self):
        qty = self.given if self.given is not None else self.number
        price = self.material.price if self.material and self.material.price else 0
        return qty * price

    def __str__(self):
        return f"{self.order} → {self.material} x {self.number}"

    class Meta:
        db_table = 'ordermaterial'
        verbose_name = "Ariza materiali"
        verbose_name_plural = "Arizalar materiallari"


class OrderGoal(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.employee} → {self.goal}"

    class Meta:
        db_table = 'OrderGoal'
        verbose_name = "xodimlar ariza kategoriyasi"
        verbose_name_plural = "xodimlar ariza kategoriyasi"


class MaterialUser(models.Model):
    sender = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='sender', null=True, blank=True, db_index=True)
    receiver = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='receiver', null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.sender} - {self.receiver}"

    class Meta:
        db_table = 'materialuser'
        verbose_name = "Material user"
        verbose_name_plural = "Material userlar"



class Deed(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)

    sender = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='deed_sender', null=True, blank=True ,db_index=True)
    message_sender = models.TextField(null=True, blank=True)
    status_sender = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed', db_index=True)
    date_sender = models.DateTimeField(null=True, blank=True)

    receiver = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='deed_receiver', null=True, blank=True, db_index=True)
    message_receiver = models.TextField(null=True, blank=True)
    status_receiver = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed', db_index=True)
    date_receiver = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='deed_user', null=True, blank=True, db_index=True)
    user_edit = models.BooleanField(default=True)
    message_user = models.TextField(null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('document', 'Dalolatnoma'),
        ('svod', 'Yakuniy hisobot'),
        ('reestr', 'Reestr'),
        ('act', 'Akt'),
        ('petition', 'Talabnoma'),
    ], default='act', db_index=True)

    file = models.FileField(upload_to='deed/', validators=[validate_file_extension])
    code = models.CharField(max_length=10, null=True, blank=True, unique=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, related_name='order', null=True, blank=True ,db_index=True)
    orders = models.ManyToManyField(Order, related_name='deeds', blank=True)

    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def generate_code(self):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=10))

    def save(self, *args, **kwargs):
        if self.pk:
            old = Deed.objects.filter(pk=self.pk).first()
            if old and self.file and old.file and old.file != self.file:
                old.file.delete(save=False)

        if not self.code:
            while True:
                new_code = self.generate_code()
                if not Deed.objects.filter(code=new_code).exists():
                    self.code = new_code
                    break

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Dalolatnoma {self.code}"

    class Meta:
        db_table = 'deed'
        verbose_name = "Xujat"
        verbose_name_plural = "Xujatlar"



class DeedConsent(models.Model):
    deed = models.ForeignKey(Deed, on_delete=models.CASCADE, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    message = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutilmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed', db_index=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Kelishuvchi #{self.id} → {self.employee}"

    class Meta:
        db_table = 'deedconsent'
        verbose_name = "Xujat kelishuvchisi"
        verbose_name_plural = "Xujat kelishuvchilari"


class Liable(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.employee} → {self.contract} → {self.category}"

    class Meta:
        db_table = 'Liable'
        verbose_name = "xodimlar kategoriyasi"
        verbose_name_plural = "xodimlar kategoriyasi"


class MaterialMovement(models.Model):
    STATUS_CHOICES = [
        ('created', "Qo'shildi"),
        ('edited', 'Taxrirlandi'),
        ('deleted', "O'chirildi"),
        ('assigned', 'Biriktirildi'),
    ]
    user = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True, related_name='movement_created')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, null=True, blank=True, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True, related_name='movement_received')
    income = models.PositiveIntegerField(null=True, blank=True)
    outcome = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', db_index=True)
    body = models.TextField(null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_status_display()} | {self.material} | {self.employee}"

    class Meta:
        db_table = 'material_movement'
        verbose_name = "Material harakati"
        verbose_name_plural = "Material harakatlari"
        ordering = ['-date_creat']