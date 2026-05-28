import os
import json
import random
import time
from datetime import datetime
from src.utils.vector_store import vector_store
from src.utils.logger import logger

MEMORY_FILE = os.path.join(os.getcwd(), 'agent_memory.json')

class MemoryAgent:
    def __init__(self):
        self.memories = []
        self.user_memory = {}
        self.load()

    def load(self):
        try:
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        parsed = json.loads(content)
                        if isinstance(parsed, dict):
                            self.memories = parsed.get("memories", [])
                            self.user_memory = parsed.get("userMemory", {})
                        elif isinstance(parsed, list):
                            self.memories = parsed
                            self.user_memory = {}
                logger.info(f"MemoryAgent loaded {len(self.memories)} episodic memories", {"agent": "memory"})
        except Exception as e:
            logger.error(f"Failed to load memory: {str(e)}", {"agent": "memory"})

    def save(self):
        try:
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                f.write(json.dumps({
                    "memories": self.memories,
                    "userMemory": self.user_memory
                }, indent=2))
        except Exception as e:
            logger.error(f"Failed to save memory: {str(e)}", {"agent": "memory"})

    def init_user(self, user_id):
        if user_id not in self.user_memory:
            self.user_memory[user_id] = {
                "working": {
                    "intent": None,
                    "entities": {},
                    "cognitiveLoad": 5,
                    "activeAgent": None,
                    "sessionStarted": None,
                    "lastQuery": None,
                },
                "semantic": {},
                "episodic": [],
                "procedural": {
                    "currentWorkflow": "IDLE",
                    "step": 0,
                    "totalSteps": 0,
                    "history": [],
                },
            }
        return self.user_memory[user_id]

    def update_working_memory(self, user_id, updates):
        mem = self.init_user(user_id)
        mem["working"].update(updates)
        mem["working"]["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
        self.save()
        return mem["working"]

    def get_working_memory(self, user_id):
        return self.init_user(user_id)["working"]

    async def set_semantic_fact(self, user_id, key, value, certainty=1.0):
        mem = self.init_user(user_id)
        mem["semantic"][key] = {
            "value": value,
            "certainty": certainty,
            "updated": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        
        # Sync to Vector Store
        await vector_store.add_semantic(user_id, key, value, {"certainty": certainty})
        self.save()
        return mem["semantic"][key]

    def get_semantic_memory(self, user_id):
        return self.init_user(user_id)["semantic"]

    async def seed_semantic_from_banking(self, user_id, user_data):
        if not user_data:
            return
        user = user_data.get("user")
        accounts = user_data.get("accounts")
        stats = user_data.get("stats")
        
        if user:
            await self.set_semantic_fact(user_id, 'User Profile', f"{user.get('firstName')} {user.get('lastName')} ({user.get('occupation')})", 1.0)
            await self.set_semantic_fact(user_id, 'Credit Score', user.get("creditScore"), 0.95)
            await self.set_semantic_fact(user_id, 'KYC Status', user.get("kycStatus"), 1.0)
            await self.set_semantic_fact(user_id, 'Risk Profile', user.get("riskProfile"), 0.9)
            
        if stats:
            await self.set_semantic_fact(user_id, 'Total Balance', stats.get("totalBalance"), 1.0)
            await self.set_semantic_fact(user_id, 'Monthly Spending', stats.get("monthlySpending"), 0.85)
            await self.set_semantic_fact(user_id, 'Net Worth', stats.get("netWorth"), 1.0)
            
        if accounts and len(accounts) > 0:
            await self.set_semantic_fact(user_id, 'Active Accounts', len(accounts), 1.0)
            await self.set_semantic_fact(user_id, 'Primary Account', accounts[0].get("accountNumber") or accounts[0].get("id"), 1.0)

    async def add_episodic_event(self, user_id, event, importance=5, valence='neutral'):
        mem = self.init_user(user_id)
        entry = {
            "id": Date_now_36() + str(random.random())[2:6],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event,
            "importance": min(10, max(1, importance)),
            "valence": valence,
        }
        mem["episodic"].insert(0, entry)
        
        # Sync to Vector Store
        await vector_store.add_episodic(user_id, event, {"importance": importance, "valence": valence})
        
        if len(mem["episodic"]) > 100:
            mem["episodic"] = mem["episodic"][:100]
            
        self.save()
        return entry

    def get_episodic_memory(self, user_id, limit=20):
        return self.init_user(user_id)["episodic"][:limit]

    def start_workflow(self, user_id, workflow_name, total_steps):
        mem = self.init_user(user_id)
        current_p = mem["procedural"]
        
        completed_outcome = 'completed' if current_p.get("step", 0) >= current_p.get("totalSteps", 0) else 'interrupted'
        history = current_p.get("history", [])
        if not history:
            history = []
            
        history.append({
            "workflow": current_p.get("currentWorkflow", "IDLE"),
            "completedAt": current_p.get("startedAt"),
            "outcome": completed_outcome
        })
        
        mem["procedural"] = {
            "currentWorkflow": workflow_name,
            "step": 1,
            "totalSteps": total_steps,
            "startedAt": datetime.utcnow().isoformat() + "Z",
            "history": history[-20:]
        }
        self.save()
        return mem["procedural"]

    def advance_workflow_step(self, user_id):
        mem = self.init_user(user_id)
        p = mem["procedural"]
        if p["step"] < p["totalSteps"]:
            p["step"] += 1
        else:
            p["currentWorkflow"] = 'IDLE'
        self.save()
        return p

    def get_procedural_memory(self, user_id):
        return self.init_user(user_id)["procedural"]

    def get_full_memory(self, user_id):
        mem = self.init_user(user_id)
        return {
            "working": mem["working"],
            "semantic": mem["semantic"],
            "episodic": mem["episodic"][:20],
            "procedural": mem["procedural"],
            "stats": {
                "semanticCount": len(mem["semantic"]),
                "episodicCount": len(mem["episodic"]),
                "workflowsCompleted": len(mem["procedural"].get("history", [])),
            }
        }

    async def add_memory(self, user_id, role, content, tags=None):
        if tags is None:
            tags = []
        memory = {
            "id": Date_now_36() + str(random.random())[2:8],
            "userId": user_id,
            "role": role,
            "content": content,
            "tags": tags,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        self.memories.append(memory)
        
        # Also log as episodic event
        importance = 3 if role == 'user' else 5
        valence = 'neutral'
        lower_content = content.lower()
        if 'error' in lower_content or 'fraud' in lower_content:
            valence = 'negative'
        elif 'approved' in lower_content or 'success' in lower_content:
            valence = 'positive'
            
        await self.add_episodic_event(
            user_id,
            f"{'User asked' if role == 'user' else 'Agent responded'}: {content[:100]}",
            importance,
            valence
        )
        
        # Update working memory
        self.update_working_memory(user_id, {
            "lastQuery": content[:200] if role == 'user' else None,
            "cognitiveLoad": 65 if role == 'user' else 15
        })
        
        if len(self.memories) > 2000:
            self.memories.pop(0)
            
        self.save()
        return memory

    def get_relevant_memories(self, user_id, query, limit=5):
        user_memories = [m for m in self.memories if m["userId"] == user_id]
        if not query:
            return user_memories[-limit:]
            
        keywords = [k.lower() for k in query.split() if len(k) > 3]
        results = []
        for m in user_memories:
            score = 0
            text = m["content"].lower()
            for k in keywords:
                if k in text:
                    score += 1
            if score > 0 or len(keywords) == 0:
                m_copy = m.copy()
                m_copy["score"] = score
                results.append(m_copy)
                
        results.sort(key=lambda x: (x.get("score", 0), x.get("timestamp", "")), reverse=True)
        return results[:limit]

def Date_now_36():
    # Helper to generate custom base36 timestamp string
    import time
    epoch_time = int(time.time())
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    result = ''
    while epoch_time > 0:
        epoch_time, remainder = divmod(epoch_time, 36)
        result = chars[remainder] + result
    return result

memory_agent = MemoryAgent()
