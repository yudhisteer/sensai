from config.config import SUPABASE_KEY, SUPABASE_URL
from supabase import Client, create_client
from supabase.client import ClientOptions


class SupabaseClientManager:
    """Manages the Supabase client instance."""

    def __init__(self):
        self.supabase_config = {
            "supabase_url": SUPABASE_URL,
            "supabase_key": SUPABASE_KEY,
        }
        self.client: Client = create_client(
            **self.supabase_config,
            options=ClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=10,
                schema="public",
            ),
        )

    def get_client(self) -> Client:
        """Returns the Supabase client instance."""
        return self.client
