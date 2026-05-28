import uuid
import datetime
from collections import Counter
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.utils.logger import logger
from src.ai.prompts import AGENT_PROMPTS
from src.agents.payment_validation_agent import payment_validation_agent
from src.agents.payment_routing_agent import payment_routing_agent


class PaymentOrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__('payment_orchestrator', 'Payment Orchestrator', '💳')
        self.use_reasoning = False

        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "initiate_payment",
                    "description": (
                        "Initiate the full end-to-end payment pipeline: validate → route → execute → reconcile. "
                        "Automatically selects the optimal payment rail. Amounts > ₹5,00,000 or SWIFT payments "
                        "require human approval and are placed on HOLD."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fromAccountId":    {"type": "string", "description": "Source account ID"},
                            "toAccountId":      {"type": "string", "description": "Destination account ID (internal) or beneficiary account"},
                            "beneficiaryName":  {"type": "string", "description": "Beneficiary full name"},
                            "amount":           {"type": "number", "description": "Payment amount"},
                            "currency":         {"type": "string", "description": "Currency code (default: INR)"},
                            "paymentType":      {"type": "string", "description": "domestic | international | internal"},
                            "urgency":          {"type": "string", "description": "standard | urgent | scheduled"},
                            "reference":        {"type": "string", "description": "Payment reference / narration"},
                            "description":      {"type": "string", "description": "Additional description"},
                        },
                        "required": ["fromAccountId", "amount"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_payment_status",
                    "description": "Retrieve the current status and details of a specific payment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paymentId": {"type": "string", "description": "The payment ID (e.g. PAY-XXXXXXXX)"}
                        },
                        "required": ["paymentId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_payment",
                    "description": "Cancel a pending or held payment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paymentId": {"type": "string", "description": "The payment ID to cancel"},
                            "reason":    {"type": "string", "description": "Reason for cancellation"},
                        },
                        "required": ["paymentId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_payment_history",
                    "description": "Retrieve recent payment history for a user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "userId": {"type": "string", "description": "User ID"},
                            "limit":  {"type": "integer", "description": "Max number of payments to return (default 20)"},
                        },
                        "required": ["userId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_payment_analytics",
                    "description": "Return aggregate analytics across all payments: volume, by-status, by-rail, success rate.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
        ]

        self.tools = {
            "initiate_payment":    self.initiate_payment,
            "get_payment_status":  self.get_payment_status,
            "cancel_payment":      self.cancel_payment,
            "get_payment_history": self.get_payment_history,
            "get_payment_analytics": self.get_payment_analytics,
        }

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}

        user_id  = params.get("userId", "")
        accounts = data_store.get_accounts_by_user_id(user_id) if user_id else []
        recent   = data_store.get_payments_by_user_id(user_id, 5) if user_id else []

        acct_lines = "\n".join(
            f"  • {a['name']} ({a['id']}): ₹{a.get('balance', 0):,.2f} [{a.get('status', 'active')}]"
            for a in accounts
        )
        recent_lines = "\n".join(
            f"  • {p['id']} | ₹{p.get('amount', 0):,.2f} | {p.get('status')} | {p.get('beneficiaryName', 'N/A')} | {p.get('rail', 'N/A')}"
            for p in recent
        )

        context_data = f"""
USER ID: {user_id}
ACCOUNTS:
{acct_lines or '  None'}

RECENT PAYMENTS (last 5):
{recent_lines or '  None'}

PIPELINE: Validate → Screen Sanctions → Route → Execute → Confirm → Reconcile
HITL GATES: Amounts > ₹5,00,000 | SWIFT/international transfers
"""
        return await super().process(session_id, user_message, params, context_data)

    # ─── Tool Implementations ──────────────────────────────────────────────────

    def initiate_payment(self, **params):
        user_id          = params.get("userId", "")
        from_account_id  = params.get("fromAccountId", "")
        to_account_id    = params.get("toAccountId", "")
        beneficiary_name = params.get("beneficiaryName", "Beneficiary")
        amount           = float(params.get("amount", 0))
        currency         = params.get("currency", "INR")
        payment_type     = params.get("paymentType", "domestic")
        urgency          = params.get("urgency", "standard")
        reference        = params.get("reference") or f"REF-{str(uuid.uuid4())[:6].upper()}"
        description      = params.get("description", "Payment initiated via AgenticBank AI")
        bene_account     = params.get("beneficiaryAccount", to_account_id)

        ts = datetime.datetime.utcnow().isoformat() + "Z"

        # ── Stage 0: Create payment record ────────────────────────────────────
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"💳 Initiating payment of ₹{amount:,.2f} to {beneficiary_name}...",
            "timestamp": ts
        })

        payment = data_store.create_payment({
            "userId":           user_id,
            "fromAccountId":    from_account_id,
            "toAccountId":      to_account_id,
            "beneficiaryName":  beneficiary_name,
            "beneficiaryAccount": bene_account,
            "amount":           amount,
            "currency":         currency,
            "paymentType":      payment_type,
            "urgency":          urgency,
            "reference":        reference,
            "description":      description,
            "status":           "processing",
        })
        payment_id = payment["id"]

        # ── Stage 1: Validation ───────────────────────────────────────────────
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"🔍 Stage 1/4 — Starting validation for {payment_id}...",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        validation = payment_validation_agent.validate_payment(
            paymentId=payment_id,
            amount=amount,
            fromAccountId=from_account_id,
            toAccountId=to_account_id,
            paymentType=payment_type,
            currency=currency,
            userId=user_id,
            beneficiaryName=beneficiary_name,
            beneficiaryAccount=bene_account,
        )

        if validation["status"] == "REJECT":
            data_store.update_payment(payment_id, {"status": "rejected", "rejectionReason": validation["reason"]})
            data_store.emit('agent:trace', {
                "agent": self.display_name,
                "content": f"❌ Payment {payment_id} REJECTED: {validation['reason']}",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
            return {
                "success":     False,
                "paymentId":   payment_id,
                "status":      "rejected",
                "reason":      validation["reason"],
                "checks":      validation.get("checks", []),
                "message":     f"Payment rejected: {validation['reason']}",
            }

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"✅ Validation PASSED for {payment_id}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        # ── Stage 2: Routing ──────────────────────────────────────────────────
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"🔀 Stage 2/4 — Routing analysis for {payment_id}...",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        routing = payment_routing_agent.select_payment_rail(
            amount=amount,
            currency=currency,
            urgency=urgency,
            paymentType=payment_type,
        )
        selected_rail = routing.get("rail", "NEFT")
        estimated_fee = routing.get("fees", 0)
        settlement_time = routing.get("estimatedTime", "N/A")

        data_store.update_payment(payment_id, {
            "rail":           selected_rail,
            "estimatedFee":   estimated_fee,
            "settlementTime": settlement_time,
        })

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"🔀 Selected rail: {selected_rail} | Fee: ₹{estimated_fee} | ETA: {settlement_time}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        # ── Stage 3: HITL gate — large amount or SWIFT ────────────────────────
        HITL_THRESHOLD = 500_000  # ₹5,00,000
        needs_approval = amount > HITL_THRESHOLD or selected_rail == "SWIFT" or validation["status"] == "HOLD"

        if needs_approval:
            hold_reason = (
                "SWIFT/international payment requires compliance approval"
                if selected_rail == "SWIFT"
                else f"Amount ₹{amount:,.2f} exceeds ₹5,00,000 HITL threshold"
                if amount > HITL_THRESHOLD
                else validation["reason"]
            )

            approval = data_store.add_approval({
                "type":       "payment_hold",
                "agentName":  self.name,
                "userId":     user_id,
                "details": {
                    "paymentId":       payment_id,
                    "amount":          amount,
                    "currency":        currency,
                    "rail":            selected_rail,
                    "beneficiaryName": beneficiary_name,
                    "reference":       reference,
                },
                "reason": hold_reason,
            })

            data_store.update_payment(payment_id, {
                "status":     "held",
                "approvalId": approval["id"],
                "holdReason": hold_reason,
            })

            data_store.emit('agent:trace', {
                "agent": self.display_name,
                "content": f"✋ Stage 3/4 — Payment {payment_id} routed to HITL approval. {hold_reason}",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })

            return {
                "success":        True,
                "paymentId":      payment_id,
                "status":         "held",
                "requiresApproval": True,
                "approvalId":     approval["id"],
                "rail":           selected_rail,
                "estimatedFee":   estimated_fee,
                "settlementTime": settlement_time,
                "reason":         hold_reason,
                "message":        f"Payment {payment_id} held for human approval. {hold_reason}. Approval ID: {approval['id']}",
            }

        # ── Stage 4: Execute — debit source account ───────────────────────────
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"⚡ Stage 3/4 — Executing payment {payment_id} via {selected_rail}...",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        from_account = data_store.get_account_by_id(from_account_id)
        txn = None
        if from_account:
            txn = data_store.create_transaction({
                "accountId":   from_account_id,
                "userId":      user_id,
                "type":        "debit",
                "amount":      -amount,
                "merchant":    f"Payment to {beneficiary_name}",
                "category":    "Payment",
                "description": f"{selected_rail} payment {payment_id} | {reference}",
                "riskScore":   0.05,
            })

        # ── Stage 5: Confirm ──────────────────────────────────────────────────
        data_store.update_payment(payment_id, {
            "status":          "completed",
            "transactionId":   txn["id"] if txn else None,
            "completedAt":     datetime.datetime.utcnow().isoformat() + "Z",
            "reconciliationStatus": "pending",
        })

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"✅ Stage 4/4 — Payment {payment_id} COMPLETED via {selected_rail}. ₹{amount:,.2f} debited from {from_account_id}.",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        data_store._audit("payment_completed", {
            "paymentId":  payment_id,
            "amount":     amount,
            "rail":       selected_rail,
            "userId":     user_id,
        })

        logger.info(f"Payment completed: {payment_id} | ₹{amount:,.2f} | {selected_rail}", {"agent": self.name})

        return {
            "success":           True,
            "paymentId":         payment_id,
            "status":            "completed",
            "rail":              selected_rail,
            "estimatedFee":      estimated_fee,
            "settlementTime":    settlement_time,
            "transactionId":     txn["id"] if txn else None,
            "amount":            amount,
            "currency":          currency,
            "beneficiaryName":   beneficiary_name,
            "reference":         reference,
            "validationChecks":  validation.get("checks", []),
            "routingReason":     routing.get("reasoning", ""),
            "message":           f"Payment {payment_id} completed via {selected_rail}. ₹{amount:,.2f} sent to {beneficiary_name}. ETA: {settlement_time}. Fee: ₹{estimated_fee}.",
        }

    def get_payment_status(self, **params):
        payment_id = params.get("paymentId", "")
        payment = data_store.get_payment_by_id(payment_id)
        if not payment:
            return {"success": False, "error": f"Payment {payment_id} not found"}
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Payment {payment_id} status: {payment.get('status')} | Rail: {payment.get('rail', 'N/A')}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return {"success": True, "payment": payment}

    def cancel_payment(self, **params):
        payment_id = params.get("paymentId", "")
        reason     = params.get("reason", "Cancelled by user")
        payment    = data_store.get_payment_by_id(payment_id)
        if not payment:
            return {"success": False, "error": f"Payment {payment_id} not found"}

        if payment.get("status") == "completed":
            return {"success": False, "error": f"Payment {payment_id} is already completed and cannot be cancelled"}

        data_store.update_payment(payment_id, {"status": "cancelled", "cancellationReason": reason})

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"🚫 Payment {payment_id} cancelled. Reason: {reason}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        data_store._audit("payment_cancelled", {"paymentId": payment_id, "reason": reason})
        return {
            "success":   True,
            "paymentId": payment_id,
            "status":    "cancelled",
            "reason":    reason,
            "message":   f"Payment {payment_id} has been cancelled. Reason: {reason}",
        }

    def get_payment_history(self, **params):
        user_id = params.get("userId", "")
        limit   = int(params.get("limit", 20))
        payments = data_store.get_payments_by_user_id(user_id, limit)

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Retrieved {len(payments)} payments for user {user_id}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return {
            "userId":   user_id,
            "count":    len(payments),
            "payments": payments,
        }

    def get_payment_analytics(self, **params):
        analytics = data_store.get_payment_analytics()

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Payment analytics: {analytics.get('total')} total payments, ₹{analytics.get('totalVolume', 0):,.2f} volume, {analytics.get('successRate', 0)}% success rate",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return analytics


payment_orchestrator_agent = PaymentOrchestratorAgent()
