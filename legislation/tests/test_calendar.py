from django.test import SimpleTestCase

from legislation import calendar
from legislation.tests.base import at


class CalendarTests(SimpleTestCase):
    def test_friday_proposal_is_ready_for_the_next_monday(self):
        # 07 §07.6: enviada na sexta, entra na votação da segunda seguinte
        for hour in (0, 12, 23):
            self.assertEqual(calendar.discussion_ends_at(at(10, 9, hour)), at(10, 12))
        self.assertEqual(calendar.monday_at_or_after(at(10, 12)), at(10, 12))

    def test_saturday_proposal_waits_for_the_following_window(self):
        ends = calendar.discussion_ends_at(at(10, 10, 0, 1))          # sábado 00:01 → terça 00:00
        self.assertEqual(ends, at(10, 13))
        self.assertEqual(calendar.monday_at_or_after(ends), at(10, 19))

    def test_monday_proposal_discussion_ends_thursday(self):
        self.assertEqual(calendar.discussion_ends_at(at(10, 5, 12)), at(10, 8))
        self.assertEqual(calendar.monday_at_or_after(at(10, 8)), at(10, 12))

    def test_next_weekly_tick_is_strictly_after(self):
        self.assertEqual(calendar.monday_after(at(10, 12)), at(10, 19))
        self.assertEqual(calendar.monday_after(at(10, 12) - 1), at(10, 12))
        self.assertTrue(calendar.is_weekly_tick(at(10, 12)))
        self.assertFalse(calendar.is_weekly_tick(at(10, 12) + 1))
        self.assertFalse(calendar.is_weekly_tick(at(10, 13)))
