"""Bildirishnomalar markazi: yozish, guruhlash, sayt sahifasi, API, tozalash."""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Notification
from core.notifications import mark_read_by_tag, record, safe_url
from core.tasks import cleanup_old_notifications
from main.push_views import notify_order_status_change, send_push_notification
from main.testing import make_employee, make_goal, make_org, make_region
from main.models import Deed, DeedConsent, Order


class RecordTests(TestCase):
    def setUp(self):
        _, self.emp = make_employee(make_org("client"), make_region())

    def test_kind_from_tag(self):
        cases = {
            "order-status-5-finished": "order", "order-new-3": "order", "deed-sender-2": "deed",
            "deed-watcher-2": "deed", "meeting-reminder-9": "meeting", "chat-7": "chat", "chat-ai-7": "chat",
            "": "system", "boshqa-narsa": "system",
        }
        for tag, kind in cases.items():
            record(self.emp, "T", tag=tag)
            self.assertEqual(Notification.objects.filter(employee=self.emp).order_by("-id").first().kind, kind, tag)
            Notification.objects.all().delete()

    def test_same_unread_tag_is_grouped_and_counted(self):
        record(self.emp, "Ali", "salom", "/chat/", tag="chat-1")
        record(self.emp, "Ali", "qalaysiz", "/chat/", tag="chat-1")
        record(self.emp, "Ali", "yana", "/chat/", tag="chat-1")
        self.assertEqual(Notification.objects.count(), 1)
        item = Notification.objects.get()
        self.assertEqual((item.count, item.body), (3, "yana"))

    def test_read_notification_is_not_reused(self):
        first = record(self.emp, "Ali", tag="chat-1")
        mark_read_by_tag(self.emp, "chat-1")
        second = record(self.emp, "Ali", tag="chat-1")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(Notification.objects.count(), 2)

    def test_unique_tags_make_separate_rows(self):
        record(self.emp, "A", tag="order-status-1-process")
        record(self.emp, "A", tag="order-status-1-finished")
        self.assertEqual(Notification.objects.count(), 2)

    def test_external_url_is_neutralized(self):
        for bad in ("https://evil.example/", "//evil.example", "javascript:alert(1)", ""):
            self.assertEqual(safe_url(bad), "/")
        self.assertEqual(safe_url("/order/sender/"), "/order/sender/")

    def test_none_employee_and_errors_do_not_raise(self):
        self.assertIsNone(record(None, "T"))
        with mock.patch("core.notifications.Notification.objects.create", side_effect=RuntimeError("boom")):
            self.assertIsNone(record(self.emp, "T"))

    def test_long_values_are_truncated(self):
        record(self.emp, "x" * 500, "y" * 2000, "/" + "z" * 1000, tag="t" * 500)
        item = Notification.objects.get()
        self.assertLessEqual(len(item.title), 200)
        self.assertLessEqual(len(item.body), 500)
        self.assertLessEqual(len(item.url), 300)
        self.assertLessEqual(len(item.tag), 120)


