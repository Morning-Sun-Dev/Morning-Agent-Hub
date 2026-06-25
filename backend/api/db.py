import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_supabase: Client = None


def get_supabase() -> Client:
    """Supabase 클라이언트 싱글톤"""
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL, SUPABASE_KEY 환경변수 필요")
        _supabase = create_client(url, key)
    return _supabase
