from client.agents.sql_agent.tools import execute_sql_query, retrieve_data_from_temp_file



if __name__ == "__main__":

    sql_query = "SELECT AVG(celsius) AS avg_celsius, AVG(fahrenheit) AS avg_fahrenheit FROM temperature_readings"
    ENDPOINT_URL = "http://127.0.0.1:8000/temperature/sql"

    data_ref_file_path = execute_sql_query(sql_query=sql_query, 
                                           ENDPOINT_URL=ENDPOINT_URL)
    print("Data reference: ", data_ref_file_path)
    print("-" * 100)
    data = retrieve_data_from_temp_file(data_ref_file_path)
    print("Data: ", data)