@mock.patch("main.tasks.send_fcm_notification_task.delay")
@mock.patch("main.tasks.send_push_notification_task.delay")
class PushHookTests(TestCase):
    """Markaziy `send_push_notification` hamma voqealarni tarixga ham yozadi."""

    def setUp(self):
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        _, self.sender = make_employee(self.client_org, self.region)

    def test_push_is_recorded(self, push, fcm):
        send_push_notification(self.sender, "Sarlavha", "Matn", "/order/sender/", tag="order-new-1")
        item = Notification.objects.get(employee=self.sender)
        self.assertEqual((item.kind, item.title, item.url), ("order", "Sarlavha", "/order/sender/"))
        push.assert_called_once()

    def test_order_status_change_creates_notification_for_sender(self, push, fcm):
        order = Order.objects.create(sender=self.sender, goal=make_goal(self.worker_org), status="finished")
        notify_order_status_change(order)
        item = Notification.objects.get(employee=self.sender)
        self.assertEqual(item.kind, "order")
        self.assertIn(f"#{order.id}", item.body)

    def test_history_survives_push_failure(self, push, fcm):
        push.side_effect = RuntimeError("broker yo'q")
        with self.assertRaises(RuntimeError):
            send_push_notification(self.sender, "T", "B", "/", tag="deed-sender-1")
        self.assertEqual(Notification.objects.filter(employee=self.sender, kind="deed").count(), 1)

    def test_meeting_reminder_is_recorded(self, push, fcm):
        from chat.meetings import send_due_reminders
        from chat.models import Meeting

        Meeting.objects.create(
            organizer=self.sender, title="Majlis", start_at=timezone.now() + timedelta(minutes=5),
            zoom_id="1", join_url="https://zoom.us/j/1",
        )
        send_due_reminders()
        item = Notification.objects.get(employee=self.sender)
        self.assertEqual((item.kind, item.url), ("meeting", "/chat/meetings/"))


@mock.patch("main.tasks.send_fcm_notification_task.delay")
@mock.patch("main.tasks.send_push_notification_task.delay")
class ChatNotificationTests(TestCase):
    def setUp(self):
        org = make_org("client")
        self.user_a, self.a = make_employee(org, first="Ali", last="Aliyev")
        self.user_b, self.b = make_employee(org, first="Bobur", last="Boboyev")

    def test_messages_grouped_per_conversation_and_cleared_when_opened(self, push, fcm):
        from chat.models import Message
        from chat.services import get_or_create_direct_conversation, mark_read
        from chat.views import _notify_recipients

        conv = get_or_create_direct_conversation(self.a, self.b)
        for text in ("salom", "yaxshimisiz", "ishlar qalay"):
            msg = Message.objects.create(conversation=conv, sender=self.a, body=text)
            _notify_recipients(conv, self.a, msg)
        item = Notification.objects.get(employee=self.b, kind="chat")
        self.assertEqual(item.count, 3)
        self.assertFalse(Notification.objects.filter(employee=self.a).exists())   # yuboruvchiga bildirishnoma yo'q

        mark_read(conv, self.b)                  # suhbat ochildi
        item.refresh_from_db()
        self.assertTrue(item.is_read)


class NotificationApiTests(TestCase):
    def setUp(self):
        org = make_org("client")
        self.user, self.emp = make_employee(org, make_region())
        _, self.other = make_employee(org, make_region())
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_list_filters_and_unread_total(self):
        record(self.emp, "Ariza", tag="order-new-1")
        record(self.emp, "Hujjat", tag="deed-sender-1")
        record(self.other, "Begona", tag="order-new-9")
        data = self.api.get("/api/v1/notifications/").json()
        self.assertEqual({n["title"] for n in data["results"]}, {"Ariza", "Hujjat"})
        self.assertEqual(data["unread"], 2)
        only_deed = self.api.get("/api/v1/notifications/", {"kind": "deed"}).json()
        self.assertEqual([n["title"] for n in only_deed["results"]], ["Hujjat"])
        mark_read_by_tag(self.emp, "deed-sender-1")
        unread = self.api.get("/api/v1/notifications/", {"unread": "1"}).json()
        self.assertEqual([n["title"] for n in unread["results"]], ["Ariza"])

    def test_unread_count_read_and_read_all(self):
        first = record(self.emp, "A", tag="order-new-1")
        record(self.emp, "B", tag="deed-sender-1")
        self.assertEqual(self.api.get("/api/v1/notifications/unread-count/").json(), {"unread": 2})
        response = self.api.post(f"/api/v1/notifications/{first.id}/read/")
        self.assertTrue(response.json()["is_read"])
        result = self.api.post("/api/v1/notifications/read-all/", {}, format="json").json()
        self.assertEqual(result, {"updated": 1, "unread": 0})

    def test_cannot_read_someone_elses(self):
        item = record(self.other, "X", tag="order-new-1")
        self.assertEqual(self.api.post(f"/api/v1/notifications/{item.id}/read/").status_code, 404)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get("/api/v1/notifications/").status_code, 401)


