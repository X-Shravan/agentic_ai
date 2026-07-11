"""Supabase client factory."""
import os
from supabase import create_client

def get_supabase_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
