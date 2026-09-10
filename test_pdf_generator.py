import unittest
from pathlib import Path

from config import Config
from pdf_generator import generate_pdf


class PdfGeneratorTest(unittest.TestCase):
    def test_generate_pdf_with_null_sensor_fields(self):
        sensor_data = {
            "soil_moisture": 18.0,
            "soil_temperature": 30.5,
            "humidity": None,
            "rainfall": None,
            "air_temperature": None,
            "ph": None,
        }
        prediction = {
            "recommended_crop": "Rice",
            "growth_months": 4,
            "confidence_pct": 62,
            "prediction_text": "Heat wave",
            "user_crop": "soybean",
            "explanation": "Soybean is acceptable, yet Rice is the stronger match today.",
            "explanation_detailed": ["Soybean is acceptable, yet Rice is the stronger match today."],
            "explanation_sections": {
                "preferred_crop_reasons": ["Soybean needs more moisture."],
                "recommended_crop_reasons": ["Rice suits warm wet conditions."],
            },
            "preferred_crop_score": 69,
        }

        Config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path, crop, months = generate_pdf(sensor_data, prediction=prediction)
        self.assertTrue(Path(pdf_path).is_file())
        self.assertEqual(crop, "Rice")
        self.assertEqual(months, 4)
        Path(pdf_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
