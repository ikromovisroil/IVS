import hashlib
import hmac
import json
import time
from datetime import date, timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from main import faceid
from main.models import Deed, FaceIDSession
from main.tasks import process_faceid_result
from main.testing import make_employee, make_org, make_region

SECRET = "whsec-test"
PINFL = "12345678901234"
FACEID = dict(FACEID_HOST="https://faceid.test", FACEID_CLIENT_ID="cid", FACEID_CLIENT_SECRET="sec",
              FACEID_WEBHOOK_SECRET=SECRET, FACEID_ENABLED=True)
SESSION = {"session_id": "sess-1", "sdk_token": "tok", "nonce": "n1", "challenges": [{"id": "ch-1", "type": "head_yaw_left"}],
           "expires_at": (timezone.now() + timedelta(minutes=10)).isoformat()}


def sign(body: bytes, ts=None, secret=SECRET):
    ts = str(ts if ts is not None else int(time.time()))
    sig = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"HTTP_X_FACEID_TIMESTAMP": ts, "HTTP_X_FACEID_SIGNATURE": sig}


class SignatureTests(TestCase):
    def test_valid_and_invalid(self):
        body = b'{"a":1}'
        ts = str(int(time.time()))
        good = "sha256=" + hmac.new(SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        self.assertTrue(faceid.verify_signature(SECRET, ts, body, good))
        self.assertFalse(faceid.verify_signature(SECRET, ts, body + b" ", good))      # tana o'zgargan
        self.assertFalse(faceid.verify_signature("boshqa", ts, body, good))
        self.assertFalse(faceid.verify_signature(SECRET, ts, body, ""))

    def test_timestamp_freshness(self):
        self.assertTrue(faceid.timestamp_is_fresh(str(int(time.time()))))
        self.assertFalse(faceid.timestamp_is_fresh(str(int(time.time()) - 3600)))
        self.assertFalse(faceid.timestamp_is_fresh("abc"))


@override_settings(**FACEID)
class FaceIDFlowTests(TestCase):
    def setUp(self):
        cache.clear()   # throttle va poll kalitlari testlar orasida aralashmasin
        org, region = make_org("worker"), make_region()
        self.user, self.emp = make_employee(org, region, pinfl=PINFL)
        self.emp.birth_date = date(1990, 5, 15)
        self.emp.save()
        _, self.creator = make_employee(org, region)
        _, self.other = make_employee(org, region)
        self.deed = Deed.objects.create(sender=self.emp, user=self.creator, organization=org)
        self.c = APIClient()
        self.c.force_authenticate(self.user)
        self.webhook = APIClient()   # sessiyasiz, imzo bilan

        patcher = mock.patch("main.views.validate_pdf_file", return_value=(True, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def create_session(self, **kw):
        with mock.patch("main.faceid.create_session", return_value=SESSION) as m:
            r = self.c.post("/api/v1/faceid/sessions/", {"deed_id": self.deed.id, "message": " ok ", **kw}, format="json")
        return r, m

    def post_webhook(self, payload, **sign_kw):
        body = json.dumps(payload).encode()
        return self.webhook.post("/api/v1/faceid/webhook/", body, content_type="application/json", **sign(body, **sign_kw))

    def data(self, pinfl=PINFL, status="passed", session_id="sess-1"):
        return {"session_id": session_id, "identity": {"pinfl": pinfl}, "verification": {"status": status, "similarity": 0.8, "liveness_score": 0.9}}

    # ── sessiya yaratish ──
    def test_config_reports_enabled(self):
        self.assertTrue(self.c.get("/api/v1/faceid/config/").json()["enabled"])

    @override_settings(FACEID_ENABLED=False)
    def test_disabled_returns_503(self):
        r, _ = self.create_session()
        self.assertEqual(r.status_code, 503)

    def test_create_session_returns_sdk_data(self):
        r, m = self.create_session()
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual((body["session_id"], body["sdk_token"], body["nonce"]), ("sess-1", "tok", "n1"))
        rec = FaceIDSession.objects.get(session_id="sess-1")
        self.assertEqual((rec.role, rec.status, rec.message, rec.employee_id), ("sender", "pending", "ok", self.emp.id))
        args, kwargs = m.call_args
        self.assertEqual(args[0], PINFL)
        self.assertEqual(args[1], date(1990, 5, 15))

    def test_only_signer_can_start(self):
        stranger = APIClient()
        stranger.force_authenticate(self.other.user)
        with mock.patch("main.faceid.create_session", return_value=SESSION):
            r = stranger.post("/api/v1/faceid/sessions/", {"deed_id": self.deed.id}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_already_approved_is_rejected(self):
        self.deed.status_sender = "approved"
        self.deed.save()
        r, _ = self.create_session()
        self.assertEqual(r.status_code, 400)

    def test_requires_pinfl_and_birth_date(self):
        self.emp.birth_date = None
        self.emp.save()
        r, m = self.create_session()
        self.assertEqual(r.status_code, 400)
        m.assert_not_called()

    def test_faceid_error_is_mapped(self):
        err = faceid.FaceIDError("x", code="IDENTITY_NOT_FOUND", http_status=404)
        with mock.patch("main.faceid.create_session", side_effect=err):
            r = self.c.post("/api/v1/faceid/sessions/", {"deed_id": self.deed.id}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (404, "IDENTITY_NOT_FOUND"))
        down = faceid.FaceIDError("x", code="FACEID_UNREACHABLE", http_status=502)
        with mock.patch("main.faceid.create_session", side_effect=down):
            r = self.c.post("/api/v1/faceid/sessions/", {"deed_id": self.deed.id}, format="json")
        self.assertEqual(r.status_code, 502)

    # ── webhook ──
    def passed_webhook(self, **data_kw):
        self.create_session()
        payload = {"event": "session.passed", "session_id": "sess-1", "callback_code": "cb1", "failure_reason": None}
        with mock.patch("main.faceid.get_data", return_value=self.data(**data_kw)), \
             mock.patch("main.deed_signing.finalize_pdf") as fin, \
             mock.patch.object(process_faceid_result, "delay", side_effect=faceid.finish_session):
            r = self.post_webhook(payload)
        return r, fin

    def test_passed_webhook_approves_deed(self):
        r, fin = self.passed_webhook()
        self.assertEqual(r.status_code, 200)
        self.deed.refresh_from_db()
        rec = FaceIDSession.objects.get(session_id="sess-1")
        self.assertEqual(self.deed.status_sender, "approved")
        self.assertEqual(self.deed.message_sender, "ok")
        self.assertEqual((rec.status, rec.similarity), ("approved", 0.8))
        fin.assert_called_once()                                   # qabul qiluvchi yo'q: imzo to'liq, PDF yig'iladi

    def test_pinfl_mismatch_does_not_approve(self):
        r, fin = self.passed_webhook(pinfl="99999999999999")
        self.deed.refresh_from_db()
        self.assertEqual(self.deed.status_sender, "viewed")
        rec = FaceIDSession.objects.get(session_id="sess-1")
        self.assertEqual((rec.status, rec.failure_reason), ("failed", "PINFL_MISMATCH"))
        fin.assert_not_called()

    def test_verification_not_passed_does_not_approve(self):
        self.passed_webhook(status="failed")
        self.deed.refresh_from_db()
        self.assertEqual(self.deed.status_sender, "viewed")

    def test_transient_faceid_error_keeps_session_pending(self):
        self.create_session()
        payload = {"event": "session.passed", "session_id": "sess-1", "callback_code": "cb1"}
        down = faceid.FaceIDError("x", code="FACEID_UNREACHABLE", http_status=502)
        with mock.patch("main.faceid.get_data", side_effect=down),              mock.patch.object(process_faceid_result, "delay", side_effect=faceid.finish_session):
            self.post_webhook(payload)
        rec = FaceIDSession.objects.get(session_id="sess-1")
        self.assertEqual((rec.status, rec.failure_reason), ("pending", ""))        # holat so'rovi qayta urinadi
        with mock.patch("main.faceid.get_session", return_value={"status": "passed", "callback_code": "cb1"}),              mock.patch("main.faceid.get_data", return_value=self.data()),              mock.patch("main.deed_signing.finalize_pdf"):
            body = self.c.get(f"/api/v1/faceid/sessions/{rec.id}/").json()
        self.assertEqual(body["status"], "approved")

    def test_permanent_faceid_error_fails_session(self):
        self.create_session()
        payload = {"event": "session.passed", "session_id": "sess-1", "callback_code": "cb1"}
        gone = faceid.FaceIDError("x", code="CODE_EXPIRED", http_status=410)
        with mock.patch("main.faceid.get_data", side_effect=gone),              mock.patch.object(process_faceid_result, "delay", side_effect=faceid.finish_session):
            self.post_webhook(payload)
        rec = FaceIDSession.objects.get(session_id="sess-1")
        self.assertEqual((rec.status, rec.failure_reason), ("failed", "CODE_EXPIRED"))

    def test_poll_failed_state_has_generic_reason(self):
        self.create_session()
        rec = FaceIDSession.objects.get(session_id="sess-1")
        with mock.patch("main.faceid.get_session", return_value={"status": "failed"}):
            body = self.c.get(f"/api/v1/faceid/sessions/{rec.id}/").json()
        self.assertEqual((body["status"], body["failure_reason"]), ("failed", "FAILED"))

    def test_other_sessions_result_is_rejected(self):
        self.passed_webhook(session_id="boshqa")
        self.deed.refresh_from_db()
        self.assertEqual(self.deed.status_sender, "viewed")

    def test_duplicate_delivery_is_harmless(self):
        self.passed_webhook()
        body = json.dumps({"event": "session.passed", "session_id": "sess-1", "callback_code": "cb1"}).encode()
        with mock.patch("main.faceid.get_data") as get_data:
            r = self.webhook.post("/api/v1/faceid/webhook/", body, content_type="application/json", **sign(body))
        self.assertEqual(r.status_code, 200)
        get_data.assert_not_called()

    def test_failed_webhook_records_reason(self):
        self.create_session()
        r = self.post_webhook({"event": "session.failed", "session_id": "sess-1", "failure_reason": "FACE_MISMATCH"})
        self.assertEqual(r.status_code, 200)
        rec = FaceIDSession.objects.get(session_id="sess-1")
        self.assertEqual((rec.status, rec.failure_reason), ("failed", "FACE_MISMATCH"))

    def test_bad_signature_and_stale_timestamp_rejected(self):
        self.create_session()
        body = json.dumps({"event": "session.passed", "session_id": "sess-1", "callback_code": "x"}).encode()
        bad = self.webhook.post("/api/v1/faceid/webhook/", body, content_type="application/json", **sign(body, secret="xato"))
        stale = self.webhook.post("/api/v1/faceid/webhook/", body, content_type="application/json",
                                  **sign(body, ts=int(time.time()) - 3600))
        self.assertEqual((bad.status_code, stale.status_code), (401, 401))
        self.assertEqual(FaceIDSession.objects.get(session_id="sess-1").status, "pending")

    def test_unknown_session_is_acknowledged(self):
        r = self.post_webhook({"event": "session.failed", "session_id": "yo'q"})
        self.assertEqual(r.status_code, 200)

    def test_receiver_must_also_sign_before_pdf_is_built(self):
        _, receiver = make_employee(self.emp.organization, self.emp.region)
        self.deed.receiver = receiver
        self.deed.save()
        r, fin = self.passed_webhook()
        self.deed.refresh_from_db()
        self.assertEqual((self.deed.status_sender, self.deed.status_receiver), ("approved", "viewed"))
        fin.assert_not_called()

    # ── holat ──
    def test_status_endpoint_shows_result_and_is_private(self):
        self.passed_webhook()
        rec = FaceIDSession.objects.get(session_id="sess-1")
        with mock.patch("main.faceid.get_session"):
            body = self.c.get(f"/api/v1/faceid/sessions/{rec.id}/").json()
        self.assertEqual((body["status"], body["deed"]["status_sender"], body["retry"]), ("approved", "approved", False))
        other = APIClient()
        other.force_authenticate(self.other.user)
        self.assertEqual(other.get(f"/api/v1/faceid/sessions/{rec.id}/").status_code, 404)

    def test_failed_status_has_message_and_retry_flag(self):
        self.create_session()
        self.post_webhook({"event": "session.failed", "session_id": "sess-1", "failure_reason": "QUALITY_LOW"})
        rec = FaceIDSession.objects.get(session_id="sess-1")
        with mock.patch("main.faceid.get_session"):
            body = self.c.get(f"/api/v1/faceid/sessions/{rec.id}/").json()
        self.assertEqual((body["status"], body["failure_reason"], body["retry"]), ("failed", "QUALITY_LOW", True))
        self.assertIn("yorug", body["message"].lower())

    def test_overdue_pending_session_expires(self):
        self.create_session()
        FaceIDSession.objects.filter(session_id="sess-1").update(expires_at=timezone.now() - timedelta(minutes=1))
        rec = FaceIDSession.objects.get(session_id="sess-1")
        with mock.patch("main.faceid.get_session"):
            self.assertEqual(self.c.get(f"/api/v1/faceid/sessions/{rec.id}/").json()["status"], "expired")

    def test_status_poll_is_fallback_when_webhook_missing(self):
        self.create_session()
        rec = FaceIDSession.objects.get(session_id="sess-1")
        with mock.patch("main.faceid.get_session", return_value={"status": "passed", "callback_code": "cb1"}), \
             mock.patch("main.faceid.get_data", return_value=self.data()), \
             mock.patch("main.deed_signing.finalize_pdf"):
            body = self.c.get(f"/api/v1/faceid/sessions/{rec.id}/").json()
        self.assertEqual(body["status"], "approved")
