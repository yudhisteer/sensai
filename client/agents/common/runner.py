import copy
import json
from collections import defaultdict
from typing import Dict, List, Optional

import instructor

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.result_handler import ToolCallHandler
from client.agents.common.types import TaskResponse
from shared.utils import debug_print


class AppRunner:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = config.client
        self.tool_handler = ToolCallHandler()
        self.messages: List[Dict] = []  # Persistent message history

    def run(
        self,
        agent: Agent,
        query: str,
        context_variables: Optional[Dict] = None,
    ) -> TaskResponse:
        loop_count = 0
        active_agent = agent
        context_variables = copy.deepcopy(context_variables or {})
        history = copy.deepcopy(self.messages)
        history.append({"role": "user", "content": query})
        init_len = len(history)

        while loop_count < self.config.max_interactions:
            debug_print(f"Active agent: {active_agent.name}")
            llm_params = self.__create_inference_request(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                token_limit=self.config.token_limit,
            )
            # Check if the client is instructor-patched
            is_instructor_client = isinstance(self.client, instructor.client.Instructor)

            # Remove response_model if not using instructor client
            if not is_instructor_client and "response_model" in llm_params:
                del llm_params["response_model"]

            response = self.client.chat.completions.create(**llm_params)

            # if the agent has a response model, we need to parse the response
            if is_instructor_client and active_agent.response_model:
                message_content = response.json()
                history_msg = {
                    "role": "assistant",
                    "content": message_content,
                    "sender": active_agent.name,
                    "tool_calls": None,
                }
            else:
                # response is a ChatCompletion
                message = response.choices[0].message
                history_msg = json.loads(message.model_dump_json())
                history_msg["sender"] = active_agent.name

            history.append(history_msg)
            loop_count += 1

            if not history_msg.get(
                "tool_calls"
            ):  # Fix: Use history_msg instead of message
                debug_print("No tool calls found in the response")
                break

            debug_print("Tool calls:", history_msg["tool_calls"])
            tool_response = self.tool_handler.handle_tool_calls(
                history_msg["tool_calls"],
                active_agent.functions,
            )
            history.extend(tool_response.messages)
            if tool_response.agent:
                debug_print(f"Switching to agent: {tool_response.agent.name}")
                active_agent = tool_response.agent

        return TaskResponse(
            messages=history[init_len:],
            agent=active_agent,
            context_variables=context_variables,
        )

    def __create_inference_request(
        self, agent: Agent, history: list, context_variables: dict, token_limit: int
    ) -> dict:
        context_variables = defaultdict(str, context_variables)
        instructions = agent.get_instructions(context_variables)
        messages = [{"role": "system", "content": instructions}] + history
        tools = agent.tools_in_json()

        params = {
            "model": agent.model,
            "messages": messages,
            "tool_choice": agent.tool_choice,
            "max_tokens": token_limit,
        }
        # Add tools if defined in the agent
        if tools:
            params["parallel_tool_calls"] = agent.parallel_tool_calls
            params["tools"] = tools

        # Add response_model if defined in the agent
        if agent.response_model:
            params["response_model"] = agent.response_model

        return params
