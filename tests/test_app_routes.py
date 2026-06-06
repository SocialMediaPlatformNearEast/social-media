import io
import json
import os
import tempfile
import unittest
import inspect
from pathlib import Path
from types import SimpleNamespace
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

    def test_timeline_dedupes_same_post_across_direct_and_repost(self):
        direct = self.sample_post(post_id=42, content="original")
        direct["timeline_created_at"] = "2026-06-01T10:00:00"
        direct["is_repost"] = False
        repost = self.sample_post(post_id=42, content="original")
        repost["timeline_created_at"] = "2026-06-01T11:00:00"
        repost["is_repost"] = True
        repost["reposted_by"] = {"username": "sam", "display_name": "Sam"}

        posts = zapp.dedupe_timeline_posts([repost, direct])

        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0]["is_repost"])

    def test_notification_stacking_uses_reel_id_for_reel_events(self):
        notifications = [
            {"type": "reel_like", "reel_id": 9, "actor_name": "Ada", "is_read": False},
            {"type": "reel_like", "reel_id": 9, "actor_name": "Sam", "is_read": True},
            {"type": "reel_like", "reel_id": 10, "actor_name": "Mina", "is_read": False},
        ]

        stacked = zapp.stack_notifications(notifications)

        self.assertEqual(len(stacked), 2)
        reel_9 = next(item for item in stacked if item["reel_id"] == 9)
        self.assertEqual(reel_9["stack_count"], 2)
        self.assertEqual(reel_9["actor_summary"], "Ada and Sam")

    def test_app_defines_shared_dedupe_helpers_once(self):
        source = inspect.getsource(zapp)

        self.assertEqual(source.count("def dedupe_timeline_posts("), 1)
        self.assertEqual(source.count("def create_notification("), 1)

    def test_recent_duplicate_submission_queries_same_actor_text_and_window(self):
        class Result:
            data = [{"id": 99}]

        class FakeTable:
            def __init__(self):
                self.calls = []

            def select(self, columns):
                self.calls.append(("select", columns))
                return self

            def eq(self, key, value):
                self.calls.append(("eq", key, value))
                return self

            def gte(self, key, value):
                self.calls.append(("gte", key, value))
                return self

            def limit(self, value):
                self.calls.append(("limit", value))
                return self

            def execute(self):
                return Result()

        table = FakeTable()
        fake_supabase = SimpleNamespace(table=lambda name: table)

        with patch.object(zapp, "supabase", fake_supabase):
            duplicate = zapp.recent_duplicate_submission(
                "messages",
                {"sender_id": 7, "receiver_id": 8},
                "content",
                "hello",
            )

        self.assertTrue(duplicate)
        self.assertIn(("eq", "sender_id", 7), table.calls)
        self.assertIn(("eq", "receiver_id", 8), table.calls)
        self.assertIn(("eq", "content", "hello"), table.calls)
        self.assertTrue(any(call[0] == "gte" and call[1] == "created_at" for call in table.calls))
        self.assertIn(("limit", 1), table.calls)

    def test_submit_script_locks_content_forms_without_native_fallback_duplicates(self):
        script = Path("static/js/script.js").read_text()

        self.assertIn("function lockSubmitForm(form, submitBtn)", script)
        self.assertIn("composer.addEventListener('submit'", script)
        self.assertIn("chatForm.dataset.submitting === '1'", script)
        self.assertIn("commentForm.dataset.submitting === '1'", script)
        self.assertNotIn("chatForm.submit();", script)
        self.assertNotIn("commentForm.submit();", script)

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

    def test_auth_page_lists_enabled_social_providers_only(self):
        auth_html = self.client.get("/auth").data.decode()

        self.assertIn("Continue securely with", auth_html)
        self.assertIn("Continue with email", auth_html)
        self.assertIn("Powered by Supabase Auth.", auth_html)
        self.assertIn('class="brand-mark brand-logo-large"', auth_html)
        self.assertIn("assets/icon-512.png", auth_html)
        self.assertNotIn('brand-mark large">LvL', auth_html)
        self.assertEqual([provider["provider"] for provider in zapp.SUPABASE_SOCIAL_PROVIDERS], ["google", "github", "discord"])
        for provider in zapp.SUPABASE_SOCIAL_PROVIDERS:
            self.assertIn(provider["label"], auth_html)
            self.assertIn(f'/auth/oauth/{provider["provider"]}', auth_html)
        self.assertNotIn('/auth/oauth/facebook', auth_html)
        self.assertNotIn('/auth/oauth/apple', auth_html)
        self.assertNotIn('/auth/oauth/azure', auth_html)
        self.assertNotIn('/auth/oauth/x', auth_html)

    def test_oauth_start_rejects_disabled_provider_before_supabase_call(self):
        class FakeAuth:
            def sign_in_with_oauth(self, _credentials):
                raise AssertionError("disabled providers must not start Supabase OAuth")

        with patch.object(zapp, "supabase", SimpleNamespace(auth=FakeAuth())):
            response = self.client.get("/auth/oauth/facebook")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/auth"))

    def test_oauth_start_redirects_to_supabase_provider(self):
        class FakeStorage:
            def __init__(self):
                self.items = {}

            def get_item(self, key):
                return self.items.get(key)

            def set_item(self, key, value):
                self.items[key] = value

        class FakeAuth:
            def __init__(self):
                self.calls = []
                self._storage_key = "supabase.auth.token"
                self._storage = FakeStorage()

            def sign_in_with_oauth(self, credentials):
                self.calls.append(credentials)
                self._storage.set_item("supabase.auth.token-code-verifier", "test-verifier")
                return SimpleNamespace(url="https://project.supabase.co/auth/v1/authorize?provider=google")

        fake = SimpleNamespace(auth=FakeAuth())

        with patch.object(zapp, "supabase", fake):
            response = self.client.get("/auth/oauth/google")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "https://project.supabase.co/auth/v1/authorize?provider=google")
        credentials = fake.auth.calls[0]
        self.assertEqual(credentials["provider"], "google")
        self.assertTrue(credentials["options"]["redirect_to"].endswith("/auth/oauth/callback"))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["oauth_provider"], "google")
            self.assertEqual(sess["oauth_code_verifier"], "test-verifier")
            self.assertEqual(credentials["options"]["query_params"]["state"], sess["oauth_state"])

    def test_oauth_callback_logs_in_existing_user_by_email(self):
        class FakeStorage:
            def __init__(self):
                self.items = {}

            def set_item(self, key, value):
                self.items[key] = value

            def get_item(self, key):
                return self.items.get(key)

            def remove_item(self, key):
                self.items.pop(key, None)

        class FakeAuth:
            def __init__(self):
                self._storage_key = "supabase.auth.token"
                self._storage = FakeStorage()
                self.exchange_params = None

            def exchange_code_for_session(self, params):
                self.exchange_params = params
                user = SimpleNamespace(
                    id="11111111-1111-1111-1111-111111111111",
                    email="oauth@example.com",
                    user_metadata={
                        "full_name": "OAuth Member",
                        "avatar_url": "https://example.com/avatar.png",
                    },
                    app_metadata={"provider": "google"},
                )
                return SimpleNamespace(user=user, session=SimpleNamespace(user=user))

        class FakeUsersTable:
            def __init__(self, fake):
                self.fake = fake
                self.filters = {}
                self.mode = "select"
                self.payload = None

            def select(self, *_args, **_kwargs):
                self.mode = "select"
                return self

            def update(self, payload):
                self.mode = "update"
                self.payload = payload
                return self

            def eq(self, key, value):
                self.filters[key] = value
                return self

            def execute(self):
                if self.mode == "update":
                    self.fake.updated_payload = self.payload
                    return SimpleNamespace(data=[])
                if self.filters.get("supabase_auth_user_id"):
                    return SimpleNamespace(data=[])
                if self.filters.get("email") == "oauth@example.com":
                    return SimpleNamespace(data=[{"id": 44, "email": "oauth@example.com", "username": "oauthmember"}])
                return SimpleNamespace(data=[])

        class FakeSupabase:
            def __init__(self):
                self.auth = FakeAuth()
                self.updated_payload = None

            def table(self, name):
                self.table_name = name
                return FakeUsersTable(self)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "expected-state"
            sess["oauth_provider"] = "google"
            sess["oauth_code_verifier"] = "stored-verifier"

        with patch.object(zapp, "supabase", fake):
            response = self.client.get("/auth/oauth/callback?code=abc123&state=expected-state")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/"))
        self.assertEqual(fake.auth.exchange_params["auth_code"], "abc123")
        self.assertEqual(fake.auth._storage.items["supabase.auth.token-code-verifier"], "stored-verifier")
        self.assertEqual(fake.updated_payload["oauth_provider"], "google")
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["user_id"], 44)
            self.assertNotIn("pending_oauth_profile", sess)

    def test_oauth_callback_sends_new_user_to_social_onboarding(self):
        class FakeAuth:
            _storage_key = "supabase.auth.token"

            class Storage:
                def set_item(self, *_args):
                    pass

            _storage = Storage()

            def exchange_code_for_session(self, _params):
                user = SimpleNamespace(
                    id="22222222-2222-2222-2222-222222222222",
                    email="new@example.com",
                    user_metadata={"name": "New OAuth"},
                    app_metadata={"provider": "github"},
                )
                return SimpleNamespace(user=user, session=SimpleNamespace(user=user))

        class FakeUsersTable:
            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args):
                return self

            def execute(self):
                return SimpleNamespace(data=[])

        fake = SimpleNamespace(auth=FakeAuth(), table=lambda _name: FakeUsersTable())
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "expected-state"
            sess["oauth_provider"] = "github"
            sess["oauth_code_verifier"] = "stored-verifier"

        with patch.object(zapp, "supabase", fake):
            response = self.client.get("/auth/oauth/callback?code=abc123&state=expected-state")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/auth/oauth/onboarding"))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["pending_oauth_profile"]["email"], "new@example.com")
            self.assertEqual(sess["pending_oauth_profile"]["provider"], "github")
            self.assertEqual(sess["pending_oauth_profile"]["first_name"], "New")

    def test_oauth_onboarding_creates_lvl_user(self):
        class FakeUsersTable:
            def __init__(self, fake, name):
                self.fake = fake
                self.name = name
                self.payload = None

            def insert(self, payload):
                self.payload = payload
                return self

            def execute(self):
                if self.name == "users":
                    self.fake.inserted_payload = self.payload
                return SimpleNamespace(data=[{"id": 55, **self.payload}])

        class FakeSupabase:
            def __init__(self):
                self.inserted_payload = None

            def table(self, name):
                self.table_name = name
                return FakeUsersTable(self, name)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["pending_oauth_profile"] = {
                "provider": "google",
                "subject": "33333333-3333-3333-3333-333333333333",
                "email": "join@example.com",
                "first_name": "Join",
                "last_name": "Member",
                "display_name": "Join Member",
                "avatar_url": "",
            }
        csrf_token = self.csrf()

        with patch.object(zapp, "supabase", fake):
            response = self.client.post("/auth/oauth/onboarding", data={
                "csrf_token": csrf_token,
                "first_name": "Join",
                "last_name": "Member",
                "nickname": "joinmember",
                "email": "join@example.com",
                "birthday": "2000-01-01",
                "gender": "Male",
            })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/"))
        self.assertEqual(fake.inserted_payload["oauth_provider"], "google")
        self.assertEqual(fake.inserted_payload["supabase_auth_user_id"], "33333333-3333-3333-3333-333333333333")
        self.assertEqual(fake.inserted_payload["username"], "joinmember")
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["user_id"], 55)
            self.assertNotIn("pending_oauth_profile", sess)

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

    def test_single_post_uses_menu_for_report_action(self):
        with zapp.app.test_request_context("/post/42"):
            html = zapp.render_template("post.html", viewer={"id": 7}, post={
                "id": 42,
                "user_id": 8,
                "content": "hello",
                "created_at": "2026-06-06T00:00:00+00:00",
                "user": {
                    "id": 8,
                    "username": "demo",
                    "display_name": "Demo User",
                    "profile_photo_url": "",
                },
            }, comments=[])

        self.assertIn('class="post-menu-wrap"', html)
        self.assertIn('data-post-menu-toggle', html)
        self.assertIn('class="post-menu"', html)
        self.assertIn("Report post", html)
        self.assertIn("Mute @demo", html)
        self.assertIn("Block @demo", html)
        self.assertNotIn('class="inline-report-form"', html)

    def test_new_routes_are_registered(self):
        routes = {rule.rule for rule in zapp.app.url_map.iter_rules()}

        self.assertIn("/profile/<username>/<list_type>", routes)
        self.assertIn("/admin/users/level", routes)
        self.assertIn("/setup-health", routes)
        self.assertIn("/level-guide", routes)
        self.assertIn("/reels", routes)
        self.assertIn("/auth/oauth/<provider>", routes)
        self.assertIn("/auth/oauth/callback", routes)
        self.assertIn("/auth/oauth/onboarding", routes)
        self.assertIn("/reels/upload", routes)
        self.assertIn("/reels/<int:reel_id>/like", routes)
        self.assertIn("/delete_post", routes)
        self.assertIn("/delete_message", routes)
        self.assertIn("/delete_account", routes)
        self.assertIn("/profile", routes)
        self.assertIn("/activity", routes)

    def test_timeline_dedupe_keeps_newest_post_instance(self):
        posts = [
            {"id": 1, "timeline_created_at": "2026-06-05T12:00:00", "is_repost": True},
            {"id": 1, "timeline_created_at": "2026-06-05T11:00:00", "is_repost": False},
            {"id": 2, "timeline_created_at": "2026-06-05T10:00:00", "is_repost": False},
        ]

        deduped = zapp.dedupe_timeline_posts(posts)

        self.assertEqual([post["id"] for post in deduped], [1, 2])
        self.assertTrue(deduped[0]["is_repost"])

    def sample_reel(self, reel_id=1, user_id=7):
        return {
            "id": reel_id,
            "user_id": user_id,
            "video_url": "https://example.com/reel.mp4",
            "caption": "hello reel",
            "visibility": "public",
            "allow_comments": True,
            "allow_downloads": False,
            "autoplay_next": True,
            "view_count": 0,
            "author": {
                "id": user_id,
                "username": "demo",
                "display_name": "Demo User",
                "profile_photo_url": "",
            },
            "user": {
                "id": user_id,
                "username": "demo",
                "display_name": "Demo User",
                "profile_photo_url": "",
            },
            "community": None,
            "like_count": 0,
            "comment_count": 0,
            "viewer_liked": False,
            "is_owner": True,
            "is_demo": False,
        }

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

    def test_forced_sin_account_level_override(self):
        user = {
            "id": 9,
            "username": "sin",
            "nickname": "sin",
            "display_name": "sin sin",
            "level": 2,
            "total_xp": 74,
        }

        zapp.apply_forced_user_levels(user)

        self.assertEqual(user["level"], 50)
        self.assertGreaterEqual(user["total_xp"], zapp.xp_required_for_level(50))
        self.assertEqual(user["activity_title"], "Icon Legend")

    def test_reel_author_renders_forced_level_badge(self):
        reel = self.sample_reel(user_id=9)
        reel["author"].update({
            "username": "sin",
            "nickname": "sin",
            "display_name": "sin sin",
            "level": 2,
            "total_xp": 74,
        })
        reel["user"] = reel["author"]
        zapp.apply_forced_user_levels(reel)

        with zapp.app.test_request_context("/reels"):
            html = zapp.render_template("_reel_card.html", viewer={"id": 7, "display_name": "Viewer", "username": "viewer"}, reel=reel)

        self.assertIn("reel-level-badge", html)
        self.assertIn("LvL 50", html)

    def test_admin_level_update_requires_token_and_updates_user_level(self):
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
                self.db.updated = values
                return self

            def eq(self, key, value):
                self.filters.append((key, value))
                return self

            def execute(self):
                self.db.calls.append((self.name, self.action, self.values, tuple(self.filters)))
                if self.name == "users" and self.action == "select":
                    return Result([{
                        "id": 9,
                        "username": "sin",
                        "display_name": "sin sin",
                        "level": 2,
                        "total_xp": 74,
                    }])
                return Result([{"id": 9, **(self.values or {})}])

        class FakeSupabase:
            def __init__(self):
                self.calls = []
                self.updated = None

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token"
        with patch.dict(os.environ, {"LVL_ADMIN_TOKEN": "secret"}), \
             patch.object(zapp, "get_current_user", return_value={"id": 7, "username": "admin"}), \
             patch.object(zapp, "supabase", fake):
            response = self.client.post("/admin/users/level", data={
                "csrf_token": "token",
                "admin_token": "secret",
                "username": "sin",
                "level": "50",
            })

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(fake.updated["level"], 50)
        self.assertEqual(fake.updated["total_xp"], zapp.xp_required_for_level(50))
        self.assertEqual(fake.updated["activity_title"], "Icon Legend")
        self.assertEqual(fake.updated["badge_color"], zapp.badge_color_for_level(50))

        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token"
        with patch.dict(os.environ, {"LVL_ADMIN_TOKEN": "secret"}), \
             patch.object(zapp, "get_current_user", return_value={"id": 7, "username": "admin"}), \
             patch.object(zapp, "supabase", fake):
            denied = self.client.post("/admin/users/level", data={
                "csrf_token": "token",
                "admin_token": "wrong",
                "username": "sin",
                "level": "50",
            })

        self.assertEqual(denied.status_code, 403)

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
        self.assertIn("Reward Roadmap", html)
        self.assertIn("Profile Color", html)
        self.assertIn("App Icon Recolor", html)
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
        self.assertIn('class="community-lens-strip"', html)
        self.assertIn("History", html)
        self.assertIn("Trends", html)
        self.assertIn("News", html)
        self.assertIn('data-community-pane="followers"', html)
        self.assertIn('aria-current="page"', html)
        self.assertRegex(html, r'data-community-pane="followers"[\s\S]+?hidden')
        self.assertNotIn("Community video feed", html)

        with zapp.app.test_request_context("/community?tab=following"):
            empty_html = zapp.render_template(
                "community.html",
                viewer=viewer,
                metrics={"users": 4, "posts": 0, "communities": 1, "likes": 0, "follows": 0},
                recent_members=[],
                popular_users=[],
                trending_posts=[],
                communities=[],
                activity_items=[],
                community_tabs=zapp.COMMUNITY_TIMELINE_TABS,
                active_tab="following",
                timeline_feeds={"followers": [], "following": [], "community": []},
                timeline_counts={"followers": 0, "following": 0, "community": 0},
                highlights=[],
            )

        self.assertIn("What this timeline means", empty_html)
        self.assertIn("This is the middle timeline", empty_html)

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

    def test_static_asset_version_is_consistent(self):
        styles = Path("static/css/styles.css").read_text()
        service_worker = Path("static/service-worker.js").read_text()
        expected_query = f"?v={zapp.ASSET_VERSION}"

        for line in styles.splitlines():
            if line.startswith("@import"):
                self.assertIn(expected_query, line)

        self.assertIn(f"const ASSET_VERSION = '{zapp.ASSET_VERSION}';", service_worker)
        self.assertIn("sections/activity.css", styles)

    def test_mobile_settings_actions_stay_in_document_flow(self):
        settings_css = Path("static/css/sections/settings.css").read_text()
        mobile_settings_css = settings_css.split("@media (max-width: 720px)", 1)[1]
        actions_rule = mobile_settings_css.split(".form-actions", 1)[1].split("}", 1)[0]

        self.assertIn("position: static", actions_rule)
        self.assertIn("margin: 0", actions_rule)
        self.assertNotIn("position: sticky", actions_rule)
        self.assertNotIn("margin-inline: -", actions_rule)

    def test_settings_profile_color_control_labels_visible_effect(self):
        settings_html = Path("templates/settings.html").read_text()
        settings_css = Path("static/css/sections/settings.css").read_text()

        self.assertIn("Profile banner color", settings_html)
        self.assertIn("Changes the banner on your profile", settings_html)
        self.assertIn("--profile-preview-color", settings_css)
        self.assertNotIn("--lvl-white-10", settings_css)

    def test_mobile_settings_profile_preview_avatar_clears_text(self):
        settings_css = Path("static/css/sections/settings.css").read_text()
        mobile_settings_css = settings_css.split("@media (max-width: 720px)", 1)[1]
        preview_rule = mobile_settings_css.split(".settings-container .profile-preview-card", 1)[1].split("}", 1)[0]
        name_rule = mobile_settings_css.split(".settings-container .profile-preview-card strong", 1)[1].split("}", 1)[0]

        self.assertIn("padding: 146px 14px 14px", preview_rule)
        self.assertIn("min-height: 270px", preview_rule)
        self.assertIn("margin-top: 0", name_rule)

    def test_reels_script_keeps_sound_preference_for_session(self):
        script = Path("static/js/script.js").read_text()

        self.assertIn("lvlReelsSoundOn", script)
        self.assertIn("sessionStorage.setItem", script)
        self.assertIn("applySoundPreferenceToAll", script)

    def test_auth_page_includes_pwa_install_prompt(self):
        auth_html = self.client.get("/auth").data.decode()

        self.assertIn('data-install-prompt', auth_html)
        self.assertIn('data-install-action', auth_html)
        self.assertIn('data-install-manual', auth_html)
        self.assertIn('Install LvL', auth_html)
        self.assertIn('Add to Home Screen', auth_html)

    def test_reels_redirects_unauthenticated_users(self):
        with patch.object(zapp, "get_current_user", return_value=None):
            response = self.client.get("/reels")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth", response.location)

    def test_reels_renders_authenticated_page(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reels", return_value=([self.sample_reel()], False)):
            html = self.client.get("/reels").data.decode()

        self.assertIn("Reels", html)
        self.assertIn('data-reels-feed', html)
        self.assertIn('mobile-reels-upload-cta', html)
        self.assertIn('mobile-reel-upload-action', html)
        self.assertIn("hello reel", html)
        self.assertNotIn('aria-label="Reels pagination"', html)

    def test_reels_empty_real_feed_does_not_use_demo_when_table_ready(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reels", return_value=([], False)):
            html = self.client.get("/reels").data.decode()

        self.assertIn("No real reels yet", html)
        self.assertNotIn("Demo reel", html)

    def test_reels_uses_demo_fallback_only_when_table_unavailable(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reels", side_effect=RuntimeError("reels relation does not exist")):
            html = self.client.get("/reels").data.decode()

        self.assertIn("Demo reel", html)
        self.assertIn("Reels database table is not ready", html)

    def test_reel_upload_renders_for_authenticated_user(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reel_upload_communities", return_value=[]):
            html = self.client.get("/reels/upload").data.decode()

        self.assertIn("Upload Reel", html)
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertIn('accept="video/mp4,video/webm,video/quicktime,video/x-m4v"', html)

    def test_reel_upload_rejects_missing_video(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reel_upload_communities", return_value=[]):
            response = self.client.post("/reels/upload", data={
                "csrf_token": self.csrf(),
                "caption": "no file",
                "visibility": "public",
                "allow_comments": "on",
                "autoplay_next": "on",
            }, follow_redirects=True)

        self.assertIn(b"Choose a video to upload.", response.data)

    def test_reel_upload_rejects_unsupported_extension(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reel_upload_communities", return_value=[]):
            response = self.client.post("/reels/upload", data={
                "csrf_token": self.csrf(),
                "caption": "bad file",
                "visibility": "public",
                "video": (io.BytesIO(b"not-video"), "clip.txt"),
            }, content_type="multipart/form-data", follow_redirects=True)

        self.assertIn(b"Videos must be MP4, WebM, MOV, or M4V.", response.data)

    def test_reel_upload_inserts_when_video_upload_is_mocked(self):
        class Result:
            def __init__(self, data=None):
                self.data = data or []

        class FakeTable:
            def __init__(self):
                self.inserted = None

            def insert(self, payload):
                self.inserted = payload
                return self

            def execute(self):
                return Result([{"id": 123}])

        class FakeSupabase:
            def __init__(self):
                self.reels = FakeTable()

            def table(self, name):
                return self.reels

        fake = FakeSupabase()
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_reel_upload_communities", return_value=[]), \
             patch.object(zapp, "upload_video_to_storage", return_value=("https://cdn.example.com/reel.mp4", "reels/7/reel.mp4")), \
             patch.object(zapp, "award_xp") as award_xp, \
             patch.object(zapp, "supabase", fake):
            response = self.client.post("/reels/upload", data={
                "csrf_token": self.csrf(),
                "caption": "mock upload",
                "visibility": "public",
                "allow_comments": "on",
                "autoplay_next": "on",
                "video": (io.BytesIO(b"video-bytes"), "clip.mp4"),
            }, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(fake.reels.inserted["video_url"], "https://cdn.example.com/reel.mp4")
        self.assertEqual(fake.reels.inserted["storage_path"], "reels/7/reel.mp4")
        award_xp.assert_called_once_with(7, "reel_created", 15, 123)

    def test_reel_like_endpoint_toggles_like_json(self):
        class Result:
            def __init__(self, data=None, count=0):
                self.data = data or []
                self.count = count

        class FakeTable:
            def __init__(self, db, name):
                self.db = db
                self.name = name
                self.action = None
                self.filters = []

            def select(self, *_args, **_kwargs):
                self.action = "select"
                return self

            def insert(self, payload):
                self.action = "insert"
                self.db.inserted = payload
                return self

            def delete(self):
                self.action = "delete"
                return self

            def eq(self, key, value):
                self.filters.append((key, value))
                return self

            def execute(self):
                self.db.calls.append((self.name, self.action, tuple(self.filters)))
                if self.action == "select" and self.filters == [("reel_id", 1), ("user_id", 7)]:
                    return Result([])
                if self.action == "select" and self.filters == [("reel_id", 1)]:
                    return Result([], count=1)
                return Result([])

        class FakeSupabase:
            def __init__(self):
                self.calls = []
                self.inserted = None

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token"
        with patch.object(zapp, "get_current_user", return_value={"id": 7, "username": "demo"}), \
             patch.object(zapp, "get_reel_by_id", return_value=self.sample_reel()), \
             patch.object(zapp, "supabase", fake):
            response = self.client.post("/reels/1/like", data={"csrf_token": "token", "ajax": "1"})

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["liked"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(fake.inserted, {"reel_id": 1, "user_id": 7})

    def test_layout_contains_reels_navigation(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with zapp.app.test_request_context("/"):
            html = zapp.render_template("index.html", viewer=viewer, posts=[], mode="all", highlights=[], page=1, has_next=False)

        self.assertIn('/reels', html)
        self.assertIn('Reels', html)
        self.assertIn('<aside class="left-rail menu-open">', html)
        self.assertNotIn('id="sidebar-toggle"', html)
        self.assertNotIn('class="mobile-sidebar-toggle"', html)
        self.assertIn('class="mobile-brand mobile-brand-logo-only" href="/" aria-label="Home"', html)
        self.assertIn('class="app-topbar topbar-search-only"', html)
        self.assertIn('topbar-search-only', html)
        self.assertIn('class="topbar-search"', html)
        self.assertNotIn('data-web-back', html)
        self.assertIn('class="topbar-actions"', html)
        self.assertIn('class="topbar-action', html)
        self.assertIn('aria-label="Messages"', html)
        self.assertIn('aria-label="Alerts"', html)
        left_rail_nav = html.split('<nav class="nav-list"', 1)[1].split('</nav>', 1)[0]
        self.assertNotIn('href="/search"', left_rail_nav)
        self.assertNotIn('aria-label="Search"', left_rail_nav)
        self.assertNotIn('href="/messages"', left_rail_nav)
        self.assertNotIn('aria-label="Messages"', left_rail_nav)
        self.assertNotIn('href="/notifications"', left_rail_nav)
        self.assertNotIn('aria-label="Alerts"', left_rail_nav)
        self.assertNotIn('href="/activity"', left_rail_nav)
        self.assertNotIn('aria-label="Activity"', left_rail_nav)
        self.assertNotIn('aria-label="Profile"', left_rail_nav)
        self.assertIn('class="mini-profile" href="/profile/demo"', html)
        self.assertIn('action="/search"', html.split('<form class="topbar-search"', 1)[1])
        topbar_actions = html.split('<div class="topbar-actions"', 1)[1]
        self.assertIn('href="/messages"', topbar_actions)
        self.assertIn('href="/notifications"', topbar_actions)
        self.assertIn('class="mobile-header-search"', html)
        self.assertIn('class="mobile-header-actions"', html)
        self.assertIn('class="nav-label sr-only"', html)
        self.assertIn('class="mobile-nav-label sr-only"', html)
        self.assertIn('data-mobile-profile-trigger', html)
        self.assertIn('data-mobile-account-menu', html)
        self.assertIn('Switch account', html)
        self.assertIn('Add account', html)
        self.assertIn('Log out', html)
        mobile_nav = html.split('<nav class="mobile-bottom-nav"', 1)[1]
        self.assertNotIn('href="/messages"', mobile_nav)
        self.assertNotIn('href="/notifications"', mobile_nav)
        mobile_order = [
            mobile_nav.index('aria-label="Home"'),
            mobile_nav.index('aria-label="Community"'),
            mobile_nav.index('aria-label="Create post"'),
            mobile_nav.index('aria-label="Reels"'),
            mobile_nav.index('aria-label="Profile"'),
        ]
        self.assertEqual(sorted(mobile_order), mobile_order)

        with zapp.app.test_request_context("/search"):
            search_html = zapp.render_template(
                "search.html",
                viewer=viewer,
                query="",
                tab="top",
                posts=[],
                users=[],
                suggested_users=[],
                recent_posts=[],
                highlights=[],
                page=1,
                has_next=False,
            )
        self.assertIn('data-web-back', search_html)
        self.assertIn('class="topbar-actions"', search_html)

    def test_mobile_reels_keep_immersive_video_fit(self):
        css = Path("static/css/sections/reels.css").read_text()

        self.assertIn(".reel-video", css)
        self.assertRegex(css, r"(?s)\.reel-video\s*\{[^}]*object-fit:\s*cover")
        self.assertNotRegex(css, r"(?s)\.reel-video\s*\{[^}]*object-fit:\s*contain")

    def test_reels_header_reserves_shared_topbar_space(self):
        css = Path("static/css/sections/reels.css").read_text()

        self.assertIn("--reels-topbar-offset: 69px", css)
        self.assertIn("--reels-header-block: 80px", css)
        self.assertIn("min-height: calc(100svh - var(--reels-topbar-offset))", css)
        self.assertIn("top: var(--reels-topbar-offset)", css)
        self.assertIn("height: calc(100svh - var(--reels-topbar-offset) - var(--reels-header-block))", css)
        self.assertIn("min-height: calc(100svh - var(--reels-topbar-offset) - var(--reels-header-block))", css)
        self.assertIn("--reels-topbar-offset: 64px", css)
        self.assertIn("calc(100dvh - 64px - var(--reels-mobile-header)", css)
        self.assertNotIn("--reels-topbar-offset: 119px", css)
        self.assertIn("top: auto", css)

    def test_mobile_reel_comments_keep_composer_above_bottom_nav(self):
        css = Path("static/css/sections/reels.css").read_text()

        self.assertIn("--reels-mobile-bottom-nav: 76px", css)
        self.assertIn("bottom: calc(var(--reels-mobile-bottom-nav) + env(safe-area-inset-bottom))", css)
        self.assertIn("max-height: calc(100dvh - 64px - var(--reels-mobile-bottom-nav) - env(safe-area-inset-bottom))", css)
        self.assertIn(".reel-comment-submit-form", css)
        self.assertIn("position: sticky", css)

    def test_mobile_reels_pagination_does_not_create_empty_bottom_section(self):
        css = Path("static/css/sections/reels.css").read_text()

        self.assertIn(".reels-pagination", css)
        self.assertIn("bottom: calc(var(--reels-mobile-bottom-nav) + 14px + env(safe-area-inset-bottom))", css)
        self.assertIn("pointer-events: none", css)
        self.assertIn(".reels-pagination .outline-button", css)
        self.assertIn("pointer-events: auto", css)

    def test_mobile_reels_uses_bottom_plus_instead_of_header_upload_cta(self):
        css = Path("static/css/sections/reels.css").read_text()
        mobile_nav_css = Path("static/css/sections/mobile-navigation.css").read_text()

        self.assertIn("--reels-mobile-header: 52px", css)
        self.assertIn(".reels-header-title", css)
        self.assertIn("display: none", css)
        self.assertIn(".reels-header .compact-action", css)
        self.assertIn("display: none", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        self.assertIn(".reels-header .compact-action", mobile_nav_css)
        self.assertIn("display: none", mobile_nav_css)
        self.assertNotIn("display: inline-flex", mobile_nav_css.split(".reels-header .compact-action", 1)[1].split("}", 1)[0])

    def test_reels_header_only_shows_for_you_and_following_tabs(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with zapp.app.test_request_context("/reels"):
            html = zapp.render_template(
                "reels.html",
                viewer=viewer,
                reels=[],
                page=1,
                has_next=False,
                table_ready=True,
                tab="for_you",
                highlights=[],
            )

        tabs = html.split('<nav class="reels-tabs"', 1)[1].split("</nav>", 1)[0]
        self.assertIn("For You", tabs)
        self.assertIn("Following", tabs)
        self.assertNotIn("Discovery", tabs)
        self.assertNotIn("tab=discovery", tabs)

    def test_reels_route_normalizes_removed_discovery_tab(self):
        captured_context = {}

        def fake_render(_template, **context):
            captured_context.update(context)
            return "ok"

        with patch.object(zapp, "get_current_user", return_value={"id": 7, "username": "demo"}), \
             patch.object(zapp, "get_reels", return_value=([], False)) as fake_get_reels, \
             patch.object(zapp, "render_template", side_effect=fake_render):
            response = self.client.get("/reels?tab=discovery")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_context["tab"], "for_you")
        self.assertEqual(fake_get_reels.call_args.kwargs["tab"], "for_you")

    def test_sidebar_labels_are_visible_only_when_menu_is_open(self):
        css = Path("static/css/sections/navigation.css").read_text()
        hardening_css = Path("static/css/sections/hardening.css").read_text()
        mobile_drawer_css = Path("static/css/sections/mobile-drawer.css").read_text()
        mobile_navigation_css = Path("static/css/sections/mobile-navigation.css").read_text()
        script = Path("static/js/script.js").read_text()

        self.assertIn(".left-rail:not(.menu-open) .nav-list a .sr-only", css)
        self.assertIn(".mobile-bottom-nav a .sr-only", css)
        self.assertIn(".left-rail.menu-open .nav-list a", css)
        self.assertIn("justify-content: flex-start", css)
        self.assertIn("gap: 14px", css)
        legacy_css = Path("static/css/sections/legacy-polish.css").read_text()
        self.assertIn("transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);", legacy_css)
        self.assertIn(".left-rail-wrapper:has(.left-rail.menu-open)", legacy_css)
        self.assertIn(".left-rail.menu-open .mini-profile div", hardening_css)
        self.assertIn("display: flex !important", hardening_css)
        self.assertIn("text-overflow: ellipsis", hardening_css)
        self.assertIn(".left-rail.menu-open", mobile_drawer_css)
        self.assertIn("display: none !important", mobile_drawer_css)
        self.assertIn(".mobile-account-menu:not([hidden])", mobile_drawer_css)
        self.assertIn("grid-template-columns: 40px minmax(0, 1fr) auto", mobile_navigation_css)
        self.assertIn("data-mobile-profile-trigger", script)
        self.assertIn("data-mobile-account-menu", script)
        self.assertIn("setTimeout(openAccountMenu, 450)", script)
        self.assertNotIn("mobile-sidebar-toggle", script)

    def test_community_highlights_badges_and_profile_hover_are_guarded(self):
        css = Path("static/css/sections/community-highlights.css").read_text()

        self.assertIn(".community-highlights.panel", css)
        self.assertIn("padding: var(--space-8)", css)
        self.assertIn(".community-highlights.panel h2", css)
        self.assertIn("font-size: clamp(21px, 1.6vw, 24px)", css)
        self.assertIn(".mini-profile:hover", css)
        self.assertIn("text-decoration: none", css)
        self.assertIn(".left-rail.menu-open .mini-profile", css)
        self.assertIn("border-radius: var(--radius-lg)", css)
        self.assertIn(".mini-profile .level-badge", css)
        self.assertIn(".mini-profile .community-level-badge", css)
        self.assertIn("min-width: calc(var(--badge-height-sm) * 3)", css)

    def test_post_actions_are_icon_first_controls(self):
        with zapp.app.test_request_context("/"):
            html = zapp.render_template("_post_card.html", viewer={"id": 7}, post=self.sample_post())

        self.assertIn('aria-label="Reply to post"', html)
        self.assertIn('aria-label="Repost"', html)
        self.assertIn('aria-label="Like post"', html)
        self.assertIn('class="post-action-icon"', html)
        self.assertNotIn('<span aria-hidden="true">Reply</span>', html)
        self.assertNotIn('<span aria-hidden="true">Repost</span>', html)
        self.assertNotIn('<span aria-hidden="true">Like</span>', html)

    def test_manifest_has_core_app_shortcuts(self):
        manifest_path = Path(__file__).resolve().parents[1] / "static" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        shortcuts = {shortcut["name"]: shortcut["url"] for shortcut in manifest["shortcuts"]}

        self.assertEqual(shortcuts["Home"], "/")
        self.assertEqual(shortcuts["Reels"], "/reels")
        self.assertEqual(shortcuts["Messages"], "/messages")
        self.assertEqual(shortcuts["Notifications"], "/notifications")
        self.assertEqual(shortcuts["Profile"], "/profile")

    def test_search_discovery_context_uses_ranked_people_and_recent_posts(self):
        viewer = {"id": 7}
        popular = [{"id": 8, "username": "ranked", "display_name": "Ranked User"}]
        recent = [self.sample_post(12, 8, "ranked", "recent")]

        with patch.object(zapp, "get_popular_users", return_value=popular) as popular_users, \
             patch.object(zapp, "get_recent_posts", return_value=recent) as recent_posts:
            context = zapp.get_search_discovery_context(viewer, people_limit=4, posts_limit=3)

        popular_users.assert_called_once_with(7, 4)
        recent_posts.assert_called_once_with(7, 3)
        self.assertEqual(context["suggested_users"], popular)
        self.assertEqual(context["recent_posts"], recent)

    def test_setup_health_page_renders_safe_project_checks(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        checks = [
            {"label": "Supabase connection", "status": "ready", "detail": "Client configured."},
            {"label": "Reels table", "status": "ready", "detail": "The reels table is queryable."},
            {"label": "PWA manifest", "status": "ready", "detail": "Manifest file exists."},
        ]
        with patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "get_setup_health", return_value=checks), \
             patch.object(zapp, "get_community_highlights", return_value=[]):
            html = self.client.get("/setup-health").data.decode()

        self.assertIn("Setup Health", html)
        self.assertIn("Supabase connection", html)
        self.assertIn("Reels table", html)
        self.assertIn("PWA manifest", html)

    def test_activity_template_groups_recent_user_history(self):
        viewer = {"id": 7, "username": "demo", "display_name": "Demo User", "profile_photo_url": ""}
        with zapp.app.test_request_context("/activity"):
            html = zapp.render_template(
                "activity.html",
                viewer=viewer,
                highlights=[],
                activity_items=[
                    zapp.activity_item("post", "Post", "Shared a status", "2026-06-01T12:00:00", "/post/1", "📝"),
                    zapp.activity_item("like", "Like", "You liked a post.", "2026-06-01T11:00:00", "/post/2", "👍"),
                ],
            )

        self.assertIn("Activity", html)
        self.assertIn("Shared a status", html)
        self.assertIn("You liked a post.", html)
        self.assertIn('class="activity-row"', html)

    def test_notification_stacking_creates_short_grouped_items(self):
        notifications = [
            {"type": "like", "post_id": 5, "actor_name": "Ada", "is_read": False},
            {"type": "like", "post_id": 5, "actor_name": "Sam", "is_read": True},
            {"type": "comment", "post_id": 5, "actor_name": "Mina", "is_read": False},
        ]

        stacked = zapp.stack_notifications(notifications)

        self.assertEqual(len(stacked), 2)
        like_item = next(item for item in stacked if item["type"] == "like")
        self.assertEqual(like_item["stack_count"], 2)
        self.assertEqual(like_item["actor_summary"], "Ada and Sam")
        self.assertFalse(like_item["is_read"])

    def test_notification_stacking_uses_reel_id_for_reel_events(self):
        notifications = [
            {"type": "reel_like", "reel_id": 9, "actor_name": "Ada", "is_read": False},
            {"type": "reel_like", "reel_id": 9, "actor_name": "Sam", "is_read": True},
            {"type": "reel_like", "reel_id": 10, "actor_name": "Mina", "is_read": False},
        ]

        stacked = zapp.stack_notifications(notifications)

        self.assertEqual(len(stacked), 2)
        reel_9 = next(item for item in stacked if item["reel_id"] == 9)
        self.assertEqual(reel_9["stack_count"], 2)
        self.assertEqual(reel_9["actor_summary"], "Ada and Sam")

    def test_profile_stats_are_ordered_without_duplicate_metric_card(self):
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

        stats_pos = html.index('class="profile-stats"')
        posts_pos = html.index('list_type=\'posts\'') if "list_type='posts'" in html else html.index('/profile/demo?m=posts')
        following_pos = html.index('/profile/demo/following')
        followers_pos = html.index('/profile/demo/followers')
        friends_pos = html.index('/profile/demo/friends')
        self.assertLess(posts_pos, following_pos)
        self.assertLess(following_pos, followers_pos)
        self.assertLess(followers_pos, friends_pos)
        self.assertGreater(posts_pos, stats_pos)
        self.assertNotIn('profile-account-card', html)
        self.assertIn('/profile/demo/following', html)
        self.assertIn('/profile/demo/followers', html)
        self.assertIn('/profile/demo/friends', html)
        self.assertIn("Achievements", html)
        self.assertIn("First Post", html)
        self.assertIn('href="/activity"', html)
        self.assertIn(">Activity</a>", html)
        self.assertIn('href="/settings"', html)
        self.assertIn(">Settings</a>", html)
        self.assertIn('href="/level-guide"', html)
        self.assertIn(">LvL Guide</a>", html)

    def test_other_profile_has_high_five_action(self):
        viewer = {
            "id": 7,
            "username": "viewer",
            "display_name": "Viewer",
            "profile_photo_url": "",
            "level": 1,
        }
        profile = {
            "id": 8,
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
                viewer=viewer,
                profile=profile,
                is_own_profile=False,
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
                achievements=[],
            )

        self.assertIn('class="profile-high-five-form"', html)
        self.assertIn('/profile/demo/high-five', html)
        self.assertIn('aria-label="High-five Demo User"', html)
        self.assertIn("Friendship starts with a streak", html)
        self.assertNotIn("Add friend", html)

    def test_mobile_profile_actions_use_stable_grid(self):
        css = Path("static/css/sections/profile-mobile.css").read_text()

        self.assertIn("@media (max-width: 420px)", css)
        self.assertIn(".profile-actions:has(.profile-high-five-form)", css)
        self.assertIn("display: grid", css)
        self.assertIn("grid-template-areas:", css)
        self.assertIn('"highfive follow message"', css)
        self.assertIn('"mute mute block"', css)
        self.assertIn('.profile-actions .ajax-action-form[data-action="follow"]', css)
        self.assertIn('.profile-actions .ajax-action-form[data-action="mute"]', css)
        self.assertIn('.profile-actions .ajax-action-form[data-action="block"]', css)
        self.assertIn("width: 100%", css)

    def test_profile_action_buttons_use_shared_control_shape(self):
        css = Path("static/css/sections/profile.css").read_text()

        self.assertIn(".profile-actions form", css)
        self.assertIn(".profile-actions .outline-button", css)
        self.assertIn("display: inline-flex", css)
        self.assertIn("min-height: var(--control-lg)", css)
        self.assertIn("align-items: center", css)
        self.assertIn("justify-content: center", css)
        self.assertIn("border-radius: var(--radius-lg)", css)

    def test_relative_time_helper_formats_short_units(self):
        self.assertEqual(zapp.relative_time(None), "")
        self.assertEqual(zapp.relative_time("not-a-date"), "")

        now = zapp.datetime(2026, 6, 1, 12, 0, 0)
        self.assertEqual(zapp.relative_time("2026-06-01T11:59:30", now=now), "30s")
        self.assertEqual(zapp.relative_time("2026-06-01T11:42:00", now=now), "18m")
        self.assertEqual(zapp.relative_time("2026-06-01T08:00:00", now=now), "4h")
        self.assertEqual(zapp.relative_time("2026-05-30T12:00:00", now=now), "2d")
        self.assertEqual(zapp.relative_time("2026-04-01T12:00:00", now=now), "2mo")
        self.assertEqual(zapp.relative_time("2025-04-01T12:00:00", now=now), "1y")

    def test_high_five_route_is_registered(self):
        routes = {rule.rule for rule in zapp.app.url_map.iter_rules()}

        self.assertIn("/profile/<username>/high-five", routes)

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

    def test_create_post_suppresses_rapid_duplicate_text(self):
        fake_user = {"id": 7, "username": "demo", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=fake_user), \
             patch.object(zapp, "interaction_blocked", return_value=False), \
             patch.object(zapp, "recent_duplicate_submission", return_value=True), \
             patch.object(zapp, "supabase") as fake_supabase:
            response = self.client.post("/create_post", data={"csrf_token": self.csrf(), "content": "same"})

        self.assertEqual(response.status_code, 302)
        fake_supabase.table.assert_not_called()

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

    def test_send_message_suppresses_rapid_duplicate_ajax(self):
        fake_user = {"id": 7, "username": "demo", "profile_photo_url": ""}
        with patch.object(zapp, "get_current_user", return_value=fake_user), \
             patch.object(zapp, "interaction_blocked", return_value=False), \
             patch.object(zapp, "recent_duplicate_submission", return_value=True), \
             patch.object(zapp, "supabase") as fake_supabase:
            response = self.client.post("/send_message", data={
                "csrf_token": self.csrf(),
                "receiver_id": "8",
                "content": "hello",
                "ajax": "1",
            })

        self.assertEqual(response.status_code, 409)
        self.assertIn(b"Already sent.", response.data)
        fake_supabase.table.assert_not_called()

    def test_share_post_blocks_safety_hidden_recipients(self):
        class Result:
            def __init__(self, data=None):
                self.data = data or []

        class FakeTable:
            def __init__(self, db, name):
                self.db = db
                self.name = name
                self.action = None
                self.payload = None

            def select(self, *_args, **_kwargs):
                self.action = "select"
                return self

            def insert(self, payload):
                self.action = "insert"
                self.payload = payload
                return self

            def neq(self, *_args):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def range(self, *_args):
                return self

            def execute(self):
                if self.name == "messages" and self.action == "insert":
                    self.db.message_payloads.append(self.payload)
                    return Result([{"id": 1}])
                if self.name == "users":
                    return Result([
                        {"id": 8, "username": "blocked", "display_name": "Blocked User"},
                        {"id": 9, "username": "open", "display_name": "Open User"},
                    ])
                return Result()

        class FakeSupabase:
            def __init__(self):
                self.message_payloads = []

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}

        with zapp.app.test_request_context("/share_post/42", method="POST", data={"target_user_id": "8"}), \
             patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "supabase", fake), \
             patch.object(zapp, "interaction_blocked", side_effect=lambda _viewer_id, target_id: target_id == 8):
            response = zapp.share_post(42)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(fake.message_payloads, [])

        rendered = {}
        with zapp.app.test_request_context("/share_post/42"), \
             patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "supabase", fake), \
             patch.object(zapp, "filter_blocked_users", return_value=[{"id": 9, "username": "open", "display_name": "Open User"}]) as filter_users, \
             patch.object(zapp, "render_template", side_effect=lambda _template, **context: rendered.update(context) or "OK"):
            self.assertEqual(zapp.share_post(42), "OK")

        filter_users.assert_called_once()
        self.assertEqual([user["id"] for user in rendered["users"]], [9])

    def test_onboarding_skips_blocked_follow_ids(self):
        class Result:
            def __init__(self, data=None):
                self.data = data or []

        class FakeTable:
            def __init__(self, db, name):
                self.db = db
                self.name = name
                self.action = None
                self.payload = None

            def select(self, *_args, **_kwargs):
                self.action = "select"
                return self

            def update(self, payload):
                self.action = "update"
                self.payload = payload
                return self

            def insert(self, payload):
                self.action = "insert"
                self.payload = payload
                return self

            def eq(self, key, value):
                self.db.filters.append((self.name, key, value))
                return self

            def execute(self):
                if self.name == "follows" and self.action == "insert":
                    self.db.follow_payloads.append(self.payload)
                return Result()

        class FakeSupabase:
            def __init__(self):
                self.filters = []
                self.follow_payloads = []

            def table(self, name):
                return FakeTable(self, name)

        fake = FakeSupabase()
        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}

        with zapp.app.test_request_context("/onboarding", method="POST", data={"follow_ids": ["8", "9"]}), \
             patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "supabase", fake), \
             patch.object(zapp, "interaction_blocked", side_effect=lambda _viewer_id, target_id: target_id == 8):
            response = zapp.onboarding()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(fake.follow_payloads, [{"follower_id": 7, "following_id": 9}])

    def test_blocked_profile_hides_stats_and_activity(self):
        class Result:
            def __init__(self, data=None, count=0):
                self.data = data or []
                self.count = count

        class FakeTable:
            def __init__(self, name):
                self.name = name

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args):
                return self

            def is_(self, *_args):
                return self

            def execute(self):
                if self.name == "users":
                    return Result([{
                        "id": 8,
                        "username": "blocked",
                        "display_name": "Blocked User",
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
                    }])
                return Result(count=99)

        class FakeSupabase:
            def table(self, name):
                return FakeTable(name)

        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}
        rendered = {}

        with zapp.app.test_request_context("/profile/blocked"), \
             patch.object(zapp, "get_current_user", return_value=viewer), \
             patch.object(zapp, "supabase", FakeSupabase()), \
             patch.object(zapp, "get_user_safety_state", return_value={"blocked": False, "muted": False, "blocked_by": True, "interaction_blocked": True}), \
             patch.object(zapp, "get_profile_posts", return_value=[self.sample_post()]), \
             patch.object(zapp, "get_pair_streak_status", return_value={"count": 0, "is_friend": False, "days_until_friend": 7}), \
             patch.object(zapp, "get_streak_friend_ids", return_value=({}, [1, 2])), \
             patch.object(zapp, "get_community_highlights", return_value=[]), \
             patch.object(zapp, "render_template", side_effect=lambda _template, **context: rendered.update(context) or "OK"):
            self.assertEqual(zapp.profile("blocked"), "OK")

        self.assertEqual(rendered["posts"], [])
        self.assertEqual(rendered["stats"], {"following": 0, "followers": 0, "friends": 0, "posts": 0, "comments": 0})

    def test_community_members_filters_blocked_users(self):
        class Result:
            def __init__(self, data=None):
                self.data = data or []

        class FakeTable:
            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, *_args):
                return self

            def execute(self):
                return Result([
                    {"user_id": 8, "user": {"id": 8, "username": "blocked"}},
                    {"user_id": 9, "user": {"id": 9, "username": "open"}},
                ])

        with patch.object(zapp, "supabase", SimpleNamespace(table=lambda _name: FakeTable())), \
             patch.object(zapp, "blocked_user_ids_for_viewer", return_value={8}):
            members = zapp.get_community_members(1, viewer_id=7)

        self.assertEqual([member["user"]["id"] for member in members], [9])

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

    def test_messages_empty_state_restores_discovery_content(self):
        viewer = {"id": 7, "username": "viewer", "display_name": "Viewer", "profile_photo_url": ""}
        with zapp.app.test_request_context("/messages"):
            html = zapp.render_template(
                "messages.html",
                viewer=viewer,
                target_username=None,
                target_user=None,
                conversations=[],
                all_users=[{
                    "id": 8,
                    "username": "demo",
                    "display_name": "Demo User",
                    "profile_photo_url": "",
                }],
                messages_list=[],
                suggested_communities=[{
                    "name": "Design",
                    "slug": "design",
                    "description": "Creative posts.",
                    "accent_color": "#1D9BF0",
                }],
                message_trending_posts=[],
                message_people=[{
                    "id": 9,
                    "username": "friend",
                    "display_name": "Friend User",
                    "profile_photo_url": "",
                }],
            )

        self.assertIn('class="chat-unselected"', html)
        self.assertIn('class="message-discovery-grid"', html)
        self.assertIn("Suggested groups", html)
        self.assertIn("People to message", html)
        self.assertIn("Start a new conversation", html)
        self.assertIn("/messages?u=demo", html)

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