class CleanupTests(TestCase):
    def test_old_notifications_are_deleted(self):
        _, emp = make_employee(make_org("client"))
        old = record(emp, "Eski", tag="order-new-1")
        new = record(emp, "Yangi", tag="order-new-2")
        Notification.objects.filter(pk=old.pk).update(date_creat=timezone.now() - timedelta(days=100))
        result = cleanup_old_notifications()
        self.assertEqual(result["deleted"], 1)
        self.assertTrue(Notification.objects.filter(pk=new.pk).exists())
        self.assertFalse(Notification.objects.filter(pk=old.pk).exists())


class NewOrderNotificationTests(TestCase):
    """Ariza "Yangi" holatdan chiqqach, "yangi ariza" bildirishnomasi hamma ijrochida o'qilgan bo'ladi."""

    def setUp(self):
        atm = make_org("worker")
        region = make_region()
        goal = make_goal(atm, "Kompyuter")
        _, self.sender = make_employee(make_org("client"), region)
        _, self.a = make_employee(atm, region)
        _, self.b = make_employee(atm, region)
        self.order = Order.objects.create(sender=self.sender, goal=goal, status="viewed")
        self.other = Order.objects.create(sender=self.sender, goal=goal, status="viewed")
        for emp in (self.a, self.b):
            for o in (self.order, self.other):
                record(emp, "Yangi ariza yuborildi", tag=f"order-new-{o.id}")

    def unread(self, emp):
        return Notification.objects.filter(employee=emp, is_read=False).count()

    def test_taken_order_clears_notification_for_everyone(self):
        self.assertEqual((self.unread(self.a), self.unread(self.b)), (2, 2))
        self.order.status = "process"
        self.order.receiver = self.a
        self.order.save(update_fields=["status", "receiver"])
        # ikkala ijrochida ham faqat boshqa (hali yangi) ariza qoldi
        self.assertEqual((self.unread(self.a), self.unread(self.b)), (1, 1))
        self.assertTrue(Notification.objects.filter(employee=self.b, tag=f"order-new-{self.other.id}", is_read=False).exists())

    def test_rejected_or_canceled_order_also_clears(self):
        for status in ("rejected", "canceled"):
            Order.objects.filter(pk=self.other.pk).update(status="viewed")
            record(self.b, "Yangi ariza yuborildi", tag=f"order-new-{self.other.id}")
            self.other.refresh_from_db()
            self.other.status = status
            self.other.save(update_fields=["status"])
            self.assertFalse(Notification.objects.filter(tag=f"order-new-{self.other.id}", is_read=False).exists(), status)

    def test_new_or_unchanged_order_keeps_notification(self):
        self.order.save()   # holat "viewed" — hech narsa o'zgarmaydi
        self.assertEqual((self.unread(self.a), self.unread(self.b)), (2, 2))

    def test_command_closes_stale_notifications(self):
        from django.core.management import call_command
        Order.objects.filter(pk=self.order.pk).update(status="process")   # signalsiz (eski ma'lumot)
        self.assertEqual(self.unread(self.a), 2)
        call_command("close_stale_order_notifications", "--dry-run", stdout=mock.MagicMock())
        self.assertEqual(self.unread(self.a), 2)
        call_command("close_stale_order_notifications", stdout=mock.MagicMock())
        self.assertEqual((self.unread(self.a), self.unread(self.b)), (1, 1))


class DeedNotificationClosingTests(TestCase):
    """Hujjatni imzolash/kelishish — "imzolashga/kelishishga yuborildi" bildirishnomasi sahifaga kirmasdan ham o'chadi."""

    def setUp(self):
        org, region = make_org("client"), make_region()
        _, self.signer = make_employee(org, region)
        _, self.agreer = make_employee(org, region)
        self.deed = Deed.objects.create(organization=org, sender=self.signer, file="deed/x.pdf")
        self.consent = DeedConsent.objects.create(deed=self.deed, employee=self.agreer)
        record(self.signer, "Hujjat imzolashga yuborildi", tag=f"deed-sender-{self.deed.pk}")
        record(self.agreer, "Hujjat kelishishga yuborildi", tag=f"deed-watcher-{self.deed.pk}")

    def unread(self, emp):
        return Notification.objects.filter(employee=emp, is_read=False).count()

    def test_signing_closes_signer_notification_only(self):
        self.deed.status_sender = "approved"
        self.deed.save(update_fields=["status_sender"])
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (0, 1))

    def test_agreeing_closes_watcher_notification(self):
        self.consent.status = "approved"
        self.consent.save(update_fields=["status"])
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (1, 0))

    def test_pending_deed_keeps_notifications(self):
        self.deed.save()
        self.consent.save()
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (1, 1))

    def test_rejected_deed_closes_everyone(self):
        self.deed.status_sender = "rejected"
        self.deed.save(update_fields=["status_sender"])
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (0, 0))

    def test_command_closes_stale_deed_notifications(self):
        from django.core.management import call_command
        Deed.objects.filter(pk=self.deed.pk).update(status_sender="approved")                  # signalsiz (eski ma'lumot)
        DeedConsent.objects.filter(pk=self.consent.pk).update(status="approved")
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (1, 1))
        call_command("close_stale_deed_notifications", "--dry-run", stdout=mock.MagicMock())
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (1, 1))
        call_command("close_stale_deed_notifications", stdout=mock.MagicMock())
        self.assertEqual((self.unread(self.signer), self.unread(self.agreer)), (0, 0))


class OrderMeetingNotificationClosingTests(TestCase):
    def setUp(self):
        self.worker_org = make_org("worker")
        _, self.sender = make_employee(make_org("client"), make_region())

    def test_orders_seen_closes_status_notifications(self):
        from main.context_processors import mark_orders_seen
        record(self.sender, "Ariza holati o'zgardi", tag="order-status-5-finished")
        record(self.sender, "Chat", tag="chat-1")
        mark_orders_seen(self.sender)
        self.assertEqual(list(Notification.objects.filter(employee=self.sender, is_read=False).values_list("tag", flat=True)), ["chat-1"])

    def _meeting(self, **kw):
        from chat.models import Meeting
        return Meeting.objects.create(
            organizer=self.sender, title="Majlis", start_at=timezone.now() + timedelta(minutes=5),
            zoom_id="1", join_url="https://zoom.us/j/1", **kw,
        )

    @mock.patch("main.tasks.send_fcm_notification_task.delay")
    @mock.patch("main.tasks.send_push_notification_task.delay")
    def test_cancelled_meeting_closes_reminder(self, push, fcm):
        from chat.meetings import send_due_reminders
        from chat.models import Meeting
        m = self._meeting()
        send_due_reminders()
        self.assertEqual(Notification.objects.filter(employee=self.sender, is_read=False).count(), 1)
        m.status = Meeting.STATUS_CANCELLED
        m.save(update_fields=["status"])
        self.assertEqual(Notification.objects.filter(employee=self.sender, is_read=False).count(), 0)

    @mock.patch("main.tasks.send_fcm_notification_task.delay")
    @mock.patch("main.tasks.send_push_notification_task.delay")
    def test_started_meeting_closes_reminder(self, push, fcm):
        from chat.meetings import send_due_reminders
        from chat.models import Meeting
        m = self._meeting()
        send_due_reminders()
        Meeting.objects.filter(pk=m.pk).update(start_at=timezone.now() - timedelta(minutes=1))
        send_due_reminders()
        self.assertEqual(Notification.objects.filter(employee=self.sender, is_read=False).count(), 0)
