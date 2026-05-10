import unittest
from unittest.mock import patch

from ticktick.ticktick_mcp_server import TickTickAPI


class DryTickTickAPI(TickTickAPI):
    def __init__(self):
        self.access_token = "dry"
        self.base_url = "dry"
        self.requests = []

    def _make_request(self, method, endpoint, data=None, params=None):
        self.requests.append({
            "method": method,
            "endpoint": endpoint,
            "data": data,
            "params": params,
        })
        return data or {}


class TickTickDatePayloadTests(unittest.TestCase):
    def setUp(self):
        self.timezone_patch = patch.dict(
            "os.environ",
            {"TICKTICK_TIMEZONE": "America/Indiana/Indianapolis"},
        )
        self.timezone_patch.start()
        self.api = DryTickTickAPI()

    def tearDown(self):
        self.timezone_patch.stop()

    def test_create_date_only_uses_ticktick_all_day_field(self):
        payload = self.api.create_task(
            title="date only",
            project_id="project",
            due_date="2026-05-11",
        )

        self.assertEqual(payload["dueDate"], "2026-05-11T00:00:00-0400")
        self.assertIs(payload["isAllDay"], True)
        self.assertEqual(payload["timeZone"], "America/Indiana/Indianapolis")
        self.assertNotIn("allDay", payload)

    def test_update_date_only_uses_ticktick_all_day_field(self):
        payload = self.api.update_task(
            task_id="task",
            project_id="project",
            due_date="2026-05-11",
        )

        self.assertEqual(payload["dueDate"], "2026-05-11T00:00:00-0400")
        self.assertIs(payload["isAllDay"], True)
        self.assertEqual(payload["timeZone"], "America/Indiana/Indianapolis")
        self.assertNotIn("allDay", payload)

    def test_timed_due_date_is_not_all_day(self):
        payload = self.api.create_task(
            title="timed",
            project_id="project",
            due_date="2026-05-11T09:30:00+0000",
            all_day=True,
        )

        self.assertEqual(payload["dueDate"], "2026-05-11T09:30:00+0000")
        self.assertIs(payload["isAllDay"], False)
        self.assertNotIn("allDay", payload)

    def test_local_timed_due_date_gets_local_offset(self):
        payload = self.api.update_task(
            task_id="task",
            project_id="project",
            due_date="2026-05-11 09:30:00",
        )

        self.assertEqual(payload["dueDate"], "2026-05-11T09:30:00-0400")
        self.assertIs(payload["isAllDay"], False)

    def test_natural_language_due_date_fails_before_api_request(self):
        with self.assertRaises(ValueError):
            self.api.create_task(
                title="bad date",
                project_id="project",
                due_date="next Monday",
            )

        self.assertEqual(self.api.requests, [])


if __name__ == "__main__":
    unittest.main()
