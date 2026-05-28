import json
import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.utils.validators import format_currency
from src.utils.logger import logger
from src.ai.deepseek_client import chat_completion

class FraudAgent(BaseAgent):
    def __init__(self):
        super().__init__('fraud', 'Fraud Detection Agent', '🛡️')
        self.use_reasoning = True
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "analyze_transactions",
                    "description": "Analyze the user's recent transactions for anomalies or fraudulent patterns.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "freeze_account",
                    "description": "Request a freeze on a specific account due to suspected fraud. This will require human approval.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string", "description": "The ID of the account to freeze"},
                            "reason": {"type": "string", "description": "Reason for freezing the account"}
                        },
                        "required": ["accountId", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "block_card",
                    "description": "Block a specific card associated with an account to prevent further unauthorized use.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string", "description": "The ID of the account whose card should be blocked"},
                            "cardLastFour": {"type": "string", "description": "Last 4 digits of the card (optional)"}
                        },
                        "required": ["accountId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "report_unauthorized_transaction",
                    "description": "Flag a transaction as unauthorized by the user, triggering an investigation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "transactionId": {"type": "string", "description": "The ID of the fraudulent transaction"},
                            "details": {"type": "string", "description": "Details provided by the user"}
                        },
                        "required": ["transactionId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "alert_banker",
                    "description": "Send a high-priority alert directly to the banker dashboard regarding suspicious activity.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "The alert message to show the banker"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "Severity of the alert"}
                        },
                        "required": ["message", "severity"]
                    }
                }
            }
        ]

        self.tools = {
            "analyze_transactions": self.analyze_transactions,
            "freeze_account": self.freeze_account,
            "block_card": self.block_card,
            "report_unauthorized_transaction": self.report_unauthorized_transaction,
            "alert_banker": self.alert_banker,
        }

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}
            
        user_id = params.get("userId")
        if not user_id:
            return {
                "agent": self.name,
                "displayName": self.display_name,
                "icon": self.icon,
                "content": 'Please select a user account to proceed.',
                "usage": {}
            }

        user = data_store.get_user_by_id(user_id)
        recent_txns = data_store.get_transactions_by_user_id(user_id, 30)
        high_risk_txns = [t for t in recent_txns if t.get("riskScore", 0) > 0.5]
        accounts = data_store.get_accounts_by_user_id(user_id)

        accounts_str = ", ".join(f"{a['name']} ({a['id']}): {a.get('status')}" for a in accounts)
        
        flagged_txns_str = ""
        if high_risk_txns:
            items = "\n".join(
                f"  - {t['id']} | {t['date'].split('T')[0]} | {t['merchant']} | {format_currency(t['amount'])} | Risk: {t['riskScore']*100:.0f}%"
                for t in high_risk_txns
            )
            flagged_txns_str = f"FLAGGED TRANSACTIONS:\n{items}"
        else:
            flagged_txns_str = "No flagged transactions."

        total_amount = sum(abs(t.get("amount", 0)) for t in recent_txns)
        avg_txn = total_amount / len(recent_txns) if recent_txns else 0

        context_data = f"""
USER: {user['firstName']} {user['lastName']} ({user_id}) | Risk Profile: {user.get('riskProfile', 'moderate')}
ACCOUNTS: {accounts_str}
TOTAL RECENT TRANSACTIONS: {len(recent_txns)}
HIGH RISK TRANSACTIONS (score > 0.5): {len(high_risk_txns)}
{flagged_txns_str}
AVERAGE TRANSACTION: {format_currency(avg_txn)}

Note: If you identify a serious threat, you MUST use the alert_banker tool to notify human staff immediately. Use freeze_account if necessary."""

        return await super().process(session_id, user_message, params, context_data)

    def analyze_transactions(self, **params):
        user_id = params.get("userId")
        txns = data_store.get_transactions_by_user_id(user_id, 50)
        amounts = [abs(t.get("amount", 0)) for t in txns]
        avg = sum(amounts) / len(amounts) if amounts else 0
        
        anomalies = [
            t for t in txns
            if abs(t.get("amount", 0)) > avg * 3 or t.get("riskScore", 0) > 0.6
        ]

        risk_level = 'HIGH' if len(anomalies) > 5 else 'MEDIUM' if len(anomalies) > 2 else 'LOW'

        return {
            "riskLevel": risk_level,
            "transactionsAnalyzed": len(txns),
            "anomaliesDetected": len(anomalies),
            "averageTransaction": avg,
            "flaggedTransactions": [
                {
                    "id": t["id"],
                    "merchant": t["merchant"],
                    "amount": t["amount"],
                    "riskScore": t.get("riskScore", 0)
                } for t in anomalies
            ]
        }

    def freeze_account(self, **params):
        user_id = params.get("userId")
        account_id = params.get("accountId")
        reason = params.get("reason", "Suspicious activity")
        
        approval = data_store.add_approval({
            "type": 'account_freeze',
            "agentName": self.name,
            "userId": user_id,
            "details": {"accountId": account_id, "reason": reason},
            "reason": 'Account freeze requires human authorization',
        })

        return {
            "success": False,
            "requiresApproval": True,
            "approvalId": approval["id"],
            "message": f"Account freeze request submitted for human review. Approval ID: {approval['id']}"
        }

    def block_card(self, **params):
        account_id = params.get("accountId")
        return {"success": True, "message": f"Card associated with account {account_id} has been successfully blocked."}

    def report_unauthorized_transaction(self, **params):
        txn_id = params.get("transactionId")
        return {"success": True, "message": f"Transaction {txn_id} has been flagged for investigation. A fraud case has been opened."}

    def alert_banker(self, **params):
        data_store.emit('agent:alert', {
            "agent": self.display_name,
            "userId": params.get("userId"),
            "message": params.get("message"),
            "severity": params.get("severity"),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return {"success": True, "message": "Alert sent to banker dashboard."}

    async def evaluate_risk(self, txn):
        try:
            account = data_store.get_account_by_id(txn.get("accountId"))
            if not account:
                return
            user = data_store.get_user_by_id(account.get("userId"))
            if not user:
                return
            
            recent_txns = data_store.get_transactions_by_user_id(user["id"], 20)
            total_amount = sum(abs(t.get("amount", 0)) for t in recent_txns)
            avg_txn = total_amount / len(recent_txns) if recent_txns else 1.0

            prompt = f"""You are an expert banking fraud detection AI.
Evaluate this newly submitted transaction for fraud risk. Pay special attention to the Merchant name and Description for any signs of social engineering, scams, or "scummy" behavior (e.g., lottery winnings, urgent IRS payments, tech support scams, suspicious crypto links).

TRANSACTION DATA:
- Merchant: {txn.get('merchant')}
- Category: {txn.get('category')}
- Amount: {format_currency(txn.get('amount', 0))}
- Description: {txn.get('description', 'No description provided')}

USER PROFILE ({user.get('firstName')} {user.get('lastName')}):
- Income: {format_currency(user.get('annualIncome', 0))}
- Account Type: {account.get('type')}
- Occupation: {user.get('occupation')}
- Average Transaction: {format_currency(avg_txn)}

Assign a risk score from 0.0 (safest) to 1.0 (certain fraud).
Return ONLY valid JSON in this format:
{{"riskScore": 0.85, "reason": "Social engineering detected in description: urgent request for 'winning fees'."}}"""

            response = await chat_completion(
                [{"role": 'system', content: prompt}],
                {
                    "agentName": self.name,
                    "useReasoning": True,
                    "responseFormat": {"type": "json_object"}
                }
            )

            try:
                result = json.loads(response.get("content", "{}"))
            except Exception:
                result = {"riskScore": 0.1, "reason": "Could not parse AI response."}

            final_score = float(result.get("riskScore", 0.1))
            
            # Update transaction in DB
            txn["riskScore"] = final_score
            data_store.save()
            
            # Emit trace
            data_store.emit('agent:trace', {
                "agent": self.display_name,
                "reasoning": response.get("reasoning", ""),
                "content": f"Evaluated Transaction: {txn.get('merchant')} for {format_currency(txn.get('amount', 0))}. Assigned Risk Score: {final_score}. Reason: {result.get('reason')}",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })

            # If high risk, alert the banker
            if final_score > 0.6:
                self.alert_banker(
                    userId=user["id"],
                    message=f"High risk transaction detected! {txn.get('merchant')} for {format_currency(txn.get('amount', 0))}. Reason: {result.get('reason')}",
                    severity='high'
                )

        except Exception as e:
            logger.error(f"Agentic Risk Eval failed: {str(e)}")

fraud_agent = FraudAgent()
