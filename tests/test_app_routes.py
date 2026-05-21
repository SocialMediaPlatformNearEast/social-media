import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.datastructures import FileStorage

import app as zapp


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        zapp.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = zapp.app.test_client()

    def csrf(self):
        html = self.client.get("/auth").data.decode()
        return html.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]

    def sample_post(self, post_id=42, user_id=8, username="demo", content="hello"):
        return {
            "id": post_id,
            "user_id": user_id,
            "content": content,
            "reply_count": 0,
            "repost_count": 0,
            "like_count": 0,
            "viewer_reposted": False,
            "viewer_liked": False,
            "is_repost": False,
            "user": {
                "id": user_id,
                "username": username,
                "display_name": "Demo User",
                "profile_photo_url": "",
                "level": 1,
            },
        }

    def test_login_requires_credentials(self):
        with patch.object(zapp, "supabase", object()):
            response = self.client.post("/auth", data={
                "csrf_token": self.csrf(),
                "action": "login",
                "username": "",
                "password": ""
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Username and password are required.", response.data)

    def test_nickname_fields_allow_uppercase_input(self):
        auth_html = self.client.get("/auth").data.decode()
        self.assertIn('name="nickname" pattern="[A-Za-z0-9_]{3,24}"', auth_html)
        self.assertIn('name="birthday"', auth_html)

        fake_user = {
            "id": 7,
            "first_name": "Demo",
            "last_name": "User",
            "nickname": "demo",
            "username": "demo",
            "display_name": "Demo User",
            "profile_photo_url": "",
            "theme_color": "#1D9BF0",
            "avatar_color": "#1D9BF0",
            "bio": "",
            "location": "",
            "website": "",
            "gender": "Male",
            "birthday": "",
        }
        with patch.object(zapp, "get_current_user", return_value=fake_user):
            settings_html = self.client.get("/settings").data.decode()
        self.assertIn('name="nickname" maxlength="24" pattern="[A-Za-z0-9_]{3,24}"', settings_html)
        self.assertIn('name="remove_profile_photo"', settings_html)

    def test_shared_post_card_has_menu_actions(self):
        with zapp.app.test_request_context("/"):
            html = zapp.render_template("_post_card.html", viewer={"id": 7}, post={
                "id": 42,
                "user_id": 8,
                "content": "hello",
                "reply_count": 0,
                "repost_count": 0,
                "like_count": 0,
                "viewer_reposted": False,
                "viewer_liked": False,
                "user": {
                    "id": 8,
                    "username": "demo",
                    "display_name": "Demo User",
                    "profile_photo_url": "",
                },
            })
        self.assertIn("Copy link", html)
        self.assertIn("Report post", html)
        self.assertIn("Mute @demo", html)
        self.assertIn("Block @demo", html)

    def test_own_post_card_has_delete_action(self):
        with zapp.app.test_request_context("/"):
            html = zapp.render_template("_post_card.html", viewer={"id": 7}, post={
                "id": 42,
                "user_id": 7,
                "content": "hello",
                "reply_count": 0,
                "repost_count": 0,
                "like_count": 0,
                "viewer_reposted": False,
                "viewer_liked": False,
                "user": {
                    "id": 7,
                    "username": "demo",
                    "display_name": "Demo User",
                    "profile_photo_url": "",
                },
            })
        self.assertIn("Delete post", html)
        self.assertNotIn("Report post", html)

    def test_new_routes_are_registered(self):
        routes = {rule.rule for rule in zapp.app.url_map.iter_rules()}

        self.assertIn("/profile/<username>/<list_type>", routes)
        self.assertIn("/level-guide", routes)
        self.assertIn("/delete_post", routes)
        self.assertIn("/delete_message", routes)
        self.assertIn("/delete_account", routes)
        self.assertIn("/profile", routes)

    def test_level_achievements_report_public_progress(self):
        profile = {"level": 5, "total_xp": 720}
        stats = {"posts": 1, "comments": 4, "followers": 2, "friends": 1}

        achievements = zapp.profile_achievements(profile, stats)

        first_post = next(item for item in achievements if item["id"] == "first_post")
        conversation = next(item for item in achievements if item["id"] == "conversation_starter")
        rising = next(item for item in achievements if item["id"] == "rising_member")

        self.assertTrue(first_post["unlocked"])
        self.assertEqual(first_post["progress_label"], "1 / 1")
        self.assertFalse(conversation["unlocked"])
        self.assertEqual(conversation["progress_label"], "4 / 10")
        self.assertTrue(rising["unlocked"])

    def test_level_guide_page_explains_xp_and_rewards(self):
        fake_user = {
            "id": 7,
            "username": "demo",
            "display_name": "Demo User",
            "profile_photo_url": "",
        }

        with patch.object(zapp, "supabase", object()), \
             patch.object(zapp, "get_current_user", return_value=fake_user), \
             patch.object(zapp, "get_community_highlights", return_value=[]):
            html = self.client.get("/level-guide").data.decode()

        self.assertIn("LvL Guide", html)
        self.assertIn("+10 XP", html)
        self.assertIn("Mythic Legend", html)
        self.assertIn("Achievements are display badges", html)

    def test_community_template_renders_three_timeline_tabs(self):
        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}
        timeline_feeds = {
            "followers": [self.sample_post(1, 8, "follower", "Follower post")],
            "following": [self.sample_post(2, 9, "following", "Following post")],
            "community": [dict(self.sample_post(3, 10, "groupuser", "Community thread"), community={
                "id": 5,
                "name": "Level Talk",
                "slug": "level-talk",
                "accent_color": "#1D9BF0",
            }, community_id=5)],
        }
        with zapp.app.test_request_context("/community?tab=following"):
            html = zapp.render_template(
                "community.html",
                viewer=viewer,
                metrics={"users": 4, "posts": 3, "communities": 1, "likes": 0, "follows": 0},
                recent_members=[],
                popular_users=[],
                trending_posts=[],
                communities=[{"name": "Level Talk", "slug": "level-talk", "description": "XP threads", "accent_color": "#1D9BF0"}],
                activity_items=[],
                community_tabs=zapp.COMMUNITY_TIMELINE_TABS,
                active_tab="following",
                timeline_feeds=timeline_feeds,
                timeline_counts={key: len(value) for key, value in timeline_feeds.items()},
                highlights=[],
            )

        self.assertIn('data-community-hub', html)
        self.assertIn('data-active-tab="following"', html)
        self.assertIn("Followers", html)
        self.assertIn("Following", html)
        self.assertIn("Community", html)
        self.assertIn("Follower post", html)
        self.assertIn("Following post", html)
        self.assertIn("Community thread", html)
        self.assertNotIn("Community video feed", html)

    def test_community_route_defaults_to_following_timeline(self):
        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}
        explore = {
            "metrics": {"users": 0, "posts": 0, "communities": 0, "likes": 0, "follows": 0},
            "recent_members": [],
            "popular_users": [],
            "trending_posts": [],
            "communities": [],
            "activity_items": [],
        }
        timeline = {
            "tabs": zapp.COMMUNITY_TIMELINE_TABS,
            "active_tab": "following",
            "feeds": {"followers": [], "following": [], "community": []},
            "counts": {"followers": 0, "following": 0, "community": 0},
        }

        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_explore_context", return_value=explore), \
             patch.object(zapp, "get_community_timeline_context", return_value=timeline) as timeline_context, \
             patch.object(zapp, "get_community_highlights", return_value=[]):
            html = self.client.get("/community").data.decode()

        timeline_context.assert_called_once_with(viewer, None)
        self.assertIn('data-active-tab="following"', html)
        self.assertIn("Follow people to fill this timeline", html)

    def test_community_timeline_context_uses_three_feed_builders(self):
        viewer = {"id": 7}
        with patch.object(zapp, "get_followers_feed_posts", return_value=[self.sample_post(1)]), \
             patch.object(zapp, "get_following_feed_posts", return_value=[self.sample_post(2)]), \
             patch.object(zapp, "get_community_timeline_posts", return_value=[]):
            context = zapp.get_community_timeline_context(viewer, "followers", limit=5)

        self.assertEqual(context["active_tab"], "followers")
        self.assertEqual(context["counts"]["followers"], 1)
        self.assertEqual(context["counts"]["following"], 1)
        self.assertEqual(context["counts"]["community"], 0)

    def test_auth_page_includes_pwa_install_prompt(self):
        auth_html = self.client.get("/auth").data.decode()

        self.assertIn('data-install-prompt', auth_html)
        self.assertIn('data-install-action', auth_html)
        self.assertIn('Install LvL', auth_html)
        self.assertIn('Add to Home Screen', auth_html)

    def test_manifest_has_core_app_shortcuts(self):
        manifest_path = Path(__file__).resolve().parents[1] / "static" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        shortcuts = {shortcut["name"]: shortcut["url"] for shortcut in manifest["shortcuts"]}

        self.assertEqual(shortcuts["Home"], "/")
        self.assertEqual(shortcuts["Messages"], "/messages")
        self.assertEqual(shortcuts["Notifications"], "/notifications")
        self.assertEqual(shortcuts["Profile"], "/profile")

    def test_profile_metric_cards_link_to_social_lists(self):
        fake_user = {
            "id": 7,
            "username": "demo",
            "display_name": "Demo User",
            "profile_photo_url": "",
            "theme_color": "#1D9BF0",
            "avatar_color": "#1D9BF0",
            "badge_color": "#71767B",
            "level": 2,
            "total_xp": 120,
            "bio": "",
            "location": "",
            "website": "",
            "gender": "Male",
            "created_at": "2026-05-14T00:00:00+00:00",
        }
        with zapp.app.test_request_context("/profile/demo"):
            html = zapp.render_template(
                "profile.html",
                viewer=fake_user,
                profile=fake_user,
                is_own_profile=True,
                is_following=False,
                friend_status=None,
                friend_action_user_id=None,
                safety_state={"muted": False, "blocked": False},
                stats={"posts": 1, "comments": 2, "friends": 3, "following": 4, "followers": 5},
                posts=[],
                mode="posts",
                page=1,
                has_next=False,
                highlights=[],
                profile_banner={"label": "Rising", "description": "Keep going.", "class": "level-1"},
                profile_banner_class="level-1",
                profile_xp_progress=20,
                profile_xp_needed=80,
                profile_xp_current=20,
                profile_xp_span=100,
                next_level_reward={"level": 5, "label": "Rising Charge", "description": "Banner upgrade"},
                achievement_summary={"unlocked": 1, "total": 3},
                achievements=[{
                    "id": "first_post",
                    "name": "First Post",
                    "description": "Share one post.",
                    "current": 1,
                    "target": 1,
                    "progress": 100,
                    "progress_label": "1 / 1",
                    "unlocked": True,
                }],
            )

        self.assertIn('class="profile-metric-link"', html)
        self.assertIn('/profile/demo/following', html)
        self.assertIn('/profile/demo/followers', html)
        self.assertIn('/profile/demo/friends', html)
        self.assertIn("Achievements", html)
        self.assertIn("First Post", html)

    def test_social_list_renders_scrollable_people_panel(self):
        with zapp.app.test_request_context("/profile/demo/followers"):
            html = zapp.render_template(
                "social_list.html",
                viewer={"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""},
                profile={"id": 8, "username": "demo", "display_name": "Demo User"},
                list_type="followers",
                list_title="Followers",
                users=[{
                    "id": 9,
                    "username": "follower",
                    "display_name": "Follower User",
                    "profile_photo_url": "",
                    "level": 1,
                    "is_following": False,
                }],
                highlights=[],
            )

        self.assertIn('class="people-list-scroll"', html)
        self.assertIn('class="person-row"', html)
        self.assertIn('/profile/follower', html)

    def test_create_post_requires_content_or_image(self):
        fake_user = {"id": 7, "username": "demo", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=fake_user):
            response = self.client.post("/create_post", data={"csrf_token": self.csrf(), "content": ""})
        self.assertEqual(response.status_code, 302)

    def test_create_post_accepts_image_only(self):
        class FakePostsTable:
            def __init__(self):
                self.inserted = None

            def insert(self, payload):
                self.inserted = payload
                return self

            def execute(self):
                return type("Response", (), {"data": [{"id": 123}]})()

        class FakeSupabase:
            def __init__(self, table):
                self.posts_table = table

            def table(self, name):
                self.last_table = name
                return self.posts_table

        fake_user = {"id": 7, "username": "demo", "profile_photo_url": ""}
        posts_table = FakePostsTable()
        fake_supabase = FakeSupabase(posts_table)

        with patch.object(zapp, "get_current_user", return_value=fake_user), \
             patch.object(zapp, "upload_image_to_storage", return_value="/static/uploads/posts/7/test.png"), \
             patch.object(zapp, "award_xp"), \
             patch.object(zapp, "supabase", fake_supabase):
            response = self.client.post("/create_post", data={
                "csrf_token": self.csrf(),
                "content": "",
                "image": (io.BytesIO(b"image-bytes"), "post.png"),
            }, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(posts_table.inserted["content"], "")
        self.assertEqual(posts_table.inserted["image_url"], "/static/uploads/posts/7/test.png")

    def test_send_message_blocks_self_message(self):
        fake_user = {"id": 7, "username": "demo", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=fake_user):
            response = self.client.post("/send_message", data={
                "csrf_token": self.csrf(),
                "receiver_id": "7",
                "content": "hello",
                "ajax": "1"
            })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"You cannot send a message to yourself", response.data)

    def test_messages_template_includes_message_delete_controls(self):
        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}
        target = {"id": 8, "username": "demo", "display_name": "Demo User", "profile_photo_url": "", "theme_color": "#1D9BF0"}
        with zapp.app.test_request_context("/messages?u=demo"):
            html = zapp.render_template(
                "messages.html",
                viewer=viewer,
                target_username="demo",
                target_user=target,
                conversations=[],
                all_users=[],
                messages_list=[{
                    "id": 42,
                    "sender_id": 7,
                    "receiver_id": 8,
                    "content": "hello",
                    "created_at": "2026-05-14T12:00:00+00:00",
                }],
                suggested_communities=[],
                message_trending_posts=[],
                message_people=[],
            )

        self.assertIn('/delete_message', html)
        self.assertIn('name="message_id" value="42"', html)
        self.assertIn("Delete message", html)

    def test_settings_template_includes_account_delete_form(self):
        fake_user = {
            "id": 7,
            "first_name": "Demo",
            "last_name": "User",
            "nickname": "demo",
            "username": "demo",
            "display_name": "Demo User",
            "profile_photo_url": "",
            "theme_color": "#1D9BF0",
            "avatar_color": "#1D9BF0",
            "bio": "",
            "location": "",
            "website": "",
            "gender": "Male",
            "birthday": "",
        }
        with zapp.app.test_request_context("/settings"):
            html = zapp.render_template("settings.html", viewer=fake_user)

        self.assertIn('/delete_account', html)
        self.assertIn('name="confirm_username"', html)
        self.assertIn('name="current_password"', html)
        self.assertIn("Delete account", html)

    def test_delete_message_removes_participant_message(self):
        class Result:
            def __init__(self, data=None):
                self.data = data or []

        class FakeTable:
            def __init__(self, db, name):
                self.db = db
                self.name = name
                self.action = None
                self.values = None
                self.filters = []

            def select(self, *_args, **_kwargs):
                self.action = "select"
                return self

            def update(self, values):
                self.action = "update"
                self.values = values
                return self

            def delete(self):
                self.action = "delete"
                return self

            def eq(self, key, value):
                self.filters.append((key, value))
                return self

            def execute(self):
                self.db.calls.append((self.name, self.action, self.values, tuple(self.filters)))
                if self.name == "messages" and self.action == "select":
                    return Result([{"id": 42, "sender_id": 7, "receiver_id": 8}])
                return Result()

        class FakeSupabase:
            def __init__(self):
                self.calls = []

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token"
        with patch.object(zapp, "get_current_user", return_value={"id": 7, "username": "viewer"}), \
             patch.object(zapp, "supabase", fake):
            response = self.client.post("/delete_message", data={
                "csrf_token": "token",
                "message_id": "42",
                "redirect": "/messages?u=demo"
            })

        self.assertEqual(response.status_code, 302)
        self.assertIn(("messages", "delete", None, (("id", 42),)), fake.calls)

    def test_delete_message_rejects_non_participant(self):
        class Result:
            def __init__(self, data=None):
                self.data = data or []

        class FakeTable:
            def __init__(self, db, name):
                self.db = db
                self.name = name
                self.action = None
                self.filters = []

            def select(self, *_args, **_kwargs):
                self.action = "select"
                return self

            def update(self, _values):
                self.action = "update"
                return self

            def delete(self):
                self.action = "delete"
                return self

            def eq(self, key, value):
                self.filters.append((key, value))
                return self

            def execute(self):
                self.db.calls.append((self.name, self.action, tuple(self.filters)))
                if self.name == "messages" and self.action == "select":
                    return Result([{"id": 42, "sender_id": 1, "receiver_id": 2}])
                return Result()

        class FakeSupabase:
            def __init__(self):
                self.calls = []

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token"
        with patch.object(zapp, "get_current_user", return_value={"id": 7, "username": "viewer"}), \
             patch.object(zapp, "supabase", fake):
            response = self.client.post("/delete_message", data={
                "csrf_token": "token",
                "message_id": "42",
                "redirect": "/messages?u=demo"
            })

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(("messages", "delete", (("id", 42),)), fake.calls)

    def test_delete_account_checks_password_and_clears_session(self):
        class Result:
            data = []

        class FakeTable:
            def __init__(self, db, name):
                self.db = db
                self.name = name
                self.action = None
                self.filters = []

            def delete(self):
                self.action = "delete"
                return self

            def eq(self, key, value):
                self.filters.append((key, value))
                return self

            def execute(self):
                self.db.calls.append((self.name, self.action, tuple(self.filters)))
                return Result()

        class FakeSupabase:
            def __init__(self):
                self.calls = []

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token"
            sess["user_id"] = 7
        viewer = {"id": 7, "username": "demo", "password_hash": "$2b$12$placeholderplaceholderplaceholderplaceholderplace"}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "supabase", fake), \
             patch.object(zapp.bcrypt, "checkpw", return_value=True):
            response = self.client.post("/delete_account", data={
                "csrf_token": "token",
                "confirm_username": "demo",
                "current_password": "password123"
            })

        self.assertEqual(response.status_code, 302)
        self.assertIn(("users", "delete", (("id", 7),)), fake.calls)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_website_normalization_accepts_http_only(self):
        self.assertEqual(zapp.normalize_website("https://example.com"), "https://example.com")
        self.assertEqual(zapp.normalize_website("ftp://example.com"), "")

    def test_image_extension_validation(self):
        self.assertTrue(zapp.allowed_image_file("photo.webp"))
        self.assertFalse(zapp.allowed_image_file("photo.exe"))

    def test_default_storage_bucket_matches_project_setup(self):
        self.assertEqual(zapp.STORAGE_BUCKET, "lvl-media")

    def test_profile_image_upload_ensures_storage_bucket(self):
        class FakeBucket:
            def __init__(self):
                self.uploaded = None

            def upload(self, path, payload, file_options=None):
                self.uploaded = (path, payload, file_options)

            def get_public_url(self, path):
                return f"https://cdn.example.com/{path}"

        class FakeStorage:
            def __init__(self):
                self.bucket = FakeBucket()
                self.checked = []

            def get_bucket(self, name):
                self.checked.append(name)
                return {"id": name}

            def from_(self, name):
                return self.bucket

        class FakeSupabase:
            def __init__(self):
                self.storage = FakeStorage()

        fake = FakeSupabase()
        upload = FileStorage(
            stream=io.BytesIO(b"avatar-bytes"),
            filename="avatar.png",
            content_type="image/png",
        )

        with patch.object(zapp, "supabase", fake):
            url = zapp.upload_image_to_storage(upload, "avatars/7")

        self.assertTrue(url.startswith("https://cdn.example.com/avatars/7/"))
        self.assertEqual(fake.storage.checked, [zapp.STORAGE_BUCKET])
        self.assertEqual(fake.storage.bucket.uploaded[2]["content-type"], "image/png")

    def test_image_upload_falls_back_to_local_storage_when_bucket_unavailable(self):
        class BrokenStorage:
            def get_bucket(self, name):
                raise RuntimeError("Bucket not found")

            def create_bucket(self, name, options=None):
                raise RuntimeError("Not allowed")

        class FakeSupabase:
            def __init__(self):
                self.storage = BrokenStorage()

        upload = FileStorage(
            stream=io.BytesIO(b"post-image-bytes"),
            filename="post.png",
            content_type="image/png",
        )
        original_static_folder = zapp.app.static_folder

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                zapp.app.static_folder = tmpdir
                with zapp.app.test_request_context("/"), \
                     patch.object(zapp, "supabase", FakeSupabase()), \
                     patch.object(zapp, "LOCAL_IMAGE_UPLOAD_FALLBACK", True):
                    url = zapp.upload_image_to_storage(upload, "posts/7")
            finally:
                zapp.app.static_folder = original_static_folder

            self.assertTrue(url.startswith("/static/uploads/posts/7/"))
            stored_path = os.path.join(tmpdir, *url.split("/static/", 1)[1].split("/"))
            self.assertTrue(os.path.exists(stored_path))


if __name__ == "__main__":
    unittest.main()
