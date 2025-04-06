from pydantic import BaseModel, field_validator
import sqlparse

class SQLQueryModel(BaseModel):
    query: str

    @field_validator("query")
    def validate_sql_query(cls, value: str) -> str:
        # Remove leading/trailing whitespace
        value = value.strip()

        # Basic check: ensure query isn't empty
        if not value:
            raise ValueError("SQL query cannot be empty")

        # Use sqlparse to check if the query is syntactically valid
        try:
            parsed = sqlparse.parse(value)
            if not parsed:
                raise ValueError("Invalid SQL query: unable to parse")
            
            # Optional: Check for specific keywords you want to disallow
            query_upper = value.upper()
            forbidden_keywords = ["DROP", "DELETE", "TRUNCATE"]
            for keyword in forbidden_keywords:
                if keyword in query_upper:
                    raise ValueError(f"SQL query contains forbidden keyword: {keyword}")

        except Exception as e:
            raise ValueError(f"Invalid SQL query: {str(e)}")

        return value


if __name__ == "__main__":
    # Valid query
    try:
        valid_query = SQLQueryModel(query="SELECT * FROM users WHERE age > 18")
        print("Valid query:", valid_query.query)
    except ValueError as e:
        print("Error:", e)

    # Invalid query
    try:
        invalid_query = SQLQueryModel(query="SELECT * FROM WHERE DROP TABLE users")
        print("Valid query:", invalid_query.query)
    except ValueError as e:
        print("Error:", e)