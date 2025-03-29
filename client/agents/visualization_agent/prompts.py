GRAPHING_SYSTEM_PROMPT = """
If the user asks to plot a line graph, call the `plot_line_graph_agent` tool which you have access to.
"""



# Note it is not a good idea to use context_variables to inject the data as the data is converted into a string of List[Dict[str, str]]
# Furthermore, the llm changes the format of the data (from single quote to double quote) and is inconsistent
# But most importantly, if we are passing a huge amount of data, we will reach the context window limit
# Plus we make risk the llm modifying the data by hallucinating - too much risk and challenge
# Instead we will call a function to get the data directly
# def visualization_system_prompt(context_variables: dict) -> str:
#     return f"""
#     You are a helpful assistant that can help with graphing data. You have tools which you can execute: plot_line_graph, plot_bar_graph, plot_pie_chart to plot the data.
#     When using these tools, choose an appropriate title, x-axis label, y-axis label, and secondary y-axis label (if needed).
#     The data is available in the context variables under the key 'data'.
#     The data is:
#     {context_variables.get("data", None)}
#     Do NOT change the data, just use it as is.
#     """