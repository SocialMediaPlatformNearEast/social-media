import re
import unittest
from pathlib import Path

from app_theme import PROFILE_COLOR_UNLOCK_LEVEL, LEVEL_COLOR_UNLOCKS, THEME_COLORS, level_color_for_level, profile_color_unlocked


COLOR_LITERAL_RE = re.compile(r"#[0-9A-Fa-f]{3,8}")
NEUTRAL_COLORS = {"#000", "#000000", "#fff", "#ffffff"}
INLINE_BOX_STYLE_RE = re.compile(r'style="[^"]*(?:border-radius|border:|padding:|gap:|height:|background:)', re.I)


class ThemeTokenTests(unittest.TestCase):
    def test_level_colors_come_from_theme_tokens(self):
        theme_values = set(THEME_COLORS.values())

        for unlock in LEVEL_COLOR_UNLOCKS:
            self.assertIn(unlock["color"], theme_values)
        self.assertEqual(level_color_for_level(1), THEME_COLORS["muted"])
        self.assertEqual(level_color_for_level(5), THEME_COLORS["cyan"])
        self.assertEqual(level_color_for_level(10), THEME_COLORS["purple"])

    def test_profile_colors_unlock_after_reward_tier(self):
        self.assertFalse(profile_color_unlocked(PROFILE_COLOR_UNLOCK_LEVEL - 1))
        self.assertTrue(profile_color_unlocked(PROFILE_COLOR_UNLOCK_LEVEL))

    def test_stylesheet_colors_are_centralized_in_root_tokens(self):
        root = Path(__file__).resolve().parents[1]
        css = "\n".join(path.read_text() for path in sorted((root / "static" / "css").glob("**/*.css")))
        css_without_root = re.sub(r":root\s*\{.*?\}", "", css, flags=re.S)

        self.assertNotRegex(css_without_root, r"#[0-9A-Fa-f]{3,8}")

    def test_stylesheet_manifest_imports_focused_sections(self):
        root = Path(__file__).resolve().parents[1]
        manifest = (root / "static" / "css" / "styles.css").read_text()

        self.assertIn("sections/rewards.css", manifest)
        self.assertIn("sections/community-timeline.css", manifest)
        self.assertIn("sections/reels.css", manifest)
        self.assertLessEqual(len(manifest.splitlines()), 40)

    def test_site_files_do_not_hardcode_accent_colors(self):
        root = Path(__file__).resolve().parents[1]
        site_files = [
            root / "app.py",
            root / "static" / "css" / "gender.css",
            root / "static" / "js" / "script.js",
            *sorted((root / "templates").glob("*.html")),
        ]

        for path in site_files:
            with self.subTest(path=path.relative_to(root)):
                colors = {match.group(0).lower() for match in COLOR_LITERAL_RE.finditer(path.read_text())}
                non_neutral_colors = colors - NEUTRAL_COLORS
                self.assertFalse(non_neutral_colors, f"Move {non_neutral_colors} into app_theme.py or CSS variables")

    def test_border_radius_uses_design_tokens(self):
        root = Path(__file__).resolve().parents[1]
        css_paths = sorted((root / "static" / "css").glob("**/*.css"))

        for path in css_paths:
            with self.subTest(path=path.relative_to(root)):
                css = path.read_text()
                css_without_roots = re.sub(r":root\s*\{.*?\}", "", css, flags=re.S)
                self.assertNotRegex(css_without_roots, r"border-radius:\s*(?:\d+px|50%)")

    def test_templates_keep_box_geometry_in_classes(self):
        root = Path(__file__).resolve().parents[1]

        for path in sorted((root / "templates").glob("*.html")):
            with self.subTest(path=path.relative_to(root)):
                self.assertIsNone(INLINE_BOX_STYLE_RE.search(path.read_text()))


if __name__ == "__main__":
    unittest.main()
