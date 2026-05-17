import unittest
from datetime import date

from app_utils import birthday_date_limits, normalize_username, profile_banner_for_level, validate_birthday


class AppUtilsTests(unittest.TestCase):
    def test_normalize_username_lowercases_and_trims(self):
        self.assertEqual(normalize_username("  EfeUser  "), "efeuser")

    def test_validate_birthday_rejects_future_and_unrealistic_dates(self):
        today = date(2026, 5, 14)

        self.assertEqual(validate_birthday("3333-02-02", today=today)[1], "Birthday cannot be in the future.")
        self.assertEqual(validate_birthday("1890-01-01", today=today)[1], "Birthday must be a realistic date.")
        self.assertEqual(validate_birthday("not-a-date", today=today)[1], "Birthday must use a real date in YYYY-MM-DD format.")

    def test_validate_birthday_enforces_minimum_age(self):
        birthday, error = validate_birthday("2015-05-14", today=date(2026, 5, 14))

        self.assertIsNone(birthday)
        self.assertEqual(error, "You must be at least 13 years old to use LvL.")

    def test_validate_birthday_accepts_realistic_dates(self):
        birthday, error = validate_birthday("2001-08-20", today=date(2026, 5, 14))

        self.assertEqual(birthday.isoformat(), "2001-08-20")
        self.assertIsNone(error)

    def test_birthday_limits_are_relative_to_today(self):
        limits = birthday_date_limits(date(2026, 5, 14))

        self.assertEqual(limits['min'].isoformat(), "1906-05-14")
        self.assertEqual(limits['max'].isoformat(), "2013-05-14")

    def test_profile_banner_level_tiers(self):
        self.assertEqual(profile_banner_for_level(1)['class'], "level-1")
        self.assertEqual(profile_banner_for_level(2)['class'], "level-2")
        self.assertEqual(profile_banner_for_level(5)['class'], "level-3")
        self.assertEqual(profile_banner_for_level(10)['class'], "level-4")
        self.assertEqual(profile_banner_for_level(20)['class'], "level-5")


if __name__ == "__main__":
    unittest.main()
