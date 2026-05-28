import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store

class ComplianceAgent(BaseAgent):
    def __init__(self):
        super().__init__('compliance', 'Compliance Agent', '📋')
        self.use_reasoning = True
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "verify_kyc",
                    "description": "Perform a Know Your Customer (KYC) verification check on the user.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "aml_check",
                    "description": "Perform an Anti-Money Laundering (AML) screening on the user's transactions.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "alert_banker",
                    "description": "Send a high-priority alert directly to the banker dashboard regarding compliance failures or SAR filing.",
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
            "verify_kyc": self.verify_kyc,
            "aml_check": self.aml_check,
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
        accounts = data_store.get_accounts_by_user_id(user_id)
        txns = data_store.get_transactions_by_user_id(user_id, 50)

        # AML indicators
        large_txns = [t for t in txns if abs(t.get("amount", 0)) > 500000]
        structuring = self.detect_structuring(txns)
        rapid_movement = len([t for t in txns if t.get("category") == 'Transfer' and abs(t.get("amount", 0)) > 100000])

        # KYC expiry (1 year check)
        kyc_date_str = user.get("kycDate")
        kyc_expiry_status = 'NOT VERIFIED ⚠️'
        if kyc_date_str:
            try:
                kyc_dt = datetime.datetime.strptime(kyc_date_str, "%Y-%m-%d")
                one_year_ago = datetime.datetime.utcnow() - datetime.timedelta(days=365)
                if kyc_dt < one_year_ago:
                    kyc_expiry_status = 'EXPIRED ⚠️'
                else:
                    kyc_expiry_status = 'Valid'
            except Exception:
                kyc_expiry_status = 'Valid'

        has_flagged_accounts = len([a for a in accounts if a.get("status") != 'active']) > 0
        account_flags_str = 'HAS FLAGGED ACCOUNTS' if has_flagged_accounts else 'All clear'

        context_data = f"""
USER: {user['firstName']} {user['lastName']} ({user_id})
KYC STATUS: {user.get('kycStatus')} | KYC DATE: {kyc_date_str or 'N/A'}
OCCUPATION: {user.get('occupation')} | EMPLOYER: {user.get('employer')}
ANNUAL INCOME: ₹{user.get('annualIncome', 0):,}
SSN (masked): {user.get('ssn')}

COMPLIANCE FLAGS:
  - Large transactions (>₹5,00,000): {len(large_txns)}
  - Potential structuring detected: {'YES ⚠️' if structuring else 'NO'}
  - Rapid fund movements (>₹1,00,000 transfers): {rapid_movement}
  - KYC expiry: {kyc_expiry_status}
  - Account status flags: {account_flags_str}

Note: Use alert_banker if you detect structuring or severe KYC issues."""

        return await super().process(session_id, user_message, params, context_data)

    def detect_structuring(self, transactions):
        suspicious = [
            t for t in transactions
            if 400000 <= abs(t.get("amount", 0)) < 500000
        ]
        return len(suspicious) >= 3

    def verify_kyc(self, **params):
        user_id = params.get("userId")
        user = data_store.get_user_by_id(user_id)
        
        checks = {
            "identity": 'VERIFIED ✅' if user.get("ssn") else 'MISSING ❌',
            "address": 'VERIFIED ✅' if user.get("address") else 'MISSING ❌',
            "employment": 'VERIFIED ✅' if user.get("employer") else 'MISSING ❌',
            "income": 'VERIFIED ✅' if float(user.get("annualIncome", 0)) > 0 else 'UNVERIFIED ⚠️',
            "status": user.get("kycStatus"),
        }

        if user.get("kycStatus") == 'flagged':
            approval = data_store.add_approval({
                "type": 'kyc_review',
                "agentName": self.name,
                "userId": user_id,
                "details": checks,
                "reason": 'Flagged KYC requires compliance officer review',
            })

            return {
                "success": False,
                "requiresApproval": True,
                "approvalId": approval["id"],
                "message": 'KYC is flagged and has been escalated to a compliance officer for manual review.',
                "checks": checks
            }

        return {
            "success": True,
            "checks": checks,
            "lastVerified": user.get("kycDate") or 'Never'
        }

    def aml_check(self, **params):
        user_id = params.get("userId")
        txns = data_store.get_transactions_by_user_id(user_id, 50)
        large_txns = [t for t in txns if abs(t.get("amount", 0)) > 500000]
        structuring = self.detect_structuring(txns)
        
        risk_level = 'HIGH' if structuring else 'MEDIUM' if len(large_txns) > 3 else 'LOW'

        return {
            "riskLevel": risk_level,
            "structuringDetected": structuring,
            "largeTransactionsCount": len(large_txns),
            "regulatoryReportingRequired": len(large_txns) > 0,
            "sarFilingRecommended": risk_level == 'HIGH'
        }

    def alert_banker(self, **params):
        data_store.emit('agent:alert', {
            "agent": self.display_name,
            "userId": params.get("userId"),
            "message": params.get("message"),
            "severity": params.get("severity"),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return {"success": True, "message": "Alert sent to banker dashboard."}

compliance_agent = ComplianceAgent()
