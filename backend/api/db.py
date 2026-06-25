import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_supabase: Client = None
_supabase_service: Client = None


def get_supabase() -> Client:
    """Supabase 클라이언트 싱글톤 (SELECT용 — anon key)"""
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL, SUPABASE_KEY 환경변수 필요")
        _supabase = create_client(url, key)
    return _supabase


def get_supabase_service() -> Client:
    """Supabase service_role 클라이언트 싱글톤 (INSERT용 — RLS 우회)"""
    global _supabase_service
    if _supabase_service is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 환경변수 필요")
        _supabase_service = create_client(url, key)
    return _supabase_service
