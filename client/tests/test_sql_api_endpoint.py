from client.agents.sql_agent.tools import execute_sql_query

if __name__ == "__main__":
    sql_query = "SELECT * FROM temperature_readings"
    response = execute_sql_query(sql_query, "http://127.0.0.1:8000/temperature/sql")
    print(response)
