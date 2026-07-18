import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.alert import BulletinText
from app.schemas.forecast import DailyForecast, ForecastResponse
from app.services import commune_overview
from app.services.geo_data import get_commune


class CommuneOverviewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        commune_overview.clear_cache()
        self.commune = get_commune("muong_pon")
        assert self.commune is not None
        self.forecast = ForecastResponse(
            commune_code=self.commune.code,
            commune_name=self.commune.name,
            lat=self.commune.lat,
            lon=self.commune.lon,
            elevation_m=self.commune.elevation_m,
            source="test-weather",
            updated_at="2026-07-18T08:00:00+07:00",
            days=[
                DailyForecast(
                    date=f"2026-07-{18 + index:02d}",
                    precip_mm=120 if index == 0 else 10,
                    temp_min_c=20,
                    temp_max_c=29,
                    temp_mean_c=24.5,
                    wind_max_kmh=32,
                    humidity_mean=91,
                )
                for index in range(7)
            ],
        )

    async def test_overview_contains_all_requested_sections_and_caches(self):
        weather_mock = AsyncMock(return_value=self.forecast)
        llm_mock = AsyncMock(return_value=[BulletinText(lang="vi", title="Brief AI", body="Nội dung brief")])
        with patch("app.services.commune_overview.weather.get_forecast", weather_mock), \
             patch("app.services.commune_overview.llm.generate_bulletins", llm_mock):
            first, first_hit = await commune_overview.get_overview("muong_pon")
            second, second_hit = await commune_overview.get_overview("muong_pon")

        self.assertFalse(first_hit)
        self.assertTrue(second_hit)
        self.assertEqual(len(first.forecast_7_days.days), 7)
        self.assertEqual(first.forecast_7_days.days[0].humidity_mean, 91)
        self.assertEqual(first.warning_brief.title, "Brief AI")
        self.assertGreater(first.current_warning.risk_level, 0)
        self.assertTrue(first.recommended_tasks)
        self.assertEqual(first.commune.code, second.commune.code)
        weather_mock.assert_awaited_once()
        llm_mock.assert_awaited_once()

    async def test_unknown_commune_raises_domain_error(self):
        with self.assertRaises(commune_overview.CommuneNotFoundError):
            await commune_overview.get_overview("khong_ton_tai")


class CommuneOverviewRouteTests(unittest.TestCase):
    def test_unknown_commune_uses_standard_error_envelope(self):
        response = TestClient(app).get("/api/v1/communes/khong_ton_tai/overview")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertIsNone(body["data"])
        self.assertEqual(body["error"]["code"], "commune_not_found")
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
