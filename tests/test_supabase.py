import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_SECRET", os.getenv("SUPABASE_KEY", ""))

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_SECRET must be set in .env or environment.")
    exit(1)

supabase = create_client(url, key)

try:
    print("Testing posts query...")
    res = supabase.table('posts').select('*, user:users!posts_user_id_fkey(*)').limit(1).execute()
    print("Success:", res.data)
except Exception as e:
    print("Error querying posts:", str(e))

try:
    print("Testing users query...")
    res = supabase.table('users').select('*').limit(1).execute()
    print("Success:", res.data)
except Exception as e:
    print("Error querying users:", str(e))
