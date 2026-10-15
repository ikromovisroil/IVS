"""Chat: istalgan faol xodim istalgan faol xodimga yoza oladi (tashkilot cheklovi yo'q), nofaol xodim - yo'q."""
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from chat.models import Conversation
from chat.services import add_group_members, create_group_conversation
from main.testing import make_employee, make_org


class ChatAccessTests(TestCase):
    def setUp(self):
        self.org_a = make_org("client")
        self.org_b = make_org("worker")
        self.user_a, self.a = make_employee(self.org_a, first="Alisher", last="Aliyev")
        self.user_a2, self.a2 = make_employee(self.org_a, first="Anvar", last="Aliyev")
        self.user_b, self.b = make_employee(self.org_b, first="Bobur", last="Boboyev")
        self.user_off, self.off = make_employee(self.org_b, first="Nofaol", last="Boboyev", active=False)
        self.client.force_login(self.user_a)

    def _names(self, response):
        return {item["name"] for item in response.json()["results"]}

    def test_contacts_include_other_organizations(self):
        names = self._names(self.client.get(reverse("chat_contacts"), {"q": "Boboyev"}))
        self.assertTrue(any("Bobur" in n for n in names))

    def test_contacts_exclude_inactive_and_self(self):
        names = self._names(self.client.get(reverse("chat_contacts")))
        self.assertFalse(any("Nofaol" in n for n in names))
        self.assertFalse(any("Alisher" in n for n in names))
        self.assertTrue(any("Anvar" in n for n in names))

    def test_open_direct_chat_with_other_organization(self):
        response = self.client.post(reverse("chat_open"), {"target": self.b.id})
        self.assertEqual(response.status_code, 200)
        conversation = Conversation.objects.get(pk=response.json()["conversation_id"])
        self.assertTrue(conversation.has_participant(self.a))
        self.assertTrue(conversation.has_participant(self.b))

    def test_cannot_open_chat_with_inactive_employee(self):
        response = self.client.post(reverse("chat_open"), {"target": self.off.id})
        self.assertEqual(response.status_code, 404)

    def test_group_mixes_organizations_but_skips_inactive(self):
        group = create_group_conversation(self.a, "Aralash", [self.a2.id, self.b.id, self.off.id])
        ids = set(group.participants.values_list("id", flat=True))
        self.assertEqual(ids, {self.a.id, self.a2.id, self.b.id})

    def test_add_members_skips_inactive(self):
        _, extra = make_employee(self.org_a, first="Qo'shimcha", last="Xodim")
        group = create_group_conversation(self.a, "Guruh", [self.a2.id, self.b.id])
        added = add_group_members(group, [extra.id, self.off.id])
        self.assertEqual(set(added), {extra.id})

    def test_api_contacts_and_open(self):
        api = APIClient()
        api.force_authenticate(self.user_a)
        names = {x["name"] for x in api.get("/api/v1/chat/contacts/", {"q": "Boboyev"}).json()["results"]}
        self.assertTrue(any("Bobur" in n for n in names))
        self.assertFalse(any("Nofaol" in n for n in names))
        self.assertEqual(api.post("/api/v1/chat/open/", {"target": self.b.id}, format="json").status_code, 200)
        self.assertEqual(api.post("/api/v1/chat/open/", {"target": self.off.id}, format="json").status_code, 404)

    def test_ai_and_saved_conversations_still_open(self):
        for target in ("ai", "saved"):
            with mock.patch("chat.realtime._send"):
                response = self.client.post(reverse("chat_open"), {"target": target})
            self.assertEqual(response.status_code, 200, target)
