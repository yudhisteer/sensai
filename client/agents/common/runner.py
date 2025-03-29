import copy
import json
from collections import defaultdict

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from client.agents.common.base import Agent
from client.agents.common.result_handler import ToolCallHandler
from client.agents.common.types import TaskResponse
from shared.utils import debug_print


class AppRunner:
    def __init__(self, client: OpenAI):
        self.client = client
        self.tool_handler = ToolCallHandler()

    def run(
        self, agent: Agent, messages: list, variables: dict, max_interactions=10
    ) -> TaskResponse:
        loop_count = 0
        active_agent = agent
        context_variables = copy.deepcopy(variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)
        parsed_response = None

        while loop_count < max_interactions:
            debug_print(f"Active agent: {active_agent.name}")
            llm_params = self.__create_inference_request(
                active_agent, 
                history, 
                context_variables
            )
            # Check if the agent has a response_format
            if active_agent.response_format:
                llm_params["response_format"] = active_agent.response_format
                response = self.client.beta.chat.completions.parse(**llm_params)
                message = response.choices[0].message.parsed
                parsed_response = message

                history_msg = {
                    "content": str(message),
                    "sender": active_agent.name,
                    "role": "assistant"
                }
                history.append(history_msg)

                # Check for and use response_handler
                if active_agent.response_handler:
                    next_agent = active_agent.response_handler(parsed_response)
                    if next_agent:
                        debug_print(f"Switching to agent: {next_agent.name}")
                        active_agent = next_agent
                        continue  # Continue with the new agent
                break  # No handler or handler returned None, so stop
                # For parsed responses, we always break since they don't use tool_calls
            else:
                response = self.client.chat.completions.create(**llm_params)
                message: ChatCompletionMessage = response.choices[0].message
                # debug_print("Response from OpenAI:", str(response))
                history_msg = json.loads(message.model_dump_json())
                history_msg["sender"] = active_agent.name
                history.append(history_msg)
                loop_count += 1
                if not message.tool_calls:
                    debug_print("No tool calls found in the response")
                    break
            debug_print("Tool calls:", message.tool_calls)
            response = self.tool_handler.handle_tool_calls(
                message.tool_calls,
                active_agent.functions,
            )
            debug_print("Response from tool handler:", str(response))
            history.extend(response.messages)
            if response.agent:
                debug_print(f"Switching to agent: {response.agent.name}")
                active_agent = response.agent
            

        return TaskResponse(
            messages=history[init_len:],
            agent=active_agent,
            context_variables=context_variables,
            parsed_response=parsed_response
        )

    @staticmethod
    def __create_inference_request(
        agent: Agent, history: list, variables: dict
    ) -> dict:
        context_variables = defaultdict(str, variables)
        instructions = agent.get_instructions(context_variables)
        messages = [{"role": "system", "content": instructions}] + history
        tools = agent.tools_in_json()
        # debug_print("Getting chat completion for...:", str(messages))

        params = {
            "model": agent.model,
            "messages": messages,
            "tool_choice": agent.tool_choice,
        }
        if tools:
            params["parallel_tool_calls"] = agent.parallel_tool_calls
            params["tools"] = tools

        return params