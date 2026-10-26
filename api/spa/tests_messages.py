"""api/spa/messages.py — "Xabarlar": ro'yxatlar, hujjat, E-IMZO bilan tasdiqlashni boshlash, flash, sonlar, holat."""
import shutil
import tempfile

import pymupdf
from django.contrib import messages as dj_messages
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import Deed, DeedConsent
from main.testing import make_employee, make_org, make_region

BASE = "/api/v1/spa/messages"
MEDIA = tempfile.mkdtemp(prefix="msg-tests-")


def pdf_bytes():
    doc = pymupdf.open()
    page = doc.new_page()
    for i in range(40):
        page.insert_text((72, 72 + i * 16), f"Test qatori {i} — dalolatnoma matni")
    data = doc.tobytes()
    doc.close()
    return data


@override_settings(MEDIA_ROOT=MEDIA, CONTEXT_CACHE_SECONDS=0)
class MessagesSpaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        region = make_region()
        self.creator_user, self.creator = make_employee(self.client_org, region, perms=["main.add_deed"], last="Yaratuvchi")
        self.signer_user, self.signer = make_employee(self.client_org, region, last="Imzolovchi")
        self.agree_user, self.agreer = make_employee(self.worker_org, region, last="Kelishuvchi")
        self.other_user, self.other = make_employee(self.client_org, region, last="Begona")

        self.deed = Deed(user=self.creator, sender=self.signer, organization=self.client_org, status="act")
        self.deed.file.save("t.pdf", ContentFile(pdf_bytes()), save=False)
        self.deed.save()
        self.consent = DeedConsent.objects.create(deed=self.deed, employee=self.agreer)

        self.done = Deed(user=self.creator, sender=self.signer, organization=self.client_org, status="svod",
                         status_sender="approved")
        self.done.file.save("d.pdf", ContentFile(pdf_bytes()), save=False)
        self.done.save()

    def api(self, user):
        c = APIClient()
        c.force_login(user)
        return c

    def codes(self, user, box):
        r = self.api(user).get(f"{BASE}/deeds/", {"box": box})
        self.assertEqual(r.status_code, 200, r.data)
        return [d["id"] for d in r.data["results"]]

    # ---------- ro'yxatlar (contact_user / contact / contact_agrement va arxivlar) ----------

    def test_boxes_match_legacy_querysets(self):
        self.assertEqual(self.codes(self.creator_user, "send"), [self.deed.id])
        self.assertEqual(self.codes(self.creator_user, "send_archive"), [self.done.id])
        self.assertEqual(self.codes(self.signer_user, "sign"), [self.deed.id])
        self.assertEqual(self.codes(self.signer_user, "sign_archive"), [self.done.id])
        self.assertEqual(self.codes(self.agree_user, "agree"), [self.deed.id])
        self.assertEqual(self.codes(self.agree_user, "agree_archive"), [])
        self.assertEqual(self.codes(self.other_user, "sign"), [])

    def test_rejected_boxes_split_from_signed_and_open(self):
        rej = Deed(user=self.creator, sender=self.signer, organization=self.client_org, status="svod",
                   status_sender="rejected")
        rej.file.save("r.pdf", ContentFile(pdf_bytes()), save=False)
        rej.save()
        DeedConsent.objects.create(deed=rej, employee=self.agreer, status="rejected")
        self.assertEqual(self.codes(self.creator_user, "send_rejected"), [rej.id])
        self.assertEqual(self.codes(self.creator_user, "send_archive"), [self.done.id])
        self.assertEqual(self.codes(self.creator_user, "send"), [self.deed.id])
        self.assertEqual(self.codes(self.signer_user, "sign_rejected"), [rej.id])
        self.assertEqual(self.codes(self.signer_user, "sign_archive"), [self.done.id])
        self.assertEqual(self.codes(self.signer_user, "sign"), [self.deed.id])
        self.assertEqual(self.codes(self.agree_user, "agree_rejected"), [rej.id])
        self.assertEqual(self.codes(self.agree_user, "agree_archive"), [])
        self.assertEqual(self.codes(self.agree_user, "agree"), [self.deed.id])
        self.assertEqual(self.codes(self.other_user, "sign_rejected"), [])

    def test_unknown_box_is_400(self):
        self.assertEqual(self.api(self.creator_user).get(f"{BASE}/deeds/", {"box": "x"}).status_code, 400)

    def test_list_has_status_modal_details(self):
        row = self.api(self.creator_user).get(f"{BASE}/deeds/", {"box": "send"}).data["results"][0]
        self.assertEqual(row["sender_info"]["full_name"], self.signer.full_name)
        self.assertEqual(row["user_info"]["organization_name"], self.client_org.name)
        self.assertEqual([c["employee"] for c in row["consents"]], [self.agreer.id])
        self.assertTrue(row["can_manage_consents"])

    def test_detail_only_for_participants(self):
        self.assertEqual(self.api(self.agree_user).get(f"{BASE}/deeds/{self.deed.id}/").status_code, 200)
        self.assertEqual(self.api(self.other_user).get(f"{BASE}/deeds/{self.deed.id}/").status_code, 404)

    def test_counts(self):
        r = self.api(self.signer_user).get(f"{BASE}/counts/")
        self.assertEqual(r.data, {"sign": 1, "agree": 0})
        r = self.api(self.agree_user).get(f"{BASE}/counts/")
        self.assertEqual(r.data, {"sign": 0, "agree": 1})

    # ---------- E-IMZO bilan tasdiqlash ----------

    def test_approve_start_sets_pending_session(self):
        c = self.api(self.signer_user)
        r = c.post(f"{BASE}/deeds/{self.deed.id}/approve/", {"message": "ok", "return_to": "/messages/sign?eimzo=1"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["redirect"], "/sso/start/approve/")
        pending = c.session["PENDING_APPROVE"]
        self.assertEqual(pending["deed_id"], self.deed.id)
        self.assertEqual(pending["role"], "sender")
        self.assertEqual(pending["message"], "ok")
        self.assertTrue(pending["redirect_url"].endswith("/app/messages/sign?eimzo=1"))

    def test_eimzo_return_brings_user_back_to_spa_and_approves(self):
        c = self.api(self.signer_user)
        c.post(f"{BASE}/deeds/{self.deed.id}/approve/", {"return_to": "/messages/sign?eimzo=1"}, format="json")
        # sso_start_approve E-IMZO ga yo'naltiradi; bu yerda uning sessiyaga yozadiganini takrorlaymiz
        import time
        s = c.session
        s["PENDING_EIMZO"] = {"doc": f"deed-{self.deed.id}-sender-{self.signer.id}", "redirect_url": "/", "ts": int(time.time())}
        s.save()
        from unittest import mock
        with mock.patch("main.sso_views.sign_pdf_inplace"), mock.patch("main.sso_views.deed_to_pdf_bytes", return_value=pdf_bytes()):
            r = c.get("/sso/eimzo-return/", {"doc": f"deed-{self.deed.id}-sender-{self.signer.id}"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith("/messages/sign?eimzo=1"))
        self.deed.refresh_from_db()
        self.assertEqual(self.deed.status_sender, "approved")
        flash = c.get(f"{BASE}/flash/").data
        self.assertIn({"text": "Hujjat muvaffaqiyatli imzolandi", "tone": "success"}, flash)
        self.assertEqual(c.get(f"{BASE}/flash/").data, [])

    def test_approve_start_rules(self):
        url = f"{BASE}/deeds/{self.deed.id}/approve/"
        self.assertEqual(self.api(self.other_user).post(url, {}, format="json").status_code, 403)
        self.assertEqual(self.api(self.signer_user).post(url, {"return_to": "https://evil.example/"}, format="json").status_code, 400)
        self.assertEqual(self.api(self.signer_user).post(f"{BASE}/deeds/{self.done.id}/approve/", {}, format="json").status_code, 400)

    def test_flash_reads_django_messages(self):
        # SSO oqimi (sso_start_approve) xabar qoldiradi → SPA o'qiydi (sessiya orqali)
        self.client.force_login(self.signer_user)
        self.client.get("/sso/start/approve/")                          # kutilayotgan tasdiqlash yo'q: xabar qoldiradi
        flash = self.client.get(f"{BASE}/flash/").json()
        self.assertEqual([m["text"] for m in flash], ["Tasdiqlash topilmadi"])
        self.assertEqual(self.client.get(f"{BASE}/flash/").json(), [])  # bir marta o'qiladi
        self.assertEqual(dj_messages.SUCCESS, 25)

    # ---------- yaratish oynasi va tahrirlash ro'yxatlari ----------

    def test_create_form_lists(self):
        c = self.api(self.creator_user)
        orgs = {o["id"] for o in c.get(f"{BASE}/organizations/").data}
        self.assertTrue({self.client_org.id, self.worker_org.id} <= orgs)
        ids = [e["id"] for e in c.get(f"{BASE}/employees/", {"organization": self.client_org.id}).json()["results"]]
        self.assertIn(self.signer.id, ids)
        workers = [e["id"] for e in c.get(f"{BASE}/workers/").json()["results"]]
        self.assertEqual(workers, [self.agreer.id])
        agreements = [e["id"] for e in c.get(f"{BASE}/agreements/", {"org_id": self.worker_org.id}).json()]
        self.assertIn(self.agreer.id, agreements)

    def test_edit_options_only_for_creator(self):
        r = self.api(self.creator_user).get(f"{BASE}/deeds/{self.deed.id}/edit-options/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.signer.id, [e["id"] for e in r.data["sender"]])
        self.assertEqual(r.data["selected_agreements"], [self.agreer.id])
        self.assertEqual(self.api(self.signer_user).get(f"{BASE}/deeds/{self.deed.id}/edit-options/").status_code, 403)

    # ---------- deed_status ----------

    def test_public_status_by_code(self):
        r = APIClient().get(f"{BASE}/status/{self.deed.code}/{self.deed.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("body", r.data)
        self.assertEqual(r.data["sender_info"]["full_name"], self.signer.full_name)
        self.assertEqual(APIClient().get(f"{BASE}/status/WRONG/{self.deed.id}/").status_code, 404)
