import datetime
from collections import Counter
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.utils.logger import logger
from src.ai.prompts import AGENT_PROMPTS


class PaymentReconciliationAgent(BaseAgent):
    def __init__(self):
        super().__init__('payment_reconciliation', 'Payment Reconciliation Agent', '🔁')
        self.use_reasoning = False

        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "reconcile_payment",
                    "description": "Reconcile a payment by matching the outbound instruction against the settlement record.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paymentId": {"type": "string", "description": "The payment ID to reconcile"}
                        },
                        "required": ["paymentId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "flag_exception",
                    "description": "Flag a payment as a reconciliation exception and emit an alert for human review.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paymentId":     {"type": "string", "description": "Payment ID"},
                            "reason":        {"type": "string", "description": "Reason for the exception"},
                            "exceptionType": {
                                "type": "string",
                                "enum": ["TIMING", "AMOUNT", "MISSING", "DUPLICATE"],
                                "description": "Classification of the reconciliation exception"
                            },
                        },
                        "required": ["paymentId", "reason", "exceptionType"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_reconciliation_summary",
                    "description": "Return aggregate counts of matched, unmatched, exception, and pending payments.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_reconciliation_report",
                    "description": "Generate a reconciliation report for a specific date, broken down by rail and status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "ISO date string YYYY-MM-DD (defaults to today)"}
                        }
                    }
                }
            },
        ]

        self.tools = {
            "reconcile_payment":           self.reconcile_payment,
            "flag_exception":              self.flag_exception,
            "get_reconciliation_summary":  self.get_reconciliation_summary,
            "generate_reconciliation_report": self.generate_reconciliation_report,
        }

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}

        summary = self.get_reconciliation_summary()
        context_data = f"""
CURRENT RECONCILIATION STATUS:
  Matched:    {summary['matched']}
  Unmatched:  {summary['unmatched']}
  Exceptions: {summary['exceptions']}
  Pending:    {summary['pending']}
  Total:      {summary['total']}

Exception types: TIMING (late settlement), AMOUNT (mismatch), MISSING (no settlement), DUPLICATE (double settlement).
All exceptions route to banker HITL queue for resolution."""

        return await super().process(session_id, user_message, params, context_data)

    # ─── Tool Implementations ──────────────────────────────────────────────────

    def reconcile_payment(self, **params):
        payment_id = params.get("paymentId", "")
        payment = data_store.get_payment_by_id(payment_id)

        if not payment:
            return {"success": False, "error": f"Payment {payment_id} not found"}

        status = payment.get("status", "processing")

        # Simulate reconciliation matching logic
        if status == "completed":
            # 90% chance of a clean match for completed payments
            import random
            is_matched = random.random() > 0.1
            if is_matched:
                match_result = "MATCHED"
                data_store.update_payment(payment_id, {"reconciliationStatus": "reconciled"})
                detail = f"Payment {payment_id} successfully matched to settlement record. Amount ₹{payment.get('amount', 0):,.2f} confirmed."
            else:
                match_result = "EXCEPTION"
                data_store.update_payment(payment_id, {"reconciliationStatus": "exception"})
                detail = f"Settlement amount mismatch detected for {payment_id}. Routing to exception queue."
                self.flag_exception(paymentId=payment_id, reason="Amount mismatch in settlement", exceptionType="AMOUNT")
        elif status == "processing":
            match_result = "PENDING"
            detail = f"Payment {payment_id} is still processing — settlement not yet received."
        elif status in ("failed", "rejected"):
            match_result = "FAILED"
            detail = f"Payment {payment_id} has status '{status}' — no settlement expected."
        elif status == "held":
            match_result = "HELD"
            detail = f"Payment {payment_id} is on hold pending human approval — reconciliation deferred."
        else:
            match_result = "UNKNOWN"
            detail = f"Unrecognised status '{status}' for payment {payment_id}."

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Reconciliation: {payment_id} → {match_result}. {detail}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        logger.info(f"Reconciliation: {payment_id} → {match_result}", {"agent": self.name})

        return {
            "paymentId":    payment_id,
            "matchResult":  match_result,
            "detail":       detail,
            "amount":       payment.get("amount"),
            "rail":         payment.get("rail"),
            "status":       payment.get("status"),
        }

    def flag_exception(self, **params):
        payment_id     = params.get("paymentId", "")
        reason         = params.get("reason", "Unspecified exception")
        exception_type = params.get("exceptionType", "MISSING")

        data_store.update_payment(payment_id, {
            "reconciliationStatus": "exception",
            "exceptionType":        exception_type,
            "exceptionReason":      reason,
        })

        data_store.emit('agent:alert', {
            "agent":     self.display_name,
            "userId":    None,
            "message":   f"Reconciliation exception [{exception_type}] on payment {payment_id}: {reason}",
            "severity":  "high",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        data_store.emit('agent:trace', {
            "agent":     self.display_name,
            "content":   f"⚠️ Exception flagged [{exception_type}] for payment {payment_id}: {reason}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        data_store._audit("payment_exception_flagged", {
            "paymentId":     payment_id,
            "exceptionType": exception_type,
            "reason":        reason,
        })

        return {
            "success":       True,
            "paymentId":     payment_id,
            "exceptionType": exception_type,
            "reason":        reason,
            "message":       f"Exception [{exception_type}] flagged for payment {payment_id}. Routed to banker review queue.",
        }

    def get_reconciliation_summary(self, **params):
        all_payments = data_store.payments
        total     = len(all_payments)
        matched   = sum(1 for p in all_payments if p.get("reconciliationStatus") == "reconciled")
        exception = sum(1 for p in all_payments if p.get("reconciliationStatus") == "exception")
        pending   = sum(1 for p in all_payments if p.get("status") in ("processing", "held"))
        unmatched = total - matched - exception - pending

        data_store.emit('agent:trace', {
            "agent":     self.display_name,
            "content":   f"Reconciliation summary: {matched} matched, {unmatched} unmatched, {exception} exceptions, {pending} pending of {total} total",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return {
            "total":      total,
            "matched":    matched,
            "unmatched":  max(unmatched, 0),
            "exceptions": exception,
            "pending":    pending,
        }

    def generate_reconciliation_report(self, **params):
        target_date = params.get("date") or datetime.datetime.utcnow().strftime("%Y-%m-%d")
        all_payments = data_store.payments

        day_payments = [
            p for p in all_payments
            if p.get("createdAt", "").startswith(target_date)
        ]

        by_rail   = dict(Counter(p.get("rail", "unknown") for p in day_payments if p.get("rail")))
        by_status = dict(Counter(p.get("status", "unknown") for p in day_payments))
        total_vol = sum(float(p.get("amount", 0)) for p in day_payments)

        report = {
            "date":          target_date,
            "totalPayments": len(day_payments),
            "totalVolume":   round(total_vol, 2),
            "byRail":        by_rail,
            "byStatus":      by_status,
            "exceptions":    [
                {
                    "paymentId":     p["id"],
                    "amount":        p.get("amount"),
                    "exceptionType": p.get("exceptionType"),
                    "reason":        p.get("exceptionReason"),
                }
                for p in day_payments
                if p.get("reconciliationStatus") == "exception"
            ],
        }

        data_store.emit('agent:trace', {
            "agent":     self.display_name,
            "content":   f"Reconciliation report for {target_date}: {len(day_payments)} payments, ₹{total_vol:,.2f} volume",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return report


payment_reconciliation_agent = PaymentReconciliationAgent()
