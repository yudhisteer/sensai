table_schema = {
    "table_name": "temperature_readings",
    "table_schema": """
        {
    "table_name": "temperature_readings",
    "schema": [
        {
        "column_name": "id",
        "data_type": "uuid",
        "is_nullable": "NO",
        "column_default": "uuid_generate_v4()"
        },
        {
        "column_name": "celsius",
        "data_type": "numeric",
        "is_nullable": "NO",
        "column_default": null
        },
        {
        "column_name": "fahrenheit",
        "data_type": "numeric",
        "is_nullable": "NO",
        "column_default": null
        },
        {
        "column_name": "created_at",
        "data_type": "timestamp with time zone",
        "is_nullable": "YES",
        "column_default": "now()"
        }
    ]
    }
    """,
}