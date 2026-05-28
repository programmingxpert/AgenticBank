import os
import sys
from datetime import datetime
import json

LEVELS = { "DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3 }
COLORS = {
    "DEBUG": "\x1b[36m",  # Cyan
    "INFO": "\x1b[32m",   # Green
    "WARN": "\x1b[33m",   # Yellow
    "ERROR": "\x1b[31m",  # Red
    "RESET": "\x1b[0m",
    "DIM": "\x1b[2m",
    "BOLD": "\x1b[1m",
}

AGENT_ICONS = {
    "orchestrator": "🧠",
    "transaction": "💸",
    "fraud": "🛡️",
    "loan": "🏦",
    "customer-service": "🎧",
    "investment": "📈",
    "compliance": "📋",
    "system": "⚙️",
    "approval": "✋",
}

class Logger:
    def __init__(self, min_level="DEBUG"):
        self.min_level = LEVELS.get(min_level, 0)
        self.logs = []

    def _format(self, level, message, context=None):
        if context is None:
            context = {}
        timestamp = datetime.utcnow().isoformat() + "Z"
        agent = context.get("agent")
        icon = AGENT_ICONS.get(agent, "🤖") if agent else "📝"
        agent_tag = f" [{agent.upper()}]" if agent else ""
        
        ctx_filtered = {k: v for k, v in context.items() if k != "agent"}
        context_str = ""
        if ctx_filtered:
            try:
                context_str = f" {COLORS['DIM']}{json.dumps(ctx_filtered)}{COLORS['RESET']}"
            except Exception:
                context_str = f" {COLORS['DIM']}{str(ctx_filtered)}{COLORS['RESET']}"

        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            **context
        }
        self.logs.append(log_entry)
        if len(self.logs) > 500:
            self.logs.pop(0)

        color = COLORS.get(level, "")
        return f"{COLORS['DIM']}{timestamp}{COLORS['RESET']} {color}{icon} [{level}]{agent_tag}{COLORS['RESET']} {message}{context_str}"

    def debug(self, message, context=None):
        if self.min_level <= LEVELS["DEBUG"]:
            sys.stdout.buffer.write((self._format("DEBUG", message, context) + '\n').encode('utf-8', errors='replace'))
            sys.stdout.flush()

    def info(self, message, context=None):
        if self.min_level <= LEVELS["INFO"]:
            sys.stdout.buffer.write((self._format("INFO", message, context) + '\n').encode('utf-8', errors='replace'))
            sys.stdout.flush()

    def warn(self, message, context=None):
        if self.min_level <= LEVELS["WARN"]:
            sys.stdout.buffer.write((self._format("WARN", message, context) + '\n').encode('utf-8', errors='replace'))
            sys.stdout.flush()

    def error(self, message, context=None):
        if self.min_level <= LEVELS["ERROR"]:
            sys.stdout.buffer.write((self._format("ERROR", message, context) + '\n').encode('utf-8', errors='replace'))
            sys.stdout.flush()

    def get_recent_logs(self, count=50):
        return self.logs[-count:]

# Auto select minimum level
env_level = "INFO" if os.getenv("NODE_ENV") == "production" else "DEBUG"
logger = Logger(env_level)
