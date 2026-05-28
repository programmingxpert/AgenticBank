import re
import json
import datetime
from typing import TypedDict, Dict, List, Optional, Any
from langgraph.graph import StateGraph, END
from src.ai.deepseek_client import chat_completion
from src.ai.prompts import ORCHESTRATOR_PROMPT
from src.agents.transaction_agent import transaction_agent
from src.agents.fraud_agent import fraud_agent
from src.agents.loan_agent import loan_agent
from src.agents.customer_service_agent import customer_service_agent
from src.agents.investment_agent import investment_agent
from src.agents.compliance_agent import compliance_agent
from src.agents.banker_copilot_agent import banker_copilot_agent
from src.agents.payment_orchestrator_agent import payment_orchestrator_agent
from src.data.data_store import data_store
from src.utils.logger import logger

agents = {
    "TRANSACTION": transaction_agent,
    "FRAUD": fraud_agent,
    "LOAN": loan_agent,
    "CUSTOMER_SERVICE": customer_service_agent,
    "INVESTMENT": investment_agent,
    "COMPLIANCE": compliance_agent,
    "PAYMENT": payment_orchestrator_agent,
}

AGENT_INFO = [
    { "id": 'TRANSACTION', "name": 'Transaction Agent', "icon": '💸', "description": 'Handles transfers, payments, balances, and transaction history' },
    { "id": 'FRAUD', "name": 'Fraud Detection Agent', "icon": '🛡️', "description": 'Monitors suspicious activity and account security' },
    { "id": 'LOAN', "name": 'Loan & Credit Agent', "icon": '🏦', "description": 'Loan applications, credit scoring, and EMI calculations' },
    { "id": 'CUSTOMER_SERVICE', "name": 'Customer Service Agent', "icon": '🎧', "description": 'Account inquiries, profile updates, and complaint filing' },
    { "id": 'INVESTMENT', "name": 'Investment Advisory Agent', "icon": '📈', "description": 'Portfolio management and investment recommendations' },
    { "id": 'COMPLIANCE', "name": 'Compliance Agent', "icon": '📋', "description": 'KYC verification, AML screening, and regulatory compliance' },
    { "id": 'PAYMENT', "name": 'Payment Orchestrator', "icon": '💳', "description": 'Autonomous payment processing: UPI, NEFT, RTGS, SWIFT, IMPS routing & execution' },
]

from langgraph.checkpoint.memory import MemorySaver

class AgentState(TypedDict):
    session_id: str
    user_message: str
    user_id: Optional[str]
    params: Dict[str, Any]
    domain: Optional[str]
    confidence: float
    summary: str
    context_data: Dict[str, Any]
    final_result: Optional[Dict[str, Any]]
    next_agent: str
    hop_count: int

def keyword_route(message: str) -> Optional[str]:
    msg = message.lower().strip()
    # Payment-specific terms checked first to prevent TRANSACTION pattern from shadowing them
    if re.search(r"pay to|send to|wire|remit|neft|rtgs|upi|imps|swift|beneficiary|payee|initiate.*payment|process.*payment|transfer to", msg):
        return 'PAYMENT'
    if re.search(r"balance|transfer|send money|pay|payment|bill|transaction history|account", msg):
        return 'TRANSACTION'
    if re.search(r"fraud|suspicious|hack|stolen|unauthorized|freeze|security", msg):
        return 'FRAUD'
    if re.search(r"loan|mortgage|credit score|emi|borrow|refinance|interest rate", msg):
        return 'LOAN'
    if re.search(r"help|complaint|update.*profile|address|phone|email|support|faq", msg):
        return 'CUSTOMER_SERVICE'
    if re.search(r"invest|portfolio|stock|trade|buy.*shares|sell.*shares|market|dividend", msg):
        return 'INVESTMENT'
    if re.search(r"kyc|compliance|aml|verify|identity|sanction|regulation", msg):
        return 'COMPLIANCE'
    return None

# ─── LangGraph Nodes ────────────────────────────────────────────────────────

# ─── LangGraph Nodes ────────────────────────────────────────────────────────

