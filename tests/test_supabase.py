import os
import unittest

from dotenv import load_dotenv
from supabase import create_client


@unittest.skipUnless(os.getenv("RUN_SUPABASE_SMOKE") == "1", "Set RUN_SUPABASE_SMOKE=1 to run live Supabase smoke checks.")
class SupabaseSmokeTests(unittest.TestCase):
    def test_posts_and_users_queries_return_lists(self):
        load_dotenv()

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SECRET", os.getenv("SUPABASE_KEY", ""))
        self.assertTrue(url, "SUPABASE_URL must be set.")
        self.assertTrue(key, "SUPABASE_SECRET or SUPABASE_KEY must be set.")

        supabase = create_client(url, key)

        posts = supabase.table("posts").select("id,content,user:users!posts_user_id_fkey(id,username,display_name)").limit(1).execute().data
        users = supabase.table("users").select("id,username,display_name").limit(1).execute().data

        self.assertIsInstance(posts, list)
        self.assertIsInstance(users, list)


if __name__ == "__main__":
    unittest.main()
