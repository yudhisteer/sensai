import json
from typing import Optional

import psycopg2
from config.config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    SUPABASE_KEY,
    SUPABASE_URL,
)
from db.schemas import TABLE_SCHEMAS
from db.supabase_client import SupabaseClientManager

from shared.logger_setup import get_logger

logger = get_logger(__name__)


class DatabaseSchemaManager:
    """Manages database schema operations."""

    TABLE_SCHEMA_SQL = """
    CREATE OR REPLACE FUNCTION get_table_schema(input_table_name TEXT)
    RETURNS TABLE (
        column_name TEXT, 
        data_type TEXT, 
        is_nullable TEXT, 
        column_default TEXT
    ) AS $$
    BEGIN
        RETURN QUERY 
        SELECT 
            c.column_name::TEXT, 
            c.data_type::TEXT, 
            c.is_nullable::TEXT, 
            c.column_default::TEXT
        FROM 
            information_schema.columns c
        WHERE 
            c.table_schema = 'public'
        AND c.table_name = input_table_name
    ORDER BY 
        c.ordinal_position;
    END;
    $$ LANGUAGE plpgsql;
    """

    def __init__(self):
        self.supabase = SupabaseClientManager().get_client()
        self.connection = None
        self.cursor = None
        self.db_config = {
            "host": DB_HOST,
            "database": DB_NAME,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "port": DB_PORT,
        }
        self.supabase_config = {
            "supabase_url": SUPABASE_URL,
            "supabase_key": SUPABASE_KEY,
        }
        self.create_db_function(self.TABLE_SCHEMA_SQL)

    def get_db_connection(self):
        """Establish a psycopg2 connection for DDL operations."""
        try:
            connection = psycopg2.connect(**self.db_config)
            logger.info("Successfully connected to database")
            return connection
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}", exc_info=True)
            raise

    def create_db_function(self, function_sql: str) -> bool:
        """Creates or replaces a PostgreSQL function."""
        try:
            self.connection = self.get_db_connection()
            self.cursor = self.connection.cursor()
            self.cursor.execute(function_sql)
            self.connection.commit()
            logger.info("Successfully created PostgreSQL function!")
            return True
        except Exception as e:
            logger.error(f"Error creating PostgreSQL function: {e}")
            return False
        finally:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()

    def create_table(self, table_name: str, schema: Optional[str] = None) -> bool:
        """Create a table in Supabase."""
        try:
            if schema is None:
                if table_name not in TABLE_SCHEMAS:
                    logger.error(f"No schema defined for '{table_name}'.")
                    return False
                schema = TABLE_SCHEMAS[table_name]

            self.connection = self.get_db_connection()
            self.cursor = self.connection.cursor()
            self.cursor.execute(schema)

            # Drop existing policies
            for policy in [
                "Allow insert for authenticated users",
                "Allow select for authenticated users",
                "Allow insert for everyone",
                "Allow select for everyone",
            ]:
                self.cursor.execute(
                    f'DROP POLICY IF EXISTS "{policy}" ON {table_name};'
                )

            # Add new policies
            self.cursor.execute(
                f"""
                CREATE POLICY "Allow insert for everyone" ON {table_name}
                FOR INSERT TO public
                WITH CHECK (true);
            """
            )
            self.cursor.execute(
                f"""
                CREATE POLICY "Allow select for everyone" ON {table_name}
                FOR SELECT TO public
                USING (true);
            """
            )
            self.connection.commit()
            logger.info(f"Table '{table_name}' created or already exists.")
            return True
        except Exception as e:
            logger.error(f"Error creating table '{table_name}': {e}")
            return False
        finally:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()

    def get_table_schema(self, table_name: str) -> str:
        """Get the schema for a table in JSON format."""
        try:
            response = self.supabase.rpc(
                "get_table_schema", {"input_table_name": table_name}
            ).execute()
            formatted_data = {"table_name": table_name, "schema": response.data}
            return json.dumps(formatted_data, indent=2)
        except Exception as e:
            logger.error(f"Error retrieving table schema: {e}")
            return None


if __name__ == "__main__":
    manager = DatabaseSchemaManager()
    schema_result = manager.get_table_schema("temperature_readings")
    print(schema_result)
