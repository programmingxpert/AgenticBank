import json
import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.middleware.human_approval import execute_approved_action, handle_rejection
from src.utils.logger import logger

BANKER_COPILOT_PROMPT = """You are the AI Banker Copilot — an intelligent virtual assistant designed to help bank staff (Compliance Officers and Fraud Analysts) monitor systems and take actions.
You have direct, elevated access to customer accounts, transactions, approvals, complaints, and audit logs.

Your role is to help the banker investigate activity and take actions. You can execute tools directly on behalf of the banker.

AVAILABLE ACTIONS & CAPABILITIES:
1. Get User Financials & Risk Profile: Retrieve accounts, KYC, loans, and recent transactions. Use get_user_financials.
2. Freeze User Accounts: Instantly freeze all accounts of a flagged user. Use freeze_user_accounts.
3. Unfreeze User Accounts: Activate accounts of a user. Use unfreeze_user_accounts.
4. Block Card: Block credit/debit card on an account. Use block_card.
5. Resolve Approvals: Approve or reject pending human-in-the-loop decisions (large transfers, loan applications, KYC reviews). Use resolve_approval.
6. Resolve Complaints: Close or update customer complaints. Use resolve_complaint.

GUIDELINES:
- Always use the Indian Rupees (₹) format for currency.
- Respond professionally, clearly, and list all actions taken.
- If a banker asks you to "freeze user X", identify the correct user ID (e.g., USR-003) and call freeze_user_accounts.
- If a banker asks you to approve or reject a transaction/loan, find the corresponding pending approval ID and call resolve_approval.
- Summarize findings in tables where appropriate to match our premium aesthetic.
"""

