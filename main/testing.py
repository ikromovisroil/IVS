"""Testlar uchun umumiy yordamchilar (faqat testlarda ishlatiladi)."""
import itertools

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from main.models import Department, Employee, Goal, Organization, Region

User = get_user_model()
_counter = itertools.count(1)


def make_org(type="client", name=None):
    n = next(_counter)
    return Organization.objects.create(name=name or f"Tashkilot {n}", type=type)


def make_region(name=None):
    n = next(_counter)
    return Region.objects.create(name=name or f"Hudud {n}")


def make_department(org, region=None, name=None):
    """Xodim bo'limga biriktirilganda uning hududi bo'limning hududidan olinadi (Employee.save)."""
    n = next(_counter)
    return Department.objects.create(name=name or f"Bo'lim {n}", organization=org, region=region)


def make_goal(org, name=None):
    n = next(_counter)
    return Goal.objects.create(name=name or f"Ariza turi {n}", organization=org)


def grant(user, *perms):
    """perms: "app_label.codename" ko'rinishida."""
    for perm in perms:
        app_label, codename = perm.split(".")
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return User.objects.get(pk=user.pk)   # ruxsat keshi yangilanadi


def make_employee(org=None, region=None, department=None, perms=(), superuser=False,
                  first="Ism", last="Familiya", pinfl=None, active=True, password=None):
    """(user, employee) qaytaradi. Employee User yaratilganda signal orqali o'zi yaratiladi."""
    n = next(_counter)
    user = User.objects.create(username=f"user{n}")
    if password:                      # parol xeshlash sekin: faqat kirish (login) sinaladigan joyda
        user.set_password(password)
    if superuser:
        user.is_superuser = True
        user.is_staff = True
    user.is_active = active
    user.save()
    emp = Employee.objects.get(user=user)
    emp.organization = org
    emp.region = region
    emp.department = department
    emp.first_name = first
    emp.last_name = last
    emp.pinfl = pinfl
    emp.save()
    if perms:
        user = grant(user, *perms)
    else:
        user = User.objects.get(pk=user.pk)
    return user, Employee.objects.get(pk=emp.pk)
