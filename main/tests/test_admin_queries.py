"""Admin ro'yxatlari qatorlar soniga bog'liq bo'lmagan (N+1 yo'q) so'rovlar bilan ochiladi."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from main.models import Deed, Order
from main.testing import make_employee, make_goal, make_org, make_region


class AdminChangelistQueriesTests(TestCase):
    def setUp(self):
        self.region = make_region()
        self.worker = make_org("worker")
        self.client_org = make_org("client")
        self.goal = make_goal(self.worker)
        admin = get_user_model().objects.create_superuser("adm", "a@a.uz", "x")
        self.client.force_login(admin)

    def _queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(ctx)

    def _grow(self, make, url):
        make(2)
        few = self._queries(url)
        make(10)
        many = self._queries(url)
        self.assertLessEqual(many, few + 2, (url, few, many))

    def test_employee_list_has_no_n_plus_one(self):
        def make(n):
            for _ in range(n):
                make_employee(self.worker, self.region)
        self._grow(make, "/ivc_service_admin_panel/main/employee/")

    def test_order_and_deed_lists_have_no_n_plus_one(self):
        def make(n):
            for _ in range(n):
                _, s = make_employee(self.client_org, self.region)
                _, r = make_employee(self.worker, self.region)
                order = Order.objects.create(sender=s, receiver=r, goal=self.goal, status="viewed")
                deed = Deed.objects.create(sender=s, receiver=r, user=s, organization=self.client_org)
                deed.orders.add(order)
        self._grow(make, "/ivc_service_admin_panel/main/order/")
        self._grow(make, "/ivc_service_admin_panel/main/deed/")

    def test_change_forms_do_not_render_every_employee_and_order(self):
        """Hujjat/ariza sahifasi bazadagi hamma xodim va arizani <select> ga chiqarmaydi (qotib qolishning sababi shu edi)."""
        _, s = make_employee(self.client_org, self.region, last="Yuboruvchi")
        _, r = make_employee(self.worker, self.region, last="Qabulqiluvchi")
        order = Order.objects.create(sender=s, receiver=r, goal=self.goal, status="viewed")
        deed = Deed.objects.create(sender=s, receiver=r, user=s, organization=self.client_org)
        deed.orders.add(order)
        others = [make_employee(self.worker, self.region, last=f"Begona{i}")[1] for i in range(5)]
        extra_orders = [Order.objects.create(sender=s, receiver=r, goal=self.goal, status="viewed") for _ in range(5)]

        html = self.client.get(f"/ivc_service_admin_panel/main/deed/{deed.pk}/change/").content.decode()
        for e in others:
            self.assertNotIn(e.last_name, html)
        for o in extra_orders:
            self.assertNotIn(str(o), html)

        html = self.client.get(f"/ivc_service_admin_panel/main/order/{order.pk}/change/").content.decode()
        for e in others:
            self.assertNotIn(e.last_name, html)

    def test_every_admin_page_opens(self):
        """Hamma admin ro'yxati va "qo'shish" formasi ochiladi (autocomplete uchun search_fields yetarli, sozlama buzilmagan)."""
        from django.contrib import admin
        from django.urls import reverse
        for model in admin.site._registry:
            if model._meta.app_label not in ("main", "chat", "core"):
                continue
            info = (model._meta.app_label, model._meta.model_name)
            self.assertEqual(self.client.get(reverse("admin:%s_%s_changelist" % info)).status_code, 200, model)
            resp = self.client.get(reverse("admin:%s_%s_add" % info))
            self.assertIn(resp.status_code, (200, 403), model)      # 403: yaratish yopilgan modellar (Meeting, AuditLog...)

    def test_big_inline_replaced_by_filtered_links(self):
        from chat.models import Conversation, Message
        _, a = make_employee(self.worker, self.region)
        _, b = make_employee(self.worker, self.region)
        conv = Conversation.objects.create(kind="direct", participant_1=a, participant_2=b)
        for i in range(5):
            Message.objects.create(conversation=conv, sender=a, body=f"Xabar-{i}")
        resp = self.client.get(f"/ivc_service_admin_panel/chat/conversation/{conv.pk}/change/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn("Xabar-0", html)             # xabarlar inline qilib chizilmaydi
        self.assertIn(f"conversation__id__exact={conv.pk}", html)
        listing = self.client.get(f"/ivc_service_admin_panel/chat/message/?conversation__id__exact={conv.pk}")
        self.assertEqual(listing.status_code, 200)
        self.assertIn("Xabar-0", listing.content.decode())

    def test_sync_log_filtered_link_is_allowed(self):
        from core.models import SyncLog
        log = SyncLog.objects.create(total=1, updated=1, blocked=0, skipped=0, errors=0, duration=1, status="success")
        resp = self.client.get(f"/ivc_service_admin_panel/core/syncemployeelog/?sync__id__exact={log.pk}")
        self.assertEqual(resp.status_code, 200)          # ruxsat etilmagan filtr bo'lsa Django ?e=1 ga yo'naltirardi
        page = self.client.get(f"/ivc_service_admin_panel/core/synclog/{log.pk}/change/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(f"sync__id__exact={log.pk}", page.content.decode())

    def test_order_material_can_be_deleted_without_returning_stock(self):
        from main.models import Material, OrderMaterial
        _, s = make_employee(self.client_org, self.region)
        material = Material.objects.create(name="Kartrij", organization=self.worker, employee=s, number=7)
        order = Order.objects.create(sender=s, goal=self.goal, status="viewed")
        om = OrderMaterial.objects.create(order=order, material=material, number=3)
        # alohida sahifadan o'chirish
        url = f"/ivc_service_admin_panel/main/ordermaterial/{om.pk}/delete/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.assertFalse(OrderMaterial.objects.filter(pk=om.pk).exists())
        material.refresh_from_db()
        self.assertEqual(material.number, 7)         # ombor qoldig'i o'zgarmadi (qaytmadi)
        self.assertFalse(Order.objects.filter(pk=order.pk).values_list("status", flat=True).first() != "viewed")
        # ariza ichidagi qatordan o'chirish ham mumkin: o'chirish katagi bor
        om2 = OrderMaterial.objects.create(order=order, material=material, number=2)
        page = self.client.get(f"/ivc_service_admin_panel/main/order/{order.pk}/change/").content.decode()
        self.assertIn("DELETE", page)