async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    user_message = state["user_message"]
    hop_count = state.get("hop_count", 0)
    context_data = state.get("context_data", {})
    
    # Recursion safety
    if hop_count >= 4:
        return {"next_agent": "FINISH"}
        
    data_store.emit('agent:trace', {
        "agent": 'orchestrator',
        "content": f"🧠 Supervisor evaluating state (Hop {hop_count + 1})...",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    
    domain = state.get("domain")
    next_agent = "FINISH"
    
    # Heuristic dynamic routing to save latency while maintaining cyclic graph abilities
    if hop_count == 0:
        domain = keyword_route(user_message) or "CUSTOMER_SERVICE"
        next_agent = domain
    else:
        executed_agents = list(context_data.keys())
        # Dynamic secondary hops based on what executed first
        if "TRANSACTION" in executed_agents and "FRAUD" not in executed_agents:
            next_agent = "FRAUD"
        elif "PAYMENT" in executed_agents and "COMPLIANCE" not in executed_agents:
            next_agent = "COMPLIANCE"
        elif "TRANSACTION" in executed_agents and "COMPLIANCE" not in executed_agents:
            next_agent = "COMPLIANCE"
        elif "LOAN" in executed_agents and "COMPLIANCE" not in executed_agents:
            next_agent = "COMPLIANCE"
        elif "FRAUD" in executed_agents and "COMPLIANCE" not in executed_agents:
            next_agent = "COMPLIANCE"
        elif "INVESTMENT" in executed_agents and "TRANSACTION" not in executed_agents:
            next_agent = "TRANSACTION"
        else:
            next_agent = "FINISH"
            
    if next_agent != "FINISH":
        data_store.emit('agent:trace', {
            "agent": 'orchestrator',
            "content": f"🔀 Supervisor dynamically routing to **{next_agent}**",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
    else:
        data_store.emit('agent:trace', {
            "agent": 'orchestrator',
            "content": f"✅ Supervisor determined workflow is complete.",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

    return {
        "next_agent": next_agent,
        "domain": domain if hop_count == 0 else state.get("domain")
    }

async def execute_agent(state: AgentState, agent_id: str) -> Dict[str, Any]:
    agent = agents[agent_id]
    
    data_store.emit('agent:trace', {
        "agent": 'orchestrator',
        "content": f"⚙️ Executing Agent Node: **{agent.display_name}**",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    
    result = await agent.process(
        state["session_id"],
        state["user_message"],
        {**state["params"], "userId": state["user_id"], "pipelineContext": state["context_data"]}
    )
    
    new_context = state["context_data"].copy()
    new_context[agent_id] = result
    
    final_result = state["final_result"]
    if agent_id == state["domain"] or final_result is None:
        final_result = result
        
    return {
        "context_data": new_context,
        "final_result": final_result,
        "hop_count": state.get("hop_count", 0) + 1
    }

async def transaction_node(state: AgentState): return await execute_agent(state, "TRANSACTION")
async def fraud_node(state: AgentState): return await execute_agent(state, "FRAUD")
async def loan_node(state: AgentState): return await execute_agent(state, "LOAN")
async def customer_service_node(state: AgentState): return await execute_agent(state, "CUSTOMER_SERVICE")
async def investment_node(state: AgentState): return await execute_agent(state, "INVESTMENT")
async def compliance_node(state: AgentState): return await execute_agent(state, "COMPLIANCE")
async def payment_node(state: AgentState): return await execute_agent(state, "PAYMENT")

async def finalize_node(state: AgentState) -> Dict[str, Any]:
    domain = state["domain"]
    session_id = state["session_id"]
    data_store.update_session(session_id, {"lastAgent": domain})
    
    final_res = state["final_result"].copy() if state["final_result"] else {}
    final_res.update({
        "domain": domain,
        "routingConfidence": state.get("confidence", 0.9),
        "routingSummary": state.get("summary", "")
    })
    return {"final_result": final_res}

# ─── Edges ──────────────────────────────────────────────────────────────────

def supervisor_router(state: AgentState) -> str:
    next_agent = state.get("next_agent", "FINISH")
    if next_agent == "FINISH":
        return "finalize"
    return next_agent

# Compile LangGraph Workflow
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("TRANSACTION", transaction_node)
workflow.add_node("FRAUD", fraud_node)
workflow.add_node("LOAN", loan_node)
workflow.add_node("CUSTOMER_SERVICE", customer_service_node)
workflow.add_node("INVESTMENT", investment_node)
workflow.add_node("COMPLIANCE", compliance_node)
workflow.add_node("PAYMENT", payment_node)
workflow.add_node("finalize", finalize_node)

workflow.set_entry_point("supervisor")

# The supervisor dynamically decides the next agent to route to, or to finalize
workflow.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "TRANSACTION": "TRANSACTION",
        "FRAUD": "FRAUD",
        "LOAN": "LOAN",
        "CUSTOMER_SERVICE": "CUSTOMER_SERVICE",
        "INVESTMENT": "INVESTMENT",
        "COMPLIANCE": "COMPLIANCE",
        "PAYMENT": "PAYMENT",
        "finalize": "finalize"
    }
)

# All agents route back to the supervisor when they are done
workflow.add_edge("TRANSACTION", "supervisor")
workflow.add_edge("FRAUD", "supervisor")
workflow.add_edge("LOAN", "supervisor")
workflow.add_edge("CUSTOMER_SERVICE", "supervisor")
workflow.add_edge("INVESTMENT", "supervisor")
workflow.add_edge("COMPLIANCE", "supervisor")
workflow.add_edge("PAYMENT", "supervisor")

workflow.add_edge("finalize", END)

# Initialize Checkpointer Memory
memory = MemorySaver()
graph_app = workflow.compile(checkpointer=memory)

# ─── Orchestrator APIs ───────────────────────────────────────────────────────

async def route_message(session_id: str, user_message: str, user_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    if params is None:
        params = {}
        
    session = data_store.get_session(session_id)
    if not session:
        session = data_store.create_session(id_val=session_id, user_id=user_id)
        
    # Append user message to session chat log in DB
    data_store.add_message_to_session(session_id, {"role": "user", "content": user_message})

    # Initialize state
    initial_state = {
        "session_id": session_id,
        "user_message": user_message,
        "user_id": user_id,
        "params": params,
        "domain": None,
        "confidence": 0.9,
        "summary": user_message,
        "context_data": {},
        "final_result": None,
        "next_agent": "",
        "hop_count": 0
    }

    # Run LangGraph State Machine with thread isolation
    thread_config = {"configurable": {"thread_id": session_id}}
    state_result = await graph_app.ainvoke(initial_state, config=thread_config)
    final_res = state_result["final_result"]

    # Append assistant response to session chat log in DB
    domain = final_res.get("domain") or state_result.get("domain") or "CUSTOMER_SERVICE"
    data_store.add_message_to_session(session_id, {
        "role": 'agent',
        "content": final_res.get("content", ""),
        "domain": domain,
        "displayName": final_res.get("displayName"),
        "icon": final_res.get("icon"),
        "requiresApproval": final_res.get("requiresApproval"),
        "approvalId": final_res.get("approvalId"),
        "routingConfidence": final_res.get("routingConfidence", 1.0),
        "routingSummary": final_res.get("routingSummary")
    })

    # Autogenerate session title if it remains 'New Chat'
    updated_session = data_store.get_session(session_id)
    if updated_session and updated_session.get("title") == 'New Chat':
        words = user_message.split()[:5]
        words_str = " ".join(words)
        new_title = words_str[:27] + "..." if len(words_str) > 30 else words_str
        data_store.update_session(session_id, {"title": new_title.upper()})

    return final_res

async def route_banker_message(session_id: str, user_message: str, target_user_id: str, banker_profile: Dict[str, Any] = None) -> Dict[str, Any]:
    if banker_profile is None:
        banker_profile = {}
        
    session = data_store.get_session(session_id)
    if not session:
        session = data_store.create_session(
            id_val=session_id,
            user_id=target_user_id or banker_profile.get("username") or 'banker',
            title=f"Banker AI Session"
        )

    data_store.add_message_to_session(session_id, {"role": "user", "content": user_message})

    data_store.emit('agent:trace', {
        "agent": 'orchestrator',
        "content": f"💼 Banker Copilot: Processing message on target user \"{target_user_id or 'N/A'}\"",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })

    result = await banker_copilot_agent.process(session_id, user_message, {
        "userId": target_user_id,
        "bankerRole": banker_profile.get("role"),
        "bankerName": banker_profile.get("username") or banker_profile.get("name") or 'Banker'
    })

    if result and result.get("content"):
        data_store.add_message_to_session(session_id, {"role": "agent", "content": result["content"]})

    # Autogenerate session title if it remains 'New Chat'
    updated_session = data_store.get_session(session_id)
    if updated_session and updated_session.get("title") == 'New Chat':
        words = user_message.split()[:5]
        words_str = " ".join(words)
        new_title = words_str[:27] + "..." if len(words_str) > 30 else words_str
        data_store.update_session(session_id, {"title": new_title.upper()})

    return result

def get_agent_info() -> List[Dict[str, Any]]:
    return AGENT_INFO

def get_agent_by_domain(domain: str):
    return agents.get(domain)
