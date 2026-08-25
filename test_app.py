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
