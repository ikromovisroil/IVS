from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify
from .validators import *
from django.utils import timezone

# Slug.
class AutoSlugMixin(models.Model):
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=200)

    class Meta:
        abstract = True

    def get_slug_source(self):
        """
        Har bir modelda slug qaysi maydondan olinadi.
        default → name
        Agar name yo‘q bo‘lsa → full_name
        """
        if hasattr(self, "name"):
            return self.name
        if hasattr(self, "full_name"):
            return self.full_name
        return None

    def save(self, *args, **kwargs):
        # Obyekt mavjud bo‘lsa eski slugni olish
        old_slug = None
        if self.pk:
            try:
                old_slug = self.__class__.objects.get(pk=self.pk).slug
            except self.__class__.DoesNotExist:
                pass

        source = self.get_slug_source()

        if source:
            base_slug = slugify(source)

            # Agar slug yo‘q bo‘lsa yoki value o‘zgargan bo‘lsa
            if not self.slug or old_slug != base_slug:
                slug = base_slug
                counter = 1

                # To‘qnashuvlarni bartaraf qilish
                while (
                    self.__class__.objects.filter(slug=slug)
                    .exclude(pk=self.pk)
                    .exists()
                ):
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                self.slug = slug

        super().save(*args, **kwargs)


# Organizator.
class Organization(AutoSlugMixin, models.Model):
    ORG_TYPES = (
        ('IMV', 'IMV'),
        ('PENSIYA', 'PENSIYA'),
        ('GAZNA', "G'azna"),
        ('IVS', 'IVS'),
    )
    org_type = models.CharField(max_length=10, choices=ORG_TYPES, db_index=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.org_type})"


    class Meta:
        db_table = 'organization'
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"


# Departament.
class Department(AutoSlugMixin, models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'department'
        verbose_name = "Departament"
        verbose_name_plural = "Departamentlar"


# Boshqarma.
class Directorate(AutoSlugMixin, models.Model):
    department = models.ForeignKey(Department, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'directorate'
        verbose_name = "Boshqarma"
        verbose_name_plural = "Boshqarmalar"


# Bo'lim.
class Division(AutoSlugMixin, models.Model):
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
        verbose_name = "Lavozim"
        verbose_name_plural = "Lavozimlar"


# viloyat.
class Region(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'region'
        verbose_name = "Mintaqa"
        verbose_name_plural = "Mintaqalar"


# Xodim.
class Employee(AutoSlugMixin, models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='employee',db_index=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=100, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    STATUS = (('client', 'Mijoz'), ('worker', 'IVS xodimi'))
    status = models.CharField(max_length=20, choices=STATUS, default='client',db_index=True)
    phone = models.CharField(max_length=50,null=True,blank=True)
    pinfl = models.CharField(max_length=20, null=True, blank=True,db_index=True)
    is_boss = models.BooleanField(default=False, db_index=True)
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
        return " ".join(p for p in parts if p) or "—"

    class Meta:
        db_table = 'employee'
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"


# Category.
class Category(AutoSlugMixin, models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'category'
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"


# texnika.
class Technics(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Aktiv'),
        ('free', "Bo'sh"),
        ('repair', 'Ta’mirda'),
        ('defect', 'Brak')
    ], default='active',db_index=True)
    name = models.CharField(max_length=100)
    parametr = models.CharField(max_length=100,null=True,blank=True)
    inventory = models.CharField(max_length=50,null=True,blank=True)
    serial = models.CharField(max_length=50,null=True,blank=True)
    moc = models.CharField(max_length=50, null=True, blank=True)
    ip = models.CharField(max_length=50,null=True,blank=True)
    year = models.CharField(max_length=50,null=True,blank=True)
    body = models.CharField(max_length=200, null=True, blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'technics'
        verbose_name = "Texnika"
        verbose_name_plural = "Texnikalar"


class ExtraTechnics(models.Model):
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Aktiv'),
        ('free', "Bo'sh"),
        ('repair', 'Ta’mirda'),
        ('defect', 'Brak')
    ], default='free', db_index=True)
    name = models.CharField(max_length=50)
    parametr = models.CharField(max_length=100, null=True, blank=True)
    inventory = models.CharField(max_length=50, null=True, blank=True)
    serial = models.CharField(max_length=50, null=True, blank=True)
    moc = models.CharField(max_length=50, null=True, blank=True)
    ip = models.CharField(max_length=50, null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    body = models.CharField(max_length=200, null=True, blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'extratanitor'
        verbose_name = "Qo'shimcha texnika"
        verbose_name_plural = "Qo'shimcha texnikalar"

# material.
class Material(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL,null=True,blank=True,db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Aktiv'),
        ('free', "Bo'sh"),
        ('repair', 'Ta’mirda'),
        ('defect', 'Brak')
    ], default='free',db_index=True)
    name = models.CharField(max_length=300)
    year = models.CharField(max_length=50, null=True, blank=True)
    body = models.CharField(max_length=200, null=True, blank=True)
    number = models.PositiveIntegerField(default=1)
    code = models.CharField(max_length=10, null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'material'
        verbose_name = "material"
        verbose_name_plural = "materiallar"


# mavzu.
class Topic(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'topic'
        verbose_name = "Mavzu"
        verbose_name_plural = "Mavzular"


# maqsad.
class Goal(models.Model):
    name = models.CharField(max_length=200)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'goal'
        verbose_name = "Maqsad"
        verbose_name_plural = "Maqsadlar"


# zayafka.
class Order(models.Model):
    sender = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='orders_sent',db_index=True)
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    receiver = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='orders_received',null=True, blank=True,db_index=True)
    body = models.TextField(null=True, blank=True)
    technics = models.ForeignKey(Technics, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    rating = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('accepted', 'Qabul qilindi'),
        ('finished', 'Yakunlandi'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed',db_index=True)
    type_of_work = models.CharField(max_length=20, choices=[
        ('online', 'onlayin'),
        ('offline', 'oflayin'),
    ], default='online',db_index=True)
    receiver_seen = models.BooleanField(default=False)
    user = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='orders_user', null=True, blank=True,db_index=True)
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
        return self.body or f"Order #{self.id}"

    class Meta:
        db_table = 'order'
        verbose_name = "Zayafka"
        verbose_name_plural = "Zayafkalar"


# zayafkadan soralgan materiali.
class OrderMaterial(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="materials",db_index=True)
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True,db_index=True)
    number = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.order} → {self.material or self.technics} x {self.number}"

    class Meta:
        db_table = 'ordermaterial'
        verbose_name = "Zayafka_material"
        verbose_name_plural = "Zayafka_materiallar"


class Deed(models.Model):
    sender = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='deeds_sent',db_index=True)
    message_sender = models.TextField(null=True, blank=True)

    receiver = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='deeds_received',db_index=True)
    message_receiver = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=[
        ('viewed', 'Kutulmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    ], default='viewed',db_index=True)
    file = models.FileField(upload_to='deed/', validators=[validate_file_extension])
    sender_seen = models.BooleanField(default=False)
    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dalolatnoma #{self.id} → {self.receiver}"

    class Meta:
        db_table = 'deed'
        verbose_name = "Akt"
        verbose_name_plural = "Aktlar"


class Deedconsent(models.Model):
    deed = models.ForeignKey(Deed, on_delete=models.CASCADE,db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,db_index=True)
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
        verbose_name = "Akt_kelishuvchi"
        verbose_name_plural = "Akt_kelishuvchilar"