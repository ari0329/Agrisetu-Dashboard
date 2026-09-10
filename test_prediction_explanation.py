import unittest

from prediction_explanation import build_prediction_explanation


SENSOR_DRY = {
    "soil_moisture": 15,
    "soil_temperature": 31,
    "rainfall": 0,
    "air_temperature": 34,
    "humidity": 40,
}


class PredictionExplanationTest(unittest.TestCase):
    def test_note_and_preferred_crop_mentioned_in_explanation(self):
        result = build_prediction_explanation(
            SENSOR_DRY,
            recommended_crop="Rice",
            user_crop="potato",
            prediction_text="high rain",
        )
        self.assertIn("high rain", result["explanation"].lower())
        self.assertIn("potato", result["explanation"].lower())
        self.assertIn("rice", result["explanation"].lower())
        self.assertFalse(result["preferred_crop_suitable"])

    def test_rain_note_contradicts_dry_sensors(self):
        result = build_prediction_explanation(
            SENSOR_DRY,
            recommended_crop="Rice",
            user_crop="tomato",
            prediction_text="expecting heavy rainfall",
        )
        alignment = result["explanation_sections"]["note_sensor_alignment"]
        self.assertTrue(any("rain" in line.lower() for line in alignment))

    def test_matching_preferred_crop_is_positive(self):
        result = build_prediction_explanation(
            SENSOR_DRY,
            recommended_crop="Rice",
            user_crop="rice",
            prediction_text="",
        )
        self.assertIn("aligns", result["explanation"].lower())


if __name__ == "__main__":
    unittest.main()
