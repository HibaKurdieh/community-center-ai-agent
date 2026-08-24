import os

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")

    if not url:
        raise RuntimeError("SUPABASE_URL is missing from .env")

    if not secret_key:
        raise RuntimeError("SUPABASE_SECRET_KEY is missing from .env")

    return create_client(url, secret_key)