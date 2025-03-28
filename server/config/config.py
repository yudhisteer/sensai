import os

from decouple import config

PROJECT_NAME = "sensai"
API_DOCS = "/api/docs"

# from .env
OPENAI_API_KEY = config("OPENAI_API_KEY")
OPENAI_API_MODEL = config("OPENAI_API_MODEL")


# PostgreSQL credentials for DDL
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY")