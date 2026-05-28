import json
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.config import config
from src.utils.validators import format_currency
from src.utils.logger import logger

class TransactionAgent(BaseAgent):
    def __init__(self):
        super().__init__('transaction', 'Transaction Agent', '💸')
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "check_balance",
                    "description": "Get the balances of all accounts for the current user.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "transfer_funds",
                    "description": "Transfer money from one account to another.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fromAccountId": {"type": "string", "description": "The ID of the account to transfer from (e.g. ACC-1001)"},
                            "toAccountId": {"type": "string", "description": "The ID of the account to transfer to"},
                            "amount": {"type": "number", "description": "The amount to transfer"},
                            "description": {"type": "string", "description": "A memo or description for the transfer"}
                        },
                        "required": ["fromAccountId", "toAccountId", "amount"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_transaction_history",
                    "description": "Get the recent transaction history for a specific account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string", "description": "The ID of the account"},
                            "limit": {"type": "number", "description": "Max number of transactions to return"}
                        },
                        "required": ["accountId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "pay_bill",
                    "description": "Pay a bill to a specific payee.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string", "description": "The ID of the account to pay from"},
                            "payee": {"type": "string", "description": "Name of the payee/merchant"},
                            "amount": {"type": "number", "description": "Amount to pay"}
                        },
                        "required": ["accountId", "payee", "amount"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "schedule_payment",
                    "description": "Schedule a future payment or recurring transfer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string", "description": "Source account ID"},
                            "toAccount": {"type": "string", "description": "Destination account number"},
                            "amount": {"type": "number", "description": "Amount to transfer"},
                            "date": {"type": "string", "description": "Date of payment (YYYY-MM-DD)"},
                            "frequency": {"type": "string", "enum": ["once", "monthly", "weekly"], "description": "Frequency of payment"}
                        },
                        "required": ["accountId", "toAccount", "amount", "date"]
                    }
                }
            }
        ]

        self.tools = {
            "check_balance": self.check_balance,
            "transfer_funds": self.transfer_funds,
            "get_transaction_history": self.get_transaction_history,
            "pay_bill": self.pay_bill,
            "schedule_payment": self.schedule_payment,
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

        accounts = data_store.get_accounts_by_user_id(user_id)
        user = data_store.get_user_by_id(user_id)

        accounts_str = "\n".join(
            f"  - {a['name']} ({a['id']}): {format_currency(a['balance'])} [{a['type']}] {a['accountNumber']}"
            for a in accounts
        )

        context_data = f"""
USER: {user['firstName']} {user['lastName']} ({user_id})
ACCOUNTS:
{accounts_str}

Note: Use the provided tools to fetch balances or make transfers if requested by the user. Do not invent transaction data."""

        return await super().process(session_id, user_message, params, context_data)

    def check_balance(self, **params):
        user_id = params.get("userId")
        accounts = data_store.get_accounts_by_user_id(user_id)
        return [{"id": a["id"], "name": a["name"], "type": a["type"], "balance": a["balance"], "number": a["accountNumber"]} for a in accounts]

    async def transfer_funds(self, **params):
        from_account_id = params.get("fromAccountId")
        to_account_id = params.get("toAccountId")
        amount = float(params.get("amount", 0))
        description = params.get("description", "")
        user_id = params.get("userId")

        # Check if human approval is needed
        if amount > config.approval_thresholds["transfer"]:
            approval = data_store.add_approval({
                "type": 'large_transfer',
                "agentName": self.name,
                "userId": user_id,
                "details": {
                    "fromAccountId": from_account_id,
                    "toAccountId": to_account_id,
                    "amount": amount,
                    "description": description
                },
                "reason": f"Transfer of {format_currency(amount)} exceeds threshold of {format_currency(config.approval_thresholds['transfer'])}",
            })

            return {
                "success": False,
                "requiresApproval": True,
                "approvalId": approval["id"],
                "message": f"This transfer of ₹{amount:,.2f} exceeds our automated threshold of ₹5,00,000. It has been flagged for human review and compliance verification. Reference ID: {approval['id']}. Would you like me to proceed with flagging this for banker approval?"
            }

        try:
            result = data_store.transfer_funds(from_account_id, to_account_id, amount, description)
            return {
                "success": True,
                "message": f"Transfer completed successfully. Reference ID: {result['debit']['id']}"
            }
        except Exception as error:
            return {"success": False, "message": f"Transfer failed: {str(error)}"}

    def get_transaction_history(self, **params):
        account_id = params.get("accountId")
        limit = int(params.get("limit", 20))
        return data_store.get_transactions_by_account_id(account_id, limit)

    def pay_bill(self, **params):
        account_id = params.get("accountId")
        payee = params.get("payee")
        amount = float(params.get("amount", 0))
        try:
            txn = data_store.create_transaction(
                account_id=account_id,
                type_val='debit',
                amount=-abs(amount),
                merchant=payee,
                category='Bills',
                description=f"Bill payment to {payee}",
            )
            return {"success": True, "transactionId": txn["id"], "message": f"Successfully paid {amount} to {payee}"}
        except Exception as error:
            return {"success": False, "message": f"Payment failed: {str(error)}"}

    def schedule_payment(self, **params):
        amount = float(params.get("amount", 0))
        to_account = params.get("toAccount")
        date_str = params.get("date")
        frequency = params.get("frequency", "once")
        return {
            "success": True,
            "message": f"Successfully scheduled {frequency} payment of {format_currency(amount)} to {to_account} on {date_str}."
        }

transaction_agent = TransactionAgent()
