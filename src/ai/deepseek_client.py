import json
import asyncio
from openai import AsyncOpenAI
from src.config import config
from src.utils.logger import logger

_client = None
_is_configured = False

def get_client():
    global _client, _is_configured
    if not _client:
        api_key = config.deepseek["api_key"]
        if not api_key or api_key == 'your_deepseek_api_key_here':
            _is_configured = False
            logger.warn('Deepseek API key not configured — running in simulation mode', {"agent": "system"})
            return None
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.deepseek["base_url"]
        )
        _is_configured = True
        logger.info(f"Deepseek client initialized: Model={config.deepseek['model']}", {"agent": "system"})
    return _client

async def chat_completion(messages, options=None):
    if options is None:
        options = {}
    
    llm = get_client()
    if not llm:
        return simulate_response(messages, options)

    retry_count = options.get("_retryCount", 0)
    try:
        api_options = {
            "model": options.get("model", config.deepseek["model"]),
            "messages": messages,
            "temperature": options.get("temperature", config.deepseek["temperature"]),
            "max_tokens": options.get("maxTokens", config.deepseek["max_tokens"])
        }

        if "responseFormat" in options:
            # Replicate OpenAI json_object schema
            api_options["response_format"] = options["responseFormat"]
            
        if "tools" in options and len(options["tools"]) > 0:
            api_options["tools"] = options["tools"]
            if "toolChoice" in options:
                api_options["tool_choice"] = options["toolChoice"]

        if options.get("useReasoning"):
            api_options["model"] = config.deepseek["reasoning_model"]
            # Deepseek reasoning specific configuration if supported by the provider, otherwise default to model reasoning config
            # Note: For openrouter / deepseek direct, we adjust headers or extra body if necessary.
            api_options["extra_body"] = {"thinking": {"type": "enabled"}}

        response = await llm.chat.completions.create(**api_options)
        choice = response.choices[0]
        message = choice.message
        
        # Safe extraction of reasoning_content if it exists (e.g. from newer OpenAI packages or custom extra fields)
        reasoning = getattr(message, "reasoning_content", "") or ""
        
        # Transform openai response format to match JS return dictionary
        result = {
            "content": message.content or "",
            "reasoning": reasoning,
            "role": message.role or "assistant",
            "toolCalls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in message.tool_calls
            ] if message.tool_calls else None,
            "messageObj": message,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            } if response.usage else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "finishReason": choice.finish_reason
        }

        logger.debug(f"LLM response received from {options.get('agentName', 'unknown')}: Tokens={result['usage']['total_tokens']}", {"agent": options.get("agentName", "unknown")})
        return result

    except Exception as error:
        logger.error(f"Deepseek API error: {str(error)}", {"agent": options.get("agentName", "unknown")})
        
        # Check for rate limit or server error
        is_rate_limit = False
        if hasattr(error, "status_code") and error.status_code == 429:
            is_rate_limit = True
        elif "429" in str(error) or "rate limit" in str(error).lower():
            is_rate_limit = True

        if is_rate_limit:
            logger.warn(f"Rate limited — waiting 2s and retrying... (retry {retry_count + 1})", {"agent": options.get("agentName")})
            await asyncio.sleep(2.0)
            options["_retryCount"] = retry_count + 1
            return await chat_completion(messages, options)

        if retry_count < 2:
            await asyncio.sleep(1.0)
            options["_retryCount"] = retry_count + 1
            return await chat_completion(messages, options)

        raise error

def simulate_response(messages, options):
    agent_name = options.get("agentName", "orchestrator")
    
    sim_responses = {
        "orchestrator": (
            "I've analyzed your request. Based on your query, I'll route this to the appropriate specialist agent. Let me process this for you.\n\n"
            "**Note:** Running in simulation mode — connect your Deepseek API key for full AI-powered responses."
        ),
        "transaction": (
            "I've reviewed your transaction request. Here's what I found:\n\n"
            "• **Account Status**: Active and in good standing\n"
            "• **Available Balance**: Sufficient for this operation\n"
            "• **Processing Time**: Immediate for internal transfers\n\n"
            "*Simulation mode — connect Deepseek API for real AI analysis.*"
        ),
        "fraud": (
            "🛡️ **Fraud Analysis Report**\n\n"
            "• **Risk Level**: LOW\n"
            "• **Suspicious Indicators**: None detected\n"
            "• **Account Activity**: Within normal parameters\n"
            "• **Recommendation**: No action required\n\n"
            "*Simulation mode — connect Deepseek API for real AI analysis.*"
        ),
        "loan": (
            "📋 **Loan Assessment**\n\n"
            "• **Eligibility**: Pre-qualified\n"
            "• **Estimated Rate**: 6.5% - 8.2% APR\n"
            "• **Credit Score Impact**: Minimal (soft check)\n"
            "• **Required Documents**: Income verification, ID\n\n"
            "*Simulation mode — connect Deepseek API for real AI analysis.*"
        ),
        "customer-service": (
            "I'd be happy to help you with your inquiry. Here's what I can assist with:\n\n"
            "• Account information and statements\n"
            "• Profile updates and preferences\n"
            "• Filing complaints and tracking status\n"
            "• General banking FAQs\n\n"
            "*Simulation mode — connect Deepseek API for real AI analysis.*"
        ),
        "investment": (
            "📈 **Investment Advisory**\n\n"
            "• **Market Outlook**: Cautiously optimistic\n"
            "• **Portfolio Health**: Well-diversified\n"
            "• **Recommendation**: Consider rebalancing quarterly\n"
            "• **Risk Assessment**: Within your stated tolerance\n\n"
            "*Simulation mode — connect Deepseek API for real AI analysis.*"
        ),
        "compliance": (
            "📋 **Compliance Check**\n\n"
            "• **KYC Status**: Verified\n"
            "• **AML Screening**: Clear\n"
            "• **Sanctions Check**: No matches\n"
            "• **Regulatory Status**: Compliant\n\n"
            "*Simulation mode — connect Deepseek API for real AI analysis.*"
        )
    }

    return {
        "content": sim_responses.get(agent_name, sim_responses["orchestrator"]),
        "role": "assistant",
        "usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
        "finishReason": "simulated"
    }

def is_api_configured():
    get_client()
    return _is_configured