class BankerCopilotAgent(BaseAgent):
    def __init__(self):
        super().__init__('banker-copilot', 'AI Banker Copilot', '🤖')
        self.system_prompt = BANKER_COPILOT_PROMPT
        self.use_reasoning = True
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "get_user_financials",
                    "description": "Get a user's accounts, recent transactions, KYC status, and active loans.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "userId": {"type": "string", "description": "The ID of the user (e.g. USR-003)"}
                        },
                        "required": ["userId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "freeze_user_accounts",
                    "description": "Freeze all accounts associated with a specific user ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "userId": {"type": "string", "description": "The ID of the user to freeze"},
                            "reason": {"type": "string", "description": "Reason for freezing the accounts"}
                        },
                        "required": ["userId", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "unfreeze_user_accounts",
                    "description": "Unfreeze (activate) all accounts associated with a specific user ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "userId": {"type": "string", "description": "The ID of the user to unfreeze"}
                        },
                        "required": ["userId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "block_card",
                    "description": "Block the card associated with a specific account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string", "description": "The account ID whose card should be blocked"}
                        },
                        "required": ["accountId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "resolve_approval",
                    "description": "Directly approve or reject a pending human-in-the-loop approval item.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "approvalId": {"type": "string", "description": "The ID of the pending approval (e.g., APR-001)"},
                            "decision": {"type": "string", "enum": ["approved", "rejected"], "description": "The resolution decision"},
                            "reviewerNote": {"type": "string", "description": "A note explaining the reason for the decision"}
                        },
                        "required": ["approvalId", "decision"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "resolve_complaint",
                    "description": "Update the status of a customer complaint (e.g. resolve it).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "complaintId": {"type": "string", "description": "The ID of the complaint (e.g., CMP-001)"},
                            "status": {"type": "string", "enum": ["open", "investigating", "resolved"], "description": "The new status of the complaint"}
                        },
                        "required": ["complaintId", "status"]
                    }
                }
            }
        ]

        self.tools = {
            "get_user_financials": self.get_user_financials,
            "freeze_user_accounts": self.freeze_user_accounts,
            "unfreeze_user_accounts": self.unfreeze_user_accounts,
            "block_card": self.block_card,
            "resolve_approval": self.resolve_approval,
            "resolve_complaint": self.resolve_complaint,
        }

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}
            
        self.system_prompt = BANKER_COPILOT_PROMPT
        
        pending_approvals = data_store.get_pending_approvals()
        all_complaints = data_store.get_all_complaints()
        open_complaints = [c for c in all_complaints if c.get("status") != 'resolved']
        
        approvals_str = "\n".join(
            f"  - ID: {a['id']} | Type: {a['type']} | User: {a['userId']} | Reason: {a['reason']} | Detail: {json.dumps(a['details'])}"
            for a in pending_approvals
        )
        
        complaints_str = "\n".join(
            f"  - ID: {c['id']} | User: {c['userId']} | Subject: {c['subject']} | Status: {c['status']} | Priority: {c['priority']}"
            for c in open_complaints
        )
        
        context_data = f"""
ROLE OF LOGGED IN BANKER: {params.get('bankerRole', 'Compliance Officer')}
NAME OF LOGGED IN BANKER: {params.get('bankerName', 'Alex Rivera')}

PENDING APPROVALS QUEUE ({len(pending_approvals)} items):
{approvals_str}

OPEN COMPLAINTS ({len(open_complaints)} items):
{complaints_str}"""

        return await super().process(session_id, user_message, params, context_data)

    def get_user_financials(self, **params):
        user_id = params.get("userId")
        user = data_store.get_user_by_id(user_id)
        if not user:
            return {"error": f"User {user_id} not found."}

        accounts = data_store.get_accounts_by_user_id(user_id)
        loans = data_store.get_loans_by_user_id(user_id)
        txns = data_store.get_transactions_by_user_id(user_id, 10)

        return {
            "user": {
                "id": user["id"],
                "name": f"{user['firstName']} {user['lastName']}",
                "riskProfile": user.get("riskProfile"),
                "kycStatus": user.get("kycStatus"),
                "occupation": user.get("occupation"),
                "annualIncome": user.get("annualIncome"),
            },
            "accounts": [{"id": a["id"], "name": a["name"], "type": a["type"], "balance": a["balance"], "status": a.get("status")} for a in accounts],
            "loans": [{"id": l["id"], "purpose": l["purpose"], "amount": l["amount"], "status": l["status"]} for l in loans],
            "recentTransactions": [
                {
                    "id": t["id"],
                    "merchant": t["merchant"],
                    "amount": t["amount"],
                    "category": t["category"],
                    "riskScore": t.get("riskScore", 0),
                    "date": t["date"]
                } for t in txns
            ]
        }

    def freeze_user_accounts(self, **params):
        user_id = params.get("userId")
        reason = params.get("reason", "Suspicious activity")
        
        accounts = data_store.get_accounts_by_user_id(user_id)
        if not accounts:
            return {"success": False, "error": f"No accounts found for user {user_id}"}

        for acc in accounts:
            data_store.update_account(acc["id"], {"status": 'frozen'})
        
        data_store._audit('banker_freeze_user', {"userId": user_id, "reason": reason})
        data_store.emit('transaction', {"userId": user_id})  # Trigger UI refreshes
        
        return {
            "success": True,
            "message": f"Successfully froze {len(accounts)} account(s) for user {user_id}.",
            "accounts": [a["id"] for a in accounts]
        }

    def unfreeze_user_accounts(self, **params):
        user_id = params.get("userId")
        accounts = data_store.get_accounts_by_user_id(user_id)
        if not accounts:
            return {"success": False, "error": f"No accounts found for user {user_id}"}

        for acc in accounts:
            data_store.update_account(acc["id"], {"status": 'active'})
            
        data_store._audit('banker_unfreeze_user', {"userId": user_id})
        data_store.emit('transaction', {"userId": user_id})  # Trigger UI refreshes
        
        return {
            "success": True,
            "message": f"Successfully unfrozen all accounts for user {user_id}.",
            "accounts": [a["id"] for a in accounts]
        }

    def block_card(self, **params):
        account_id = params.get("accountId")
        data_store._audit('banker_block_card', {"accountId": account_id})
        data_store.save()
        return {
            "success": True,
            "message": f"Card for account {account_id} has been blocked successfully."
        }

    async def resolve_approval(self, **params):
        approval_id = params.get("approvalId")
        decision = params.get("decision")
        reviewer_note = params.get("reviewerNote", "")

        try:
            # Find the approval item
            approval = next((a for a in data_store.approval_queue if a["id"] == approval_id), None)
            if not approval:
                return {"success": False, "error": f"Approval item {approval_id} not found."}
            if approval.get("status") != 'pending':
                return {"success": False, "error": f"Approval item {approval_id} is already {approval.get('status')}."}

            resolved = data_store.resolve_approval(approval_id, decision, reviewer_note)
            
            exec_result = None
            if decision == 'approved':
                exec_result = await execute_approved_action(resolved)
            else:
                exec_result = handle_rejection(resolved)

            data_store.emit('approval:resolved', {"id": approval_id, "decision": decision})
            
            return {
                "success": True,
                "message": f"Approval item {approval_id} resolved as {decision}.",
                "details": exec_result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resolve_complaint(self, **params):
        complaint_id = params.get("complaintId")
        status = params.get("status")

        complaint = next((c for c in data_store.complaints if c["id"] == complaint_id), None)
        if not complaint:
            return {"success": False, "error": f"Complaint {complaint_id} not found."}

        data_store.update_complaint(complaint_id, {"status": status})
        data_store._audit('banker_resolve_complaint', {"complaintId": complaint_id, "status": status})
        
        data_store.emit('complaint:resolved', complaint)  # Notify UI
        return {
            "success": True,
            "message": f"Complaint {complaint_id} status updated to {status}."
        }

banker_copilot_agent = BankerCopilotAgent()
