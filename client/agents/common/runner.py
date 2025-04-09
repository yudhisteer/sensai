import copy
import json
from collections import defaultdict
from typing import Dict, List, Optional

import instructor
from openai import OpenAI

from client.agents.common.base import Agent, AgentConfig, FuncResult
from client.agents.common.result_handler import ToolCallHandler
from client.agents.common.types import TaskResponse
from shared.utils import debug_print


class AppRunner:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.openai_client = OpenAI(api_key=config.api_key)
        self.instructor_client = instructor.from_openai(OpenAI(api_key=config.api_key))
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
        # context_variables = copy.deepcopy(context_variables or {})
        context_variables = context_variables or {}

        history = copy.deepcopy(self.messages)
        history.append({"role": "user", "content": query})
        init_len = len(history)

        while loop_count < self.config.max_interactions:
            print("")
            debug_print(f"-----------LOOP COUNT: {loop_count}-----------")
            debug_print(f"Active agent: {active_agent.name}")
            llm_params = self.__create_inference_request(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                token_limit=self.config.token_limit,
            )

            # Choose client based on agent configuration
            if active_agent.functions and not active_agent.response_model:
                client = self.openai_client  # Use raw OpenAI for tool calls
                if "response_model" in llm_params:
                    del llm_params["response_model"]
            else:
                client = self.instructor_client  # Use instructor for response_model
                if "tools" in llm_params:
                    del llm_params["tools"]
                    del llm_params["parallel_tool_calls"]
                if not active_agent.response_model:
                    llm_params["response_model"] = None

            # Make the API call
            response = client.chat.completions.create(**llm_params)
            debug_print("RESPONSE:", response)
            # debug_print(f"Raw response from {active_agent.name}: {response}")
            # if the agent has a response model, we need to parse the response
            if active_agent.response_model:
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

            # Check for tool calls (if any)
            if history_msg.get("tool_calls"):
                debug_print("Tool calls:", history_msg["tool_calls"])
                tool_response = self.tool_handler.handle_tool_calls(
                    history_msg["tool_calls"],
                    active_agent.functions,
                )
                debug_print("TOOL RESPONSE:", tool_response)
                history.extend(tool_response.messages)
                debug_print("HISTORY:", history)

                if tool_response.context_variables:
                    context_variables.update(tool_response.context_variables)

                if tool_response.agent:
                    debug_print(f"Switching to agent: {tool_response.agent.name}")
                    active_agent = tool_response.agent
                    continue
                continue


            # If no tool calls, check for next_agent
            if active_agent.next_agent:
                # next_agent is a list containing either an Agent or a function
                next_step = active_agent.next_agent[0]  # Get the first (and only) element
                if isinstance(next_step, Agent):
                    next_agent = next_step
                else:
                    # It's a function; call it with history and context_variables
                    result = next_step(context_variables=context_variables, history_msg=history_msg)

                    # Check if the result is an FuncResult or an Agent
                    if isinstance(result, FuncResult):
                        next_agent = result.agent
                        if result.context_variables:
                            context_variables.update(result.context_variables)
                    else:
                        next_agent = result

                if next_agent:
                    debug_print(f"Switching to next agent: {next_agent.name}")
                    active_agent = next_agent
                    continue
                continue

            debug_print("No tool calls or next agent found, ending process")
            break

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
