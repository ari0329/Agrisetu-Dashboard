import unittest

from advisory import assess_environmental_risks
from farm_risk import is_model_available, predict_farm_risk


SAMPLE_SENSOR = {
    "soil_moisture": 50,
    "soil_temperature": 25,
    "rainfall": 10,
    "air_temperature": 28,
    "humidity": 60,
    "water_level": 55,
}


@unittest.skipUnless(is_model_available(), "farm_risk_model.pkl not available")
class FarmRiskModelTest(unittest.TestCase):
    def test_predict_returns_ml_fields(self):
        result = predict_farm_risk(SAMPLE_SENSOR)
        self.assertEqual(result["prediction_source"], "ml")
        self.assertEqual(result["model_used"], "farm_risk_model")
        self.assertIn("yield_risk_pct", result)
        self.assertIn("predicted_regime", result)
        self.assertIn("anomaly_decision", result)
        self.assertGreaterEqual(result["yield_risk_pct"], 0)
        self.assertLessEqual(result["yield_risk_pct"], 100)
        self.assertEqual(len(result["risks"]), 4)

    def test_extreme_drought_scores_high_risk(self):
        drought = {
            "soil_moisture": 12,
            "soil_temperature": 32,
            "rainfall": 0,
            "air_temperature": 40,
            "humidity": 25,
            "water_level": 10,
        }
        result = predict_farm_risk(drought)
        self.assertGreaterEqual(result["yield_risk_pct"], 80)
        drought_risk = next(r for r in result["risks"] if r["id"] == "drought")
        self.assertGreaterEqual(drought_risk["score"], 70)

    def test_advisory_uses_ml_when_model_loaded(self):
        result = assess_environmental_risks(SAMPLE_SENSOR)
        self.assertEqual(result["prediction_source"], "ml")
        self.assertIsNotNone(result.get("predicted_regime"))


if __name__ == "__main__":
    unittest.main()
