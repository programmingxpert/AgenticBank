import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        # Deepseek API
        self.deepseek = {
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "reasoning_model": os.getenv("DEEPSEEK_REASONING_MODEL", "deepseek-v4-pro"),
            "temperature": float(os.getenv("AGENT_TEMPERATURE", "0.3")),
            "max_tokens": int(os.getenv("AGENT_MAX_TOKENS", "2048")),
        }
        
        # Server
        self.server = {
            "port": int(os.getenv("PORT", "3000")),
            "env": os.getenv("NODE_ENV", "development"),
        }
        
        # Human-in-the-loop thresholds
        self.approval_thresholds = {
            "transfer": 500000, # ₹5,00,000
            "trade": 100000,    # ₹1,00,000
        }
        
        # Session
        self.session_secret = os.getenv("SESSION_SECRET", "fallback-dev-secret")

config = Config()

def validate_config():
    warnings = []
    errors = []
    
    if not config.deepseek["api_key"] or config.deepseek["api_key"] == "your_deepseek_api_key_here":
        warnings.append("DEEPSEEK_API_KEY is not set. AI agents will return simulated responses.")
        
    if config.server["env"] == "production" and config.session_secret == "fallback-dev-secret":
        errors.append("SESSION_SECRET must be set in production.")
        
    return warnings, errors, len(errors) == 0
