import json
from typing import List, Union

from openai.types.chat import ChatCompletionMessageToolCall

from client.agents.common.base import Agent, FuncResult
from client.agents.common.types import AgentFunction, TaskResponse
from shared.utils import debug_print


class ToolCallHandler:

    @staticmethod
    def __handle_function_result(result) -> FuncResult:
        if isinstance(result, FuncResult):
            return result

        if isinstance(result, Agent):
            agent: Agent = result
            return FuncResult(
                value=json.dumps({"assistant": agent.name}),
                agent=agent,
            )

        try:
            return FuncResult(value=str(result))
        except Exception as e:
            error_message = f"Failed to cast response to string: {result}. Make sure agent functions return a string or Result object. Error: {str(e)}"
            debug_print(error_message)
            raise TypeError(error_message)

    def handle_tool_calls(
        self,
        tool_calls: List[Union[ChatCompletionMessageToolCall, dict]],
        functions: List[AgentFunction],
    ) -> TaskResponse:
        functions_map = {f.__name__: f for f in functions}
        partial_response = TaskResponse(messages=[], agent=None, context_variables={})
        if not tool_calls:
            return partial_response
        for tool_call in tool_calls:
            self.__handle_call(tool_call, functions_map, partial_response)
        return partial_response

    def __handle_call(
        self,
        tool_call: Union[ChatCompletionMessageToolCall, dict],
        function_map: dict,
        partial_response: TaskResponse,
    ):
        # Handle both dict and object cases
        if isinstance(tool_call, dict):
            name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            call_id = tool_call["id"]
        else:
            name = tool_call.function.name
            arguments = tool_call.function.arguments
            call_id = tool_call.id

        if name not in function_map:
            debug_print(f"Function {name} not found in function map")
            partial_response.messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "tool_call_id": call_id,
                    "content": f"Error: tool {name} not found",
                }
            )
            return
        
        raw_result = self.__execute_tool(function_map, name, arguments)
        result = self.__handle_function_result(raw_result)
        partial_response.messages.append(
            {
                "role": "tool",
                "tool_name": name,
                "tool_call_id": call_id,
                "content": result.value,
            }
        )
        if result.agent:
            partial_response.agent = result.agent

    @staticmethod
    def __execute_tool(function_map, name, arguments):
        args = json.loads(arguments)
        debug_print(f"Executing tool {name} with args {args}")
        return function_map[name](**args)