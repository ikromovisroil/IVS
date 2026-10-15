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
from main.models import Order


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


def table_html(response):
    """Faqat sahifa jadvalining ichi (tepadagi qo'ng'iroq menyusidagi qatorlar hisobga olinmaydi)."""
    html = response.content.decode()
    return html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]


class NotificationPageTests(TestCase):
    def setUp(self):
        org = make_org("client")
        self.user, self.emp = make_employee(org, make_region())
        _, self.other = make_employee(org, make_region())
        self.client.force_login(self.user)

    def test_page_lists_only_own_notifications(self):
        record(self.emp, "Menikida", tag="order-new-1")
        record(self.other, "Boshqaniki", tag="order-new-2")
        response = self.client.get(reverse("notifications_page"))
        self.assertContains(response, "Menikida")
        self.assertNotContains(response, "Boshqaniki")

    def test_tabs_filter_by_kind_and_unread(self):
        record(self.emp, "Ariza-xabar", tag="order-new-1")
        record(self.emp, "Hujjat-xabar", tag="deed-sender-1")
        read = record(self.emp, "Oqilgan-xabar", tag="meeting-reminder-1")
        mark_read_by_tag(self.emp, "meeting-reminder-1")
        url = reverse("notifications_page")
        deed = table_html(self.client.get(url, {"tab": "deed"}))
        self.assertIn("Hujjat-xabar", deed)
        self.assertNotIn("Ariza-xabar", deed)
        unread = table_html(self.client.get(url, {"tab": "unread"}))
        self.assertIn("Ariza-xabar", unread)
        self.assertNotIn("Oqilgan-xabar", unread)
        self.assertIsNotNone(read)

    def test_pagination_20_per_page(self):
        for i in range(45):
            record(self.emp, f"Xabar-{i:02d}", tag=f"order-new-{i}")
        url = reverse("notifications_page")
        count = lambda r: sum(1 for i in range(45) if f"Xabar-{i:02d}" in table_html(r))
        self.assertEqual(count(self.client.get(url)), 20)
        self.assertEqual(count(self.client.get(url, {"page": 3})), 5)

    def test_open_marks_read_and_redirects(self):
        item = record(self.emp, "X", url="/order/sender/", tag="order-new-1")
        response = self.client.get(reverse("notification_open", args=[item.id]))
        self.assertRedirects(response, "/order/sender/", fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertTrue(item.is_read)
        self.assertIsNotNone(item.date_read)

    def test_cannot_open_someone_elses(self):
        item = record(self.other, "X", tag="order-new-1")
        self.assertEqual(self.client.get(reverse("notification_open", args=[item.id])).status_code, 404)
        item.refresh_from_db()
        self.assertFalse(item.is_read)

    def test_read_all_only_touches_own(self):
        mine = record(self.emp, "A", tag="order-new-1")
        deed = record(self.emp, "B", tag="deed-sender-1")
        theirs = record(self.other, "C", tag="order-new-2")
        self.client.post(reverse("notifications_read_all"), {"tab": "order"})
        for item, expected in ((mine, True), (deed, False), (theirs, False)):
            item.refresh_from_db()
            self.assertEqual(item.is_read, expected)
        self.client.post(reverse("notifications_read_all"), {})
        deed.refresh_from_db()
        theirs.refresh_from_db()
        self.assertTrue(deed.is_read)
        self.assertFalse(theirs.is_read)

    def test_count_endpoint_and_header_bell(self):
        record(self.emp, "A", tag="order-new-1")
        record(self.emp, "B", tag="order-new-2")
        self.assertEqual(self.client.get(reverse("notifications_count")).json(), {"unread": 2})
        html = self.client.get(reverse("notifications_page")).content.decode()
        self.assertIn('id="notif-badge"', html)
        self.assertIn(">2</span>", html)

    def test_bell_menu_shows_only_unread(self):
        from core.context_processors import notification_center

        unread = record(self.emp, "Yangi-xabar", tag="order-new-1")
        read = record(self.emp, "Eski-xabar", tag="order-new-2")
        mark_read_by_tag(self.emp, "order-new-2")
        request = mock.Mock(user=self.user)
        context = notification_center(request)
        self.assertEqual([n.id for n in context["notif_recent"]], [unread.id])
        self.assertEqual(context["notif_unread"], 1)
        self.assertNotEqual(unread.id, read.id)

    def test_recent_endpoint_returns_only_own_unread_newest_first(self):
        for i in range(8):
            record(self.emp, f"Yangi-{i}", f"matn {i}", "/order/sender/", tag=f"order-new-{i}")
        record(self.emp, "Oqilgan", tag="deed-sender-1")
        mark_read_by_tag(self.emp, "deed-sender-1")
        record(self.other, "Boshqaniki", tag="order-new-99")
        data = self.client.get(reverse("notifications_recent")).json()
        self.assertEqual(data["unread"], 8)                       # o'qilgani va boshqaniki hisobga olinmaydi
        self.assertEqual(len(data["items"]), 6)                   # menyuda 6 tagacha
        self.assertEqual(data["items"][0]["title"], "Yangi-7")    # eng yangisi birinchi
        titles = {item["title"] for item in data["items"]}
        self.assertNotIn("Oqilgan", titles)
        self.assertNotIn("Boshqaniki", titles)
        first = data["items"][0]
        self.assertEqual(first["open_url"], reverse("notification_open", args=[first["id"]]))

    def test_recent_endpoint_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("notifications_recent")).status_code, 302)

    def test_bell_menu_is_marked_for_live_refresh(self):
        record(self.emp, "A", tag="order-new-1")
        html = self.client.get(reverse("notifications_page")).content.decode()
        self.assertIn('id="notif-menu"', html)
        self.assertIn('id="notif-footer"', html)
        self.assertIn(reverse("notifications_recent"), html)

    def test_read_all_ajax_returns_json_and_marks_everything_read(self):
        record(self.emp, "A", tag="order-new-1")
        record(self.emp, "B", tag="deed-sender-1")
        theirs = record(self.other, "C", tag="order-new-2")
        response = self.client.post(reverse("notifications_read_all"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"updated": 2, "unread": 0})
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)
        self.assertEqual(self.client.get(reverse("notifications_recent")).json(), {"unread": 0, "items": []})

    def test_bell_has_read_all_button_only_when_unread_exist(self):
        html = self.client.get(reverse("notifications_page")).content.decode()
        self.assertIn('id="notif-read-all"', html)                      # tugma bor (JS yashirin/ko'rsatadi)
        self.assertIn('id="notif-footer" class="text-center py-2" style="display:none"', html)   # o'qilmagan yo'q: yashirin
        record(self.emp, "A", tag="order-new-1")
        html = self.client.get(reverse("notifications_page")).content.decode()
        self.assertIn('id="notif-footer" class="text-center py-2">', html)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("notifications_page")).status_code, 302)


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
