import random
import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.utils.logger import logger
from src.ai.prompts import AGENT_PROMPTS

class PaymentValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__('payment_validation', 'Payment Validation Agent', '✅')
        self.use_reasoning = False

        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "validate_payment",
                    "description": "Validate a payment request — checks funds, limits, duplicates, and sanctions. Returns PASS, HOLD, or REJECT.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paymentId":       {"type": "string",  "description": "Internal payment ID"},
                            "amount":          {"type": "number",  "description": "Payment amount in INR"},
                            "fromAccountId":   {"type": "string",  "description": "Source account ID"},
                            "toAccountId":     {"type": "string",  "description": "Destination account ID"},
                            "paymentType":     {"type": "string",  "description": "domestic | international"},
                            "currency":        {"type": "string",  "description": "Currency code, e.g. INR"},
                        },
                        "required": ["paymentId", "amount", "fromAccountId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_duplicate",
                    "description": "Scan the last 60 seconds of payments for a duplicate with the same fromAccount, amount, and beneficiary.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fromAccountId":  {"type": "string", "description": "Source account ID"},
                            "amount":         {"type": "number", "description": "Payment amount"},
                            "beneficiaryId":  {"type": "string", "description": "Beneficiary account or ID"},
                        },
                        "required": ["fromAccountId", "amount"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_velocity_limits",
                    "description": "Count payments made by a user in the last 24 hours and flag if the velocity limit is exceeded.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "userId": {"type": "string", "description": "The user's ID"},
                        },
                        "required": ["userId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "screen_sanctions",
                    "description": "Screen a beneficiary name and account against sanctions / watchlists.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "beneficiaryName":    {"type": "string", "description": "Beneficiary full name"},
                            "beneficiaryAccount": {"type": "string", "description": "Beneficiary account number"},
                        },
                        "required": ["beneficiaryName"]
                    }
                }
            },
        ]

        self.tools = {
            "validate_payment":    self.validate_payment,
            "check_duplicate":     self.check_duplicate,
            "check_velocity_limits": self.check_velocity_limits,
            "screen_sanctions":    self.screen_sanctions,
        }

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}

        user_id = params.get("userId", "")
        accounts = data_store.get_accounts_by_user_id(user_id) if user_id else []
        recent_payments = data_store.get_payments_by_user_id(user_id, 20) if user_id else []

        accounts_str = ", ".join(
            f"{a['name']} ({a['id']}): ₹{a.get('balance', 0):,.2f}"
            for a in accounts
        )

        context_data = f"""
USER ID: {user_id}
ACCOUNTS: {accounts_str or 'N/A'}
RECENT PAYMENTS (last 20): {len(recent_payments)}

Validation rules:
- Per-transaction max: ₹50,00,000
- Daily aggregate limit: ₹2,00,00,000
- Max payments per day: 10 (velocity limit)
- Duplicate window: 60 seconds (same amount + beneficiary)
- Sanctions: block any watchlist hit immediately"""

        return await super().process(session_id, user_message, params, context_data)

    # ─── Tool Implementations ──────────────────────────────────────────────────

    def validate_payment(self, **params):
        payment_id    = params.get("paymentId", "UNKNOWN")
        amount        = float(params.get("amount", 0))
        from_acct_id  = params.get("fromAccountId", "")
        to_acct_id    = params.get("toAccountId", "")
        payment_type  = params.get("paymentType", "domestic")
        currency      = params.get("currency", "INR")
        user_id       = params.get("userId", "")
        beneficiary   = params.get("beneficiaryName", "")
        bene_account  = params.get("beneficiaryAccount", "")

        checks = []
        overall_status = "PASS"
        reject_reason = None

        # ── 1. Funds availability ──────────────────────────────────────────────
        from_account = data_store.get_account_by_id(from_acct_id)
        if not from_account:
            checks.append({"check": "funds_availability", "status": "REJECT", "detail": f"Source account {from_acct_id} not found"})
            overall_status = "REJECT"
            reject_reason = f"Source account {from_acct_id} not found"
        else:
            balance = float(from_account.get("balance", 0))
            if balance < amount:
                checks.append({"check": "funds_availability", "status": "REJECT", "detail": f"Insufficient funds. Balance ₹{balance:,.2f}, required ₹{amount:,.2f}"})
                overall_status = "REJECT"
                reject_reason = f"Insufficient funds (balance ₹{balance:,.2f})"
            else:
                checks.append({"check": "funds_availability", "status": "PASS", "detail": f"Balance ₹{balance:,.2f} is sufficient"})

        # ── 2. Per-transaction limit ───────────────────────────────────────────
        MAX_TXN = 5_000_000  # ₹50,00,000
        if amount > MAX_TXN:
            checks.append({"check": "per_txn_limit", "status": "REJECT", "detail": f"Amount ₹{amount:,.2f} exceeds per-transaction limit of ₹{MAX_TXN:,.2f}"})
            overall_status = "REJECT"
            reject_reason = reject_reason or f"Exceeds per-transaction limit ₹50,00,000"
        else:
            checks.append({"check": "per_txn_limit", "status": "PASS", "detail": f"Amount ₹{amount:,.2f} is within per-transaction limit"})

        # ── 3. Daily aggregate limit ───────────────────────────────────────────
        MAX_DAILY = 20_000_000  # ₹2,00,00,000
        if user_id:
            now = datetime.datetime.utcnow()
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            user_payments = data_store.get_payments_by_user_id(user_id, 200)
            daily_total = sum(
                float(p.get("amount", 0))
                for p in user_payments
                if p.get("status") not in ("cancelled", "failed", "rejected")
                and p.get("createdAt", "") >= day_start.isoformat()
            )
            if daily_total + amount > MAX_DAILY:
                checks.append({"check": "daily_limit", "status": "HOLD", "detail": f"Daily limit ₹{MAX_DAILY:,.2f} would be exceeded (current ₹{daily_total:,.2f})"})
                if overall_status == "PASS":
                    overall_status = "HOLD"
            else:
                checks.append({"check": "daily_limit", "status": "PASS", "detail": f"Daily usage ₹{daily_total:,.2f} of ₹{MAX_DAILY:,.2f}"})

        # ── 4. Duplicate detection ─────────────────────────────────────────────
        dup_result = self.check_duplicate(
            fromAccountId=from_acct_id,
            amount=amount,
            beneficiaryId=to_acct_id or bene_account,
        )
        if dup_result.get("isDuplicate"):
            checks.append({"check": "duplicate_detection", "status": "REJECT", "detail": dup_result.get("detail")})
            overall_status = "REJECT"
            reject_reason = reject_reason or "Duplicate payment detected within 60 seconds"
        else:
            checks.append({"check": "duplicate_detection", "status": "PASS", "detail": "No duplicate found in last 60 seconds"})

        # ── 5. Sanctions screening ─────────────────────────────────────────────
        if beneficiary:
            sanctions = self.screen_sanctions(beneficiaryName=beneficiary, beneficiaryAccount=bene_account or "")
            if sanctions.get("hit"):
                checks.append({"check": "sanctions_screen", "status": "REJECT", "detail": f"Sanctions hit: {sanctions.get('details')}"})
                overall_status = "REJECT"
                reject_reason = reject_reason or "Sanctions/watchlist hit detected"
            else:
                checks.append({"check": "sanctions_screen", "status": "PASS", "detail": "No sanctions hits"})

        reason = reject_reason if overall_status == "REJECT" else (
            "Daily velocity limit exceeded — requires senior approval" if overall_status == "HOLD"
            else "All validation checks passed"
        )

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Validation result for {payment_id}: {overall_status} — {reason}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        logger.info(f"Payment validation: {payment_id} → {overall_status}", {"agent": self.name})

        return {
            "status":  overall_status,
            "reason":  reason,
            "checks":  checks,
            "paymentId": payment_id,
        }

    def check_duplicate(self, **params):
        from_acct = params.get("fromAccountId", "")
        amount    = float(params.get("amount", 0))
        bene_id   = params.get("beneficiaryId", "")

        now = datetime.datetime.utcnow()
        window_start = (now - datetime.timedelta(seconds=60)).isoformat()

        all_payments = data_store.payments
        for p in all_payments:
            if p.get("status") in ("cancelled", "failed", "rejected"):
                continue
            if p.get("fromAccountId") != from_acct:
                continue
            if abs(float(p.get("amount", 0)) - amount) > 0.01:
                continue
            if p.get("createdAt", "") < window_start:
                continue
            # Beneficiary check — loose: either toAccountId or beneficiaryAccount
            if bene_id and p.get("toAccountId") != bene_id and p.get("beneficiaryAccount") != bene_id:
                continue

            data_store.emit('agent:trace', {
                "agent": self.display_name,
                "content": f"⚠️ Duplicate detected: payment {p['id']} matches amount ₹{amount:,.2f} to same beneficiary within 60s",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
            return {
                "isDuplicate": True,
                "duplicatePaymentId": p["id"],
                "detail": f"Duplicate of payment {p['id']} (same amount ₹{amount:,.2f} to same beneficiary within 60 seconds)"
            }

        return {"isDuplicate": False, "detail": "No duplicate found"}

    def check_velocity_limits(self, **params):
        user_id = params.get("userId", "")
        if not user_id:
            return {"status": "PASS", "count": 0, "limit": 10, "detail": "No userId provided"}

        now = datetime.datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        user_payments = data_store.get_payments_by_user_id(user_id, 200)
        today_count = sum(
            1 for p in user_payments
            if p.get("status") not in ("cancelled", "failed", "rejected")
            and p.get("createdAt", "") >= day_start
        )

        MAX_PER_DAY = 10
        status = "HOLD" if today_count >= MAX_PER_DAY else "PASS"

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Velocity check for user {user_id}: {today_count}/{MAX_PER_DAY} payments today → {status}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return {
            "status":  status,
            "count":   today_count,
            "limit":   MAX_PER_DAY,
            "detail":  f"{today_count} payments today (limit {MAX_PER_DAY})" + (
                " — velocity limit reached, routing to HOLD" if status == "HOLD" else ""
            )
        }

    def screen_sanctions(self, **params):
        beneficiary_name    = params.get("beneficiaryName", "")
        beneficiary_account = params.get("beneficiaryAccount", "")

        # 5% random demo hit to simulate a real sanctions engine
        is_hit = random.random() < 0.05

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Sanctions screen for '{beneficiary_name}' ({beneficiary_account or 'N/A'}): {'⛔ HIT' if is_hit else '✅ CLEAR'}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return {
            "screened": True,
            "hit":      is_hit,
            "details":  (
                f"OFAC/UN watchlist match for '{beneficiary_name}' — payment blocked pending compliance review"
                if is_hit
                else f"No watchlist matches found for '{beneficiary_name}'"
            )
        }


payment_validation_agent = PaymentValidationAgent()
