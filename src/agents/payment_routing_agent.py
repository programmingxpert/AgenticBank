import random
import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.utils.logger import logger
from src.ai.prompts import AGENT_PROMPTS

# ─── Rail Configuration ──────────────────────────────────────────────────────
RAILS = {
    "UPI": {
        "maxAmount":       100_000,
        "currencies":      ["INR"],
        "settlementTime":  "Instant (<10s)",
        "fee":             0,
        "feeType":         "flat",
        "description":     "Unified Payments Interface — real-time domestic payments",
        "availability":    "24x7",
    },
    "IMPS": {
        "maxAmount":       500_000,
        "currencies":      ["INR"],
        "settlementTime":  "Instant (<30s)",
        "fee":             5,
        "feeType":         "flat_plus_gst",
        "description":     "Immediate Payment Service — 24x7 real-time domestic",
        "availability":    "24x7",
    },
    "NEFT": {
        "maxAmount":       None,    # unlimited
        "currencies":      ["INR"],
        "settlementTime":  "30 minutes (batch)",
        "feeType":         "slab",
        "description":     "National Electronic Funds Transfer — batch settlement every 30 min",
        "availability":    "24x7",
    },
    "RTGS": {
        "minAmount":       200_000,
        "maxAmount":       None,
        "currencies":      ["INR"],
        "settlementTime":  "Real-time (30 min cutoff)",
        "feeType":         "slab_rtgs",
        "description":     "Real-Time Gross Settlement — high-value real-time domestic",
        "availability":    "Business hours",
    },
    "SWIFT": {
        "maxAmount":       None,
        "currencies":      ["USD", "EUR", "GBP", "AED", "SGD", "JPY", "AUD", "CAD", "CHF"],
        "settlementTime":  "1-3 business days",
        "feeType":         "swift",
        "description":     "Society for Worldwide Interbank Financial Telecommunication — cross-border wire",
        "availability":    "Business days",
    },
    "Internal": {
        "maxAmount":       None,
        "currencies":      ["INR"],
        "settlementTime":  "Instant",
        "fee":             0,
        "feeType":         "flat",
        "description":     "Internal AgenticBank transfer — same-bank accounts",
        "availability":    "24x7",
    },
}


