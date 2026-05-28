import json
import asyncio
from datetime import datetime
from src.ai.deepseek_client import chat_completion
from src.ai.prompts import AGENT_PROMPTS
from src.utils.logger import logger
from src.data.data_store import data_store
from src.ai.memory_agent import memory_agent
from src.utils.vector_store import vector_store

class BaseAgent:
    def __init__(self, name, display_name, icon):
        self.name = name
        self.display_name = display_name
        self.icon = icon
        self.system_prompt = AGENT_PROMPTS.get(name, '')
        self.tool_definitions = []  # OpenAI JSON schemas for tools
        self.tools = {}             # Callable mappings for execution
        self.use_reasoning = False

    def get_history(self, session_id):
        return data_store.get_agent_history(session_id, self.name)

    def add_message_to_history(self, session_id, message_obj):
        history = self.get_history(session_id)
        history.append(message_obj)
        # Keep last 40 to accommodate tool-call conversation steps
        if len(history) > 40:
            history = history[-40:]
        data_store.save_agent_history(session_id, self.name, history)

    async def build_messages(self, session_id, user_message, context_data='', params=None):
        if params is None:
            params = {}
            
        history = self.get_history(session_id)
        user_id = params.get("userId")
        
        vector_memories = {"episodic": [], "semantic": []}
        if user_id:
            try:
                vector_memories = await vector_store.search_memory(user_id, user_message, 5)
            except Exception as e:
                logger.error(f"Vector memory query failed: {str(e)}")

        episodic_list = vector_memories.get("episodic", [])
        episodic_str = ""
        if episodic_list:
            items = "\n".join(f"- {doc}" for doc in episodic_list if doc)
            episodic_str = f"\nRELEVANT PAST CONVERSATIONS / EVENTS:\n{items}\n"

        semantic_list = vector_memories.get("semantic", [])
        semantic_str = ""
        if semantic_list:
            items = "\n".join(f"- {doc}" for doc in semantic_list if doc)
            semantic_str = f"\nRELEVANT PROFILE / FINANCIAL FACTS:\n{items}\n"

        legacy_memories = memory_agent.get_relevant_memories(user_id, user_message) if user_id else []
        legacy_str = ""
        if legacy_memories:
            items = "\n".join(f"[{m['timestamp'].split('T')[0]}] {'User' if m['role'] == 'user' else 'Agent'}: {m['content']}" for m in legacy_memories)
            legacy_str = f"\nRECENT MESSAGE CONTEXT:\n{items}\n"

        memory_context = f"{episodic_str}{semantic_str}{legacy_str}"
        current_date = datetime.utcnow().strftime("%Y-%m-%d")
        system_content = f"{self.system_prompt}\n\n--- CURRENT CONTEXT DATA ---\n{context_data}{memory_context}\nCurrent Date: {current_date}"

        # Add user message to working memory
        if user_id:
            await memory_agent.add_memory(user_id, 'user', user_message)

        # Update or insert system prompt at history[0]
        if not history or history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system_content})
        else:
            history[0]["content"] = system_content

        data_store.save_agent_history(session_id, self.name, history)
        return history + [{"role": "user", "content": user_message}]

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}
            
        logger.info(f"Processing request in base agent", {"agent": self.name})
        
        # Ensure session exists
        session = data_store.get_session(session_id)
        if not session:
            logger.info(f"Session {session_id} not found. Creating on the fly.", {"agent": self.name})
            data_store.create_session(id_val=session_id, user_id=params.get("userId", ""))

        messages = await self.build_messages(session_id, user_message, context_data, params)
        self.add_message_to_history(session_id, {"role": "user", "content": user_message})

        requires_approval = False
        approval_id = None
        iterations = 0
        max_iterations = 5

        while iterations < max_iterations:
            iterations += 1
            
            history_list = self.get_history(session_id)
            if not history_list:
                logger.warn(f"history_list is empty for agent {self.name} in session {session_id}. Falling back to build_messages.", {"agent": self.name})
                history_list = messages

            response = await chat_completion(history_list, {
                "agentName": self.name,
                "tools": self.tool_definitions if self.tool_definitions else None,
                "useReasoning": self.use_reasoning
            })

            # Append LLM output (assistant role or structure) to cache history
            if response.get("messageObj"):
                # Handle raw openai message class translation or dictionary
                msg_obj = response["messageObj"]
                if not isinstance(msg_obj, dict):
                    # Convert to JSON serializable dictionary
                    tool_calls_serialized = None
                    if getattr(msg_obj, "tool_calls", None):
                        tool_calls_serialized = [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in msg_obj.tool_calls
                        ]
                    msg_dict = {
                        "role": msg_obj.role or "assistant",
                        "content": msg_obj.content or "",
                    }
                    if tool_calls_serialized:
                        msg_dict["tool_calls"] = tool_calls_serialized
                    self.add_message_to_history(session_id, msg_dict)
                else:
                    self.add_message_to_history(session_id, msg_obj)
            else:
                self.add_message_to_history(session_id, {"role": "assistant", "content": response.get("content", "")})

            # Emit live trace event
            data_store.emit('agent:trace', {
                "agent": self.name,
                "reasoning": response.get("reasoning", ""),
                "content": response.get("content", ""),
                "toolCalls": [
                    {"name": tc["function"]["name"], "args": tc["function"]["arguments"]}
                    for tc in response.get("toolCalls", [])
                ] if response.get("toolCalls") else [],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })

            tool_calls = response.get("toolCalls")
            if tool_calls and len(tool_calls) > 0:
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    raw_args = tc["function"].get("arguments", "{}")
                    try:
                        fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        fn_args = {}

                    logger.info(f"Agent executing tool: {fn_name}", {"agent": self.name, "args": fn_args})
                    
                    result = ""
                    try:
                        if fn_name in self.tools:
                            tool_params = {**fn_args, **params}
                            
                            # Invoke tool
                            tool_result = self.tools[fn_name](**tool_params)
                            if asyncio.iscoroutine(tool_result):
                                tool_result = await tool_result

                            if isinstance(tool_result, dict) and tool_result.get("requiresApproval"):
                                requires_approval = True
                                approval_id = tool_result.get("approvalId")

                            if isinstance(tool_result, (dict, list)):
                                result = json.dumps(tool_result)
                            else:
                                result = str(tool_result)
                        else:
                            result = f"Error: Tool {fn_name} not found"
                            logger.warn(result, {"agent": self.name})
                    except Exception as e:
                        result = f"Error executing {fn_name}: {str(e)}"
                        logger.error(result, {"agent": self.name})

                    # Record tool call output
                    self.add_message_to_history(session_id, {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })

                    # Emit trace for tool output
                    data_store.emit('agent:trace', {
                        "agent": self.name,
                        "toolResult": {"name": fn_name, "result": result},
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
            else:
                # Loop ends, store final agent content to memories
                user_id = params.get("userId")
                if user_id and response.get("content"):
                    await memory_agent.add_memory(user_id, 'agent', response["content"])

                return {
                    "agent": self.name,
                    "displayName": self.display_name,
                    "icon": self.icon,
                    "content": response.get("content", ""),
                    "requiresApproval": requires_approval,
                    "approvalId": approval_id,
                    "usage": response.get("usage", {})
                }
        
        return {
            "agent": self.name,
            "displayName": self.display_name,
            "icon": self.icon,
            "content": "I reached the maximum number of iterations while processing your request. Please try rephrasing.",
            "requiresApproval": requires_approval,
            "approvalId": approval_id,
            "usage": {}
        }

    def clear_history(self, session_id):
        data_store.save_agent_history(session_id, self.name, [])
