import math
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.utils.validators import format_currency

class LoanAgent(BaseAgent):
    def __init__(self):
        super().__init__('loan', 'Loan & Credit Agent', '🏦')
        self.use_reasoning = True
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "calculate_emi",
                    "description": "Calculate the Equated Monthly Installment (EMI) for a loan.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Loan amount"},
                            "rate": {"type": "number", "description": "Annual interest rate (e.g. 5.5 for 5.5%)"},
                            "termMonths": {"type": "number", "description": "Loan term in months"}
                        },
                        "required": ["amount", "rate", "termMonths"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_loan_application",
                    "description": "Submit a loan application for human review and approval.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Requested loan amount"},
                            "purpose": {"type": "string", "description": "Purpose of the loan"},
                            "termMonths": {"type": "number", "description": "Requested term in months"},
                            "type": {"type": "string", "enum": ["personal", "mortgage", "auto", "business"], "description": "Type of loan"}
                        },
                        "required": ["amount", "purpose", "termMonths", "type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "alert_banker",
                    "description": "Send a high-priority alert directly to the banker dashboard regarding a loan query.",
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
            "calculate_emi": self.calculate_emi_tool,
            "submit_loan_application": self.submit_loan_application,
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
        existing_loans = data_store.get_loans_by_user_id(user_id)
        accounts = data_store.get_accounts_by_user_id(user_id)
        
        total_debt = sum(l["remainingBalance"] for l in existing_loans if l["status"] == "active")
        
        annual_income = float(user.get("annualIncome", 0))
        monthly_income = annual_income / 12.0 if annual_income > 0 else 1.0
        
        # Calculate Debt to Income ratio
        dti = ((total_debt / 12.0) / monthly_income * 100.0)
        dti_str = f"{dti:.1f}"

        loans_list_str = ""
        if existing_loans:
            loans_list_str = "\n".join(
                f"  - {l['id']} | {l['type']} | {format_currency(l['amount'])} | Remaining: {format_currency(l['remainingBalance'])} | Rate: {l['interestRate']}% | Status: {l['status']}"
                for l in existing_loans
            )
        else:
            loans_list_str = "  None"

        context_data = f"""
USER: {user['firstName']} {user['lastName']} | Credit Score: {user['creditScore']} | Annual Income: {format_currency(user['annualIncome'])}
DEBT-TO-INCOME RATIO: {dti_str}%
EXISTING LOANS:
{loans_list_str}"""

        return await super().process(session_id, user_message, params, context_data)

    def calculate_emi_tool(self, **params):
        amount = float(params.get("amount", 0))
        rate = float(params.get("rate", 0))
        term_months = int(params.get("termMonths", 12))
        
        P = amount
        r = (rate / 100.0) / 12.0
        n = term_months
        
        if r == 0:
            emi = P / n
        else:
            emi = P * r * math.pow(1 + r, n) / (math.pow(1 + r, n) - 1)
            
        total_payment = emi * n
        total_interest = total_payment - P

        return {
            "loanAmount": P,
            "interestRate": rate,
            "termMonths": n,
            "monthlyEMI": emi,
            "totalPayment": total_payment,
            "totalInterest": total_interest
        }

    def submit_loan_application(self, **params):
        amount = float(params.get("amount", 0))
        purpose = params.get("purpose")
        term_months = int(params.get("termMonths", 60))
        loan_type = params.get("type", "personal")
        user_id = params.get("userId")

        user = data_store.get_user_by_id(user_id)
        rate = self.estimate_rate(user.get("creditScore", 700), loan_type)
        monthly_payment = self.calc_emi(amount, rate, term_months)

        loan = data_store.create_loan(
            user_id=user_id,
            type_val=loan_type,
            amount=amount,
            purpose=purpose,
            term_months=term_months,
            interest_rate=rate,
            monthly_payment=monthly_payment
        )

        approval = data_store.add_approval({
            "type": 'loan_application',
            "agentName": self.name,
            "userId": user_id,
            "details": {
                "loanId": loan["id"],
                "amount": amount,
                "rate": rate,
                "termMonths": term_months,
                "purpose": purpose,
                "creditScore": user.get("creditScore")
            },
            "reason": 'All loan applications require human review',
        })

        return {
            "success": True,
            "requiresApproval": True,
            "approvalId": approval["id"],
            "applicationId": loan["id"],
            "estimatedRate": rate,
            "estimatedEMI": loan["monthlyPayment"],
            "message": f"Loan application submitted successfully. It is pending human approval. Approval ID: {approval['id']}"
        }

    def alert_banker(self, **params):
        import datetime
        data_store.emit('agent:alert', {
            "agent": self.display_name,
            "userId": params.get("userId"),
            "message": params.get("message"),
            "severity": params.get("severity"),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return {"success": True, "message": "Alert sent to banker dashboard."}

    def estimate_rate(self, credit_score, loan_type):
        base = 6.0 if loan_type == 'mortgage' else 5.5 if loan_type == 'auto' else 7.0 if loan_type == 'business' else 8.0
        if credit_score >= 750:
            base -= 1.5
        elif credit_score >= 700:
            base -= 0.75
        elif credit_score < 650:
            base += 2.0
        return round(max(base, 3.5), 2)

    def calc_emi(self, P, rate, n):
        r = (rate / 100.0) / 12.0
        if r == 0:
            return round(P / n, 2)
        return round(P * r * math.pow(1 + r, n) / (math.pow(1 + r, n) - 1), 2)

loan_agent = LoanAgent()
