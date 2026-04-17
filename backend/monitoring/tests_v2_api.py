from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from .models import DrivingEvent, UserProfile


class ApiV2BaseTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin01", password="pass1234", is_staff=True)
        UserProfile.objects.create(
            user=self.admin,
            full_name="管理员A",
            role=UserProfile.Role.ADMIN,
            phone="13800138001",
            id_card="IDADMIN0001",
        )

        self.driver = User.objects.create_user(username="driver01", password="pass1234", is_staff=False)
        UserProfile.objects.create(
            user=self.driver,
            full_name="驾驶员A",
            role=UserProfile.Role.DRIVER,
            phone="13800138002",
            id_card="IDDRIVER0001",
        )

        now = timezone.now()
        self.auto_event = DrivingEvent.objects.create(
            owner=self.driver,
            event_type=DrivingEvent.EventType.FATIGUE,
            source_event_id="evt-auto-1",
            source_session_id="sess-1",
            source_label="fatigue",
            start_time=now - timedelta(minutes=4),
            end_time=now - timedelta(minutes=3),
            duration_sec=60.0,
            peak_risk_conf=0.83,
            review_status=DrivingEvent.ReviewStatus.AUTO,
            snapshot_path="/media/evidence/a.jpg",
        )

        self.pending_event = DrivingEvent.objects.create(
            owner=self.driver,
            event_type=DrivingEvent.EventType.FATIGUE,
            source_event_id="evt-pending-1",
            source_session_id="sess-2",
            source_label="fatigue",
            start_time=now - timedelta(minutes=2),
            end_time=now - timedelta(minutes=1),
            duration_sec=60.0,
            peak_risk_conf=0.91,
            review_status=DrivingEvent.ReviewStatus.PENDING,
            snapshot_path="/media/evidence/b.jpg",
        )


class ApiV2AuthTests(ApiV2BaseTestCase):
    def test_auth_login_returns_envelope(self):
        client = Client()
        resp = client.post(
            "/api/v2/auth/login",
            data='{"login_id":"admin01","password":"pass1234"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 0)
        self.assertIn("request_id", body)
        self.assertEqual(body["data"]["session"]["user"]["role"], "admin")

    def test_auth_me_requires_login(self):
        client = Client()
        resp = client.get("/api/v2/auth/me")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], 1001)


class ApiV2EventWorkflowTests(ApiV2BaseTestCase):
    def test_driver_can_appeal_auto_event(self):
        client = Client()
        self.assertTrue(client.login(username="driver01", password="pass1234"))

        resp = client.patch(
            f"/api/v2/events/{self.auto_event.id}/appeal",
            data='{"note":"模型误判，申请复核"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.auto_event.refresh_from_db()
        self.assertEqual(self.auto_event.review_status, DrivingEvent.ReviewStatus.PENDING)

    def test_admin_can_review_pending_event(self):
        client = Client()
        self.assertTrue(client.login(username="admin01", password="pass1234"))

        resp = client.patch(
            f"/api/v2/events/{self.pending_event.id}/review",
            data='{"review_status":"confirmed","note":"人工确认疲劳"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.pending_event.refresh_from_db()
        self.assertEqual(self.pending_event.review_status, DrivingEvent.ReviewStatus.CONFIRMED)
        self.assertEqual(self.pending_event.reviewed_by_id, self.admin.id)

    def test_invalid_state_transition_returns_conflict(self):
        client = Client()
        self.assertTrue(client.login(username="admin01", password="pass1234"))

        resp = client.patch(
            f"/api/v2/events/{self.auto_event.id}/review",
            data='{"review_status":"confirmed"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], 1409)


class ApiV2AdminUsersTests(ApiV2BaseTestCase):
    def test_admin_users_crud_basics(self):
        client = Client()
        self.assertTrue(client.login(username="admin01", password="pass1234"))

        create_resp = client.post(
            "/api/v2/admin/users",
            data='{"username":"driver02","password":"pass1234","full_name":"驾驶员B","role":"driver"}',
            content_type="application/json",
        )
        self.assertEqual(create_resp.status_code, 200)
        new_user_id = create_resp.json()["data"]["item"]["id"]

        list_resp = client.get("/api/v2/admin/users?page=1&page_size=10")
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(len(list_resp.json()["data"]["items"]), 1)

        update_resp = client.patch(
            f"/api/v2/admin/users/{new_user_id}",
            data='{"role":"admin","is_active":true,"full_name":"新管理员"}',
            content_type="application/json",
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["data"]["item"]["role"], "admin")

    def test_driver_cannot_access_admin_users_api(self):
        client = Client()
        self.assertTrue(client.login(username="driver01", password="pass1234"))
        resp = client.get("/api/v2/admin/users")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 1003)