class PaymentRoutingAgent(BaseAgent):
    def __init__(self):
        super().__init__('payment_routing', 'Payment Routing Agent', '🔀')
        self.use_reasoning = False

        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "select_payment_rail",
                    "description": "Select the optimal payment rail (UPI/IMPS/NEFT/RTGS/SWIFT/Internal) for a given payment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount":      {"type": "number",  "description": "Payment amount in source currency"},
                            "currency":    {"type": "string",  "description": "Currency code (INR, USD, etc.)"},
                            "urgency":     {"type": "string",  "description": "standard | urgent | scheduled"},
                            "paymentType": {"type": "string",  "description": "domestic | international | internal"},
                        },
                        "required": ["amount", "currency", "paymentType"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "estimate_fees",
                    "description": "Estimate the processing fee for a payment on a given rail.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Payment amount in INR"},
                            "rail":   {"type": "string", "description": "Payment rail name"},
                        },
                        "required": ["amount", "rail"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "estimate_settlement_time",
                    "description": "Return the expected settlement time for a given payment rail.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rail": {"type": "string", "description": "Payment rail name"}
                        },
                        "required": ["rail"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_network_status",
                    "description": "Check current operational status of a payment network/rail.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rail": {"type": "string", "description": "Payment rail name"}
                        },
                        "required": ["rail"]
                    }
                }
            },
        ]

        self.tools = {
            "select_payment_rail":    self.select_payment_rail,
            "estimate_fees":          self.estimate_fees,
            "estimate_settlement_time": self.estimate_settlement_time,
            "check_network_status":   self.check_network_status,
        }

    async def process(self, session_id, user_message, params=None, context_data=''):
        if params is None:
            params = {}

        context_data = """
RAIL MATRIX:
| Rail     | Limit   | Speed           | Fee        | Scope        |
|----------|---------|-----------------|------------|--------------|
| UPI      | ₹1L     | Instant <10s    | Free       | Domestic     |
| IMPS     | ₹5L     | Instant <30s    | ₹5+GST     | Domestic 24x7|
| NEFT     | No cap  | 30-min batch    | ₹2-25      | Domestic     |
| RTGS     | ₹2L+    | Real-time       | ₹25-50     | Domestic HV  |
| SWIFT    | No cap  | 1-3 days        | ₹500-2000  | International|
| Internal | No cap  | Instant         | Free       | Same-bank    |

Routing priority: UPI > IMPS > NEFT > RTGS (domestic) / SWIFT (international) / Internal (same-bank)
"""
        return await super().process(session_id, user_message, params, context_data)

    # ─── Tool Implementations ──────────────────────────────────────────────────

    def select_payment_rail(self, **params):
        amount       = float(params.get("amount", 0))
        currency     = params.get("currency", "INR").upper()
        urgency      = params.get("urgency", "standard").lower()
        payment_type = params.get("paymentType", "domestic").lower()

        rail = None
        reasoning = []

        # ── International ──────────────────────────────────────────────────────
        if payment_type == "international" or currency != "INR":
            rail = "SWIFT"
            reasoning.append(f"Cross-border/international payment in {currency} → SWIFT is the only viable rail")

        # ── Internal same-bank ─────────────────────────────────────────────────
        elif payment_type == "internal":
            rail = "Internal"
            reasoning.append("Same-bank internal transfer → Internal rail (instant, zero fee)")

        # ── Domestic selection ─────────────────────────────────────────────────
        else:
            if amount < 100_000:
                rail = "UPI"
                reasoning.append(f"Amount ₹{amount:,.2f} < ₹1,00,000 → UPI (free, instant)")
            elif amount < 500_000:
                rail = "IMPS"
                reasoning.append(f"Amount ₹{amount:,.2f} < ₹5,00,000 → IMPS (24x7, near-instant)")
            elif amount >= 200_000 and urgency == "urgent":
                rail = "RTGS"
                reasoning.append(f"Amount ₹{amount:,.2f} ≥ ₹2,00,000 and urgency='{urgency}' → RTGS (real-time gross settlement)")
            else:
                rail = "NEFT"
                reasoning.append(f"Amount ₹{amount:,.2f} → NEFT (batch settlement, lower fee, no cap)")

        fee = self.estimate_fees(amount=amount, rail=rail)
        settlement = self.estimate_settlement_time(rail=rail)
        network = self.check_network_status(rail=rail)

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Rail selected: {rail} for ₹{amount:,.2f} ({payment_type}, {urgency}). Fee: ₹{fee['fee']}. ETA: {settlement['estimatedTime']}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        logger.info(f"Payment routing: ₹{amount:,.2f} → {rail}", {"agent": self.name})

        return {
            "rail":            rail,
            "estimatedTime":   settlement["estimatedTime"],
            "fees":            fee["fee"],
            "feeBreakdown":    fee.get("breakdown", ""),
            "reasoning":       " ".join(reasoning),
            "networkStatus":   network.get("status"),
            "railDescription": RAILS.get(rail, {}).get("description", ""),
        }

    def estimate_fees(self, **params):
        amount = float(params.get("amount", 0))
        rail   = params.get("rail", "NEFT")

        if rail == "UPI" or rail == "Internal":
            fee = 0
            breakdown = "Free — no processing fee"
        elif rail == "IMPS":
            base = 5
            gst  = round(base * 0.18, 2)
            fee  = round(base + gst, 2)
            breakdown = f"Base ₹{base} + GST ₹{gst} = ₹{fee}"
        elif rail == "NEFT":
            if amount <= 10_000:
                fee = 2
            elif amount <= 100_000:
                fee = 5
            elif amount <= 200_000:
                fee = 15
            else:
                fee = 25
            gst = round(fee * 0.18, 2)
            fee = round(fee + gst, 2)
            breakdown = f"NEFT slab fee ₹{fee - gst} + GST ₹{gst} = ₹{fee}"
        elif rail == "RTGS":
            if amount <= 500_000:
                fee = 25
            else:
                fee = 50
            gst = round(fee * 0.18, 2)
            fee = round(fee + gst, 2)
            breakdown = f"RTGS slab fee ₹{fee - gst} + GST ₹{gst} = ₹{fee}"
        elif rail == "SWIFT":
            if amount <= 500_000:
                fee = 500
            elif amount <= 2_000_000:
                fee = 1000
            else:
                fee = 2000
            gst = round(fee * 0.18, 2)
            fee = round(fee + gst, 2)
            breakdown = f"SWIFT wire fee ₹{fee - gst} + GST ₹{gst} = ₹{fee}"
        else:
            fee = 0
            breakdown = "No fee data"

        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Fee estimate for {rail}: ₹{fee} ({breakdown})",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        return {"rail": rail, "fee": fee, "breakdown": breakdown}

    def estimate_settlement_time(self, **params):
        rail = params.get("rail", "NEFT")
        times = {
            "UPI":      "Instant (<10s)",
            "IMPS":     "Instant (<30s)",
            "NEFT":     "30 minutes (batch)",
            "RTGS":     "Real-time (30 min cutoff)",
            "SWIFT":    "1-3 business days",
            "Internal": "Instant",
        }
        estimated = times.get(rail, "Unknown")
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Settlement time for {rail}: {estimated}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return {"rail": rail, "estimatedTime": estimated}

    def check_network_status(self, **params):
        rail = params.get("rail", "NEFT")
        # 99% uptime simulation — 1% random degradation
        is_degraded = random.random() < 0.01
        status      = "DEGRADED" if is_degraded else "OPERATIONAL"
        message     = (
            f"{rail} network is experiencing degraded performance. Consider an alternative rail."
            if is_degraded
            else f"{rail} network is fully operational."
        )
        data_store.emit('agent:trace', {
            "agent": self.display_name,
            "content": f"Network status {rail}: {status}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return {"rail": rail, "status": status, "message": message}


payment_routing_agent = PaymentRoutingAgent()
