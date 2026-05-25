import os
from supabase import create_client

url = "https://ivhshtfrfdrgbpzgemwj.supabase.co"
key = "sb_publishable_WEsYK_4zOEZ-OvuKtPDOCA_UR8x3-l9"
supabase = create_client(url, key)

try:
    print("Testing posts query...")
    res = supabase.table('posts').select('*, user:users(*)').limit(1).execute()
    print("Success:", res.data)
except Exception as e:
    print("Error querying posts:", str(e))

try:
    print("Testing users query...")
    res = supabase.table('users').select('*').limit(1).execute()
    print("Success:", res.data)
except Exception as e:
    print("Error querying users:", str(e))
