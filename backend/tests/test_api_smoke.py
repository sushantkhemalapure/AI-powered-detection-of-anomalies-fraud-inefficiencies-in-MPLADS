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

    def test_allocation_review_endpoints(self):
        for path in ("/api/anomalies", "/api/alerts", "/api/dashboard/state-ranking"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_allocation_analysis_endpoints(self):
        analytics = self.client.get("/api/allocation/analytics")
        self.assertEqual(analytics.status_code, 200)
        self.assertIn("distribution", analytics.get_json())
        self.assertIn("coverage", analytics.get_json())

        members = self.client.get("/api/allocation/members?page_size=5")
        self.assertEqual(members.status_code, 200)
        self.assertIn("items", members.get_json())

        export = self.client.get("/api/export/allocations.csv")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.mimetype, "text/csv")


if __name__ == "__main__":
    unittest.main()
