"""Minimal API contract checks for a seeded local demo database."""

import unittest

from app import app


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_dashboard_summary_contract(self):
        response = self.client.get("/api/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("totals", payload)
        self.assertIn("risk_breakdown", payload)

    def test_decision_intelligence_endpoints(self):
        for path in ("/api/insights/early-warning", "/api/insights/compliance", "/api/map/works"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
