import unittest
from unittest.mock import patch

import app as app_module


class AgriSetuAppTest(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = app_module.app.test_client()

    def login_session(self):
        with self.client.session_transaction() as session:
            session["user"] = {
                "id": "user-1",
                "name": "Farmer",
                "email": "farmer@example.com",
            }

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    @patch("app.user_exists", return_value=False)
    def test_unknown_user_is_sent_to_shared_signup(self, _user_exists):
        response = self.client.post(
            "/login",
            data={"email": "new@example.com", "password": "not-used"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, app_module.Config.SIGNUP_URL)

    @patch("app.authenticate_user")
    @patch("app.user_exists", return_value=True)
    def test_shared_user_can_login(self, _user_exists, authenticate_user):
        authenticate_user.return_value = {
            "id": "user-1",
            "name": "Farmer",
            "email": "farmer@example.com",
        }
        response = self.client.post(
            "/login",
            data={"email": "farmer@example.com", "password": "correct"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")

    @patch("app.create_field")
    def test_field_pairing_is_owned_by_logged_in_user(self, create_field):
        self.login_session()
        create_field.return_value = {
            "id": "field-1",
            "name": "North Field",
            "paired": True,
        }
        response = self.client.post(
            "/api/fields",
            json={"name": "North Field", "device_id": "DEVICE-001"},
        )
        self.assertEqual(response.status_code, 201)
        create_field.assert_called_once_with("user-1", "North Field", "DEVICE-001")

    @patch("app.create_field", side_effect=app_module.DuplicateDevice("This Device ID is already paired"))
    def test_duplicate_device_id_returns_conflict(self, _create_field):
        self.login_session()
        response = self.client.post(
            "/api/fields",
            json={"name": "South Field", "device_id": "DEVICE-001"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "This Device ID is already paired")

    @patch("app.update_field")
    def test_field_update_is_owned_by_logged_in_user(self, update_field):
        self.login_session()
        update_field.return_value = {
            "id": "field-1",
            "name": "North Plot",
            "paired": True,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        response = self.client.patch(
            "/api/fields/field-1",
            json={"name": "North Plot", "device_id": "DEVICE-002"},
        )
        self.assertEqual(response.status_code, 200)
        update_field.assert_called_once_with("user-1", "field-1", "North Plot", "DEVICE-002")

    @patch("app.delete_field", return_value=True)
    def test_field_delete_removes_owned_field(self, delete_field):
        self.login_session()
        response = self.client.delete("/api/fields/field-1")
        self.assertEqual(response.status_code, 200)
        delete_field.assert_called_once_with("user-1", "field-1")

    def test_tts_requires_login(self):
        response = self.client.post("/api/tts", json={"text": "Hello"})
        self.assertEqual(response.status_code, 401)

    @patch("app.synthesize_speech", return_value=b"fake-mp3-bytes")
    def test_tts_returns_audio_for_authenticated_user(self, synthesize_speech):
        self.login_session()
        response = self.client.post("/api/tts", json={"text": "Irrigate now"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")
        self.assertEqual(response.data, b"fake-mp3-bytes")
        synthesize_speech.assert_called_once_with("Irrigate now", lang="en")

    @patch("app.synthesize_speech")
    def test_tts_rejects_empty_text(self, synthesize_speech):
        self.login_session()
        response = self.client.post("/api/tts", json={"text": "   "})
        self.assertEqual(response.status_code, 400)
        synthesize_speech.assert_not_called()

    @patch("app.save_device_telemetry")
    def test_arduino_device_id_routes_telemetry(self, save_device_telemetry):
        app_module.ARDUINO_SECRET = "test-ingest-secret"
        save_device_telemetry.return_value = {
            "field_id": "field-1",
            "received_at": app_module.datetime.now(),
        }
        response = self.client.post(
            "/api/arduino-data",
            headers={"X-Arduino-Secret": "test-ingest-secret"},
            json={
                "device_id": "DEVICE-001",
                "soil_moisture": 51.2,
                "soil_temperature": 24.3,
                "L1": 1,
                "L2": 0,
                "L3": 0,
                "L4": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
