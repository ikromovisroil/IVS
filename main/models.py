from django.contrib.auth.models import User
from .validators import *
from django.utils import timezone
import random
import string
import qrcode
from io import BytesIO
from django.core.files import File
from django.db import models
from django.urls import reverse


# Organizator.
class Organization(models.Model):
    name = models.CharField(max_length=200)
    contract = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.name}"


    class Meta:
        db_table = 'organization'
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"


# Departament.
class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'department'
        verbose_name = "Departament"
        verbose_name_plural = "Departamentlar"


# Boshqarma.
class Directorate(models.Model):
    department = models.ForeignKey(Department, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'directorate'
        verbose_name = "Boshqarma"
        verbose_name_plural = "Boshqarmalar"


# Bo'lim.
class Division(models.Model):
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'division'
        verbose_name = "Bo'lim"
        verbose_name_plural = "Bo'limlar"


# Lavozim.
class Rank(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'rank'
        verbose_name = "Bo'lim"
        verbose_name_plural = "Bo'limlar"


# viloyat.
class Region(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'region'
        verbose_name = "Xudud"
        verbose_name_plural = "Xududlar"


class Rol(models.Model):
    employee = models.OneToOneField("Employee", on_delete=models.CASCADE, null=True, blank=True)
    full = models.BooleanField(default=False, db_index=True)
    confirm = models.BooleanField(default=False, db_index=True)
    order = models.BooleanField(default=False, db_index=True)
    boss = models.BooleanField(default=False, db_index=True)
    shop = models.BooleanField(default=False, db_index=True)
    akt = models.BooleanField(default=False, db_index=True)
    status = models.BooleanField(default=False, db_index=True)
    technics = models.BooleanField(default=False, db_index=True)
    technics_edit = models.BooleanField(default=False, db_index=True)
    material = models.BooleanField(default=False, db_index=True)
    material_edit = models.BooleanField(default=False, db_index=True)


    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'rol'
        verbose_name = "Rol"
        verbose_name_plural = "Rollar"


# Xodim.
class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='employee',db_index=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=100, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    phone = models.CharField(max_length=50,null=True,blank=True)
    pinfl = models.CharField(max_length=20, null=True, blank=True,db_index=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Agar division tanlangan bo‘lsa → directorate avtomatik to‘lsin
        if self.division and self.division.directorate:
            self.directorate = self.division.directorate

        # Agar directorate tanlangan bo‘lsa → department avtomatik to‘lsin
        if self.directorate and self.directorate.department:
            self.department = self.directorate.department

        # Agar department tanlangan bo‘lsa → organization avtomatik to‘lsin
        if self.department and self.department.organization:
            self.organization = self.department.organization

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


# Category.
class Group(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'group'
        verbose_name = "Uskuna turi"
        verbose_name_plural = "Uskuna turlari"


# Category.
class Category(models.Model):
    group = models.ForeignKey(Group, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'category'
        verbose_name = "Uskuna kategoriyasi"
        verbose_name_plural = "Uskuna kategoriyalari"


# texnika.
class Technics(models.Model):
    group = models.ForeignKey(Group, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('free', "Bo'sh"),
        ('active', 'Aktiv'),
        ('repair', 'Ta’mirda'),
        ('defect', 'Yaroqsiz')
    ], default='free',db_index=True)
    name = models.CharField(max_length=100)
    parametr = models.CharField(max_length=100,null=True,blank=True)
    inventory = models.CharField(max_length=50,null=True,blank=True)
    serial = models.CharField(max_length=50,null=True,blank=True)
    mac = models.CharField(max_length=50, null=True, blank=True)
    ip = models.CharField(max_length=50,null=True,blank=True)
    price = models.DecimalField(max_digits=12,decimal_places=2,null=True, blank=True)
    year = models.CharField(max_length=50,null=True,blank=True)
    is_active = models.BooleanField(default=True)
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

        if self.employee:
            self.status = 'active'
            self.organization_id = self.employee.organization_id
            self.department_id = self.employee.department_id
            self.directorate_id = self.employee.directorate_id
            self.division_id = self.employee.division_id

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
    category = models.ForeignKey(StructureCategory, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
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
    price = models.DecimalField(max_digits=12,decimal_places=2,null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'structure'
        verbose_name = "Qurulma"
        verbose_name_plural = "Qurulmalar"


# birligi
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


# material.
class Material(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    category = models.ForeignKey(MaterialCategory, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('free', "Bo'sh"),
        ('active', 'Aktiv'),
        ('repair', 'Ta’mirda'),
        ('defect', 'Yaroqsiz')
    ], default='free',db_index=True)
    name = models.CharField(max_length=300)
    number = models.PositiveIntegerField(default=1)
    code = models.CharField(max_length=10, null=True, blank=True)
    price = models.DecimalField(max_digits=12,decimal_places=2,null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'material'
        verbose_name = "Material"
        verbose_name_plural = "Materiallar"


# maqsad.
class Goal(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'goal'
        verbose_name = "Ariza kategoriyasi"
        verbose_name_plural = "Ariza kategoriyalari"


# zayafka.
class Order(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    user = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='order_user', null=True, blank=True, db_index=True)

    sender = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='order_sender', null=True, blank=True, db_index=True)
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    body = models.TextField(null=True, blank=True)
    rating = models.PositiveIntegerField(null=True, blank=True)

    receiver = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='order_receiver',null=True, blank=True,db_index=True)
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)

    status = models.CharField(max_length=20, choices=[
        ('viewed', 'Yangi'),
        ('accepted', 'Jarayonda'),
        ('finished', 'Yakunlandi'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed',db_index=True)
    receiver_seen = models.BooleanField(default=False)
    # --- Sana maydonlari ---
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    # Har bir status uchun alohida vaqt
    date_accepted = models.DateTimeField(null=True, blank=True)
    date_finished = models.DateTimeField(null=True, blank=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    date_rejected = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # ACCEPTED vaqtini avtomatik saqlash
        if self.status == "accepted":
            self.date_accepted = timezone.now()

        # finished uchun
        if self.status == "finished":
            self.date_finished = timezone.now()

        # APPROVED uchun
        if self.status == "approved":
            self.date_approved = timezone.now()

        # REJECTED uchun
        if self.status == "rejected":
            self.date_rejected = timezone.now()

        super().save(*args, **kwargs)

    @property
    def materials_all(self):
        return self.materials.select_related('material').all()

    def __str__(self):
        return f"Order #{self.id}"

    class Meta:
        db_table = 'order'
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"


# zayafkadan soralgan materiali.
class OrderMaterial(models.Model):
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="materials", db_index=True)
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    number = models.PositiveIntegerField(default=1)
    given = models.PositiveIntegerField(null=True, blank=True)

    @property
    def given_summa(self):
        qty = self.given if self.given is not None else self.number
        price = self.material.price if self.material and self.material.price else 0
        return qty * price

    def __str__(self):
        return f"{self.order} → {self.material or self.technics} x {self.number}"

    class Meta:
        db_table = 'ordermaterial'
        verbose_name = "Ariza materiali"
        verbose_name_plural = "Arizalar materiallari"


class MaterialUser(models.Model):
    sender = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='sender', null=True, blank=True ,db_index=True)
    receiver = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='receiver', null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.sender} - {self.receiver}"

    class Meta:
        db_table = 'materialuser'
        verbose_name = "Material user"
        verbose_name_plural = "Material userlar"


class Deed(models.Model):
    sender = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='deed_sender', null=True, blank=True ,db_index=True)
    message_sender = models.TextField(null=True, blank=True)
    status_sender = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed', db_index=True)
    date_sender = models.DateTimeField(null=True, blank=True)
    sender_seen = models.BooleanField(default=False, db_index=True)

    receiver = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='deed_receiver', null=True, blank=True, db_index=True)
    message_receiver = models.TextField(null=True, blank=True)
    status_receiver = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed', db_index=True)
    date_receiver = models.DateTimeField(null=True, blank=True)
    receiver_seen = models.BooleanField(default=False, db_index=True)

    user = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name='deed_user', null=True, blank=True, db_index=True)
    message_user = models.TextField(null=True, blank=True)
    body = models.TextField(null=True, blank=True)

    file_type = models.BooleanField(default=False)
    file = models.FileField(upload_to='deed/', validators=[validate_file_extension])
    code = models.CharField(max_length=10, null=True, blank=True, db_index=True)

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
    deed = models.ForeignKey(Deed, on_delete=models.CASCADE,db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    message = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed',db_index=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Kelishuvchi #{self.id} → {self.employee}"

    class Meta:
        db_table = 'deedconsent'
        verbose_name = "Xujat kelishuvchisi"
        verbose_name_plural = "Xujat kelishuvchilari"


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


class Liable(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.employee} → {self.contract} → {self.category}"

    class Meta:
        db_table = 'Liable'
        verbose_name = "Shartnomaga javobgar shaxs"
        verbose_name_plural = "Shartnomaga javobgar shaxslar"
