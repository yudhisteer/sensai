# db/schemas.py
from typing import Dict

TABLE_SCHEMAS: Dict[str, str] = {
    "temperature_readings": """
    CREATE TABLE IF NOT EXISTS temperature_readings (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        celsius DECIMAL(5,2) NOT NULL,
        fahrenheit DECIMAL(5,2) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    "humidity_readings": """
    CREATE TABLE IF NOT EXISTS humidity_readings (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        relative_humidity DECIMAL(5,2) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    # Add more schemas here
}
