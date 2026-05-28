import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store
from src.config import config
from src.utils.validators import format_currency

class InvestmentAgent(BaseAgent):
    def __init__(self):
        super().__init__('investment', 'Investment Advisory Agent', '📈')
        self.use_reasoning = True
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "execute_trade",
                    "description": "Execute a stock trade (buy or sell) for the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "The stock symbol (e.g. AAPL, TSLA)"},
                            "action": {"type": "string", "enum": ["buy", "sell"], "description": "The trade action"},
                            "quantity": {"type": "number", "description": "Number of shares"},
                            "price": {"type": "number", "description": "The current market price to execute at"}
                        },
                        "required": ["symbol", "action", "quantity", "price"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_analysis",
                    "description": "Get detailed AI analysis of the current market indices and trends.",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

        self.tools = {
            "execute_trade": self.execute_trade,
            "get_market_analysis": self.get_market_analysis
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
        portfolio = data_store.get_portfolio_by_user_id(user_id)
        market = data_store.get_market_data()

        indices_str = " | ".join(f"{i['symbol']}: {i['value']} ({i['change']})" for i in market.get("indices", []))

        context_data = f"""
USER: {user['firstName']} {user['lastName']} | Risk Profile: {user.get('riskProfile', 'moderate')}
MARKET INDICES: {indices_str}"""

        if portfolio:
            total_gain = sum((h["currentPrice"] - h["avgCost"]) * h["shares"] for h in portfolio.get("holdings", []))
            
            holdings_str = ""
            if portfolio.get("holdings"):
                holdings_str = "\n".join(
                    f"  - {h['symbol']} | {h['name']} | {h['shares']} shares | Avg: {format_currency(h['avgCost'])} | Current: {format_currency(h['currentPrice'])} | P&L: {format_currency((h['currentPrice'] - h['avgCost']) * h['shares'])} ({(h['currentPrice'] - h['avgCost']) / h['avgCost'] * 100.0:.1f}%)"
                    for h in portfolio["holdings"]
                )
            else:
                holdings_str = "  None"

            context_data += f"""
PORTFOLIO VALUE: {format_currency(portfolio['totalValue'])} | Risk Tolerance: {portfolio.get('riskTolerance', 'moderate')}
TOTAL UNREALIZED GAIN/LOSS: {format_currency(total_gain)}
HOLDINGS:
{holdings_str}"""
        else:
            context_data += '\nNo investment portfolio found for this user.'
            
        context_data += "\n\nNote: This is AI-generated advice, not professional financial advice. Do not guarantee returns."

        return await super().process(session_id, user_message, params, context_data)

    def execute_trade(self, **params):
        user_id = params.get("userId")
        symbol = params.get("symbol")
        action = params.get("action")
        quantity = float(params.get("quantity", 0))
        price = float(params.get("price", 0))
        total_value = quantity * price

        if total_value > config.approval_thresholds["trade"]:
            approval = data_store.add_approval({
                "type": 'high_value_trade',
                "agentName": self.name,
                "userId": user_id,
                "details": {
                    "symbol": symbol,
                    "action": action,
                    "quantity": quantity,
                    "price": price,
                    "totalValue": total_value
                },
                "reason": f"Trade of {format_currency(total_value)} exceeds threshold of {format_currency(config.approval_thresholds['trade'])}",
            })

            return {
                "success": False,
                "requiresApproval": True,
                "approvalId": approval["id"],
                "message": f"Trade of {format_currency(total_value)} exceeds the auto-approval threshold. Queued for human review. Approval ID: {approval['id']}"
            }

        try:
            trade = data_store.execute_trade(user_id, symbol, action, quantity, price)
            return {
                "success": True,
                "message": f"Trade executed successfully. Action: {action}, Symbol: {symbol}, Quantity: {quantity}, Total: {format_currency(total_value)}"
            }
        except Exception as error:
            return {"success": False, "message": f"Trade failed: {str(error)}"}

    def get_market_analysis(self, **params):
        market = data_store.get_market_data()
        return {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "sentiment": "Slightly Bullish",
            "analysis": "Market indices are showing steady growth. Tech sector is outperforming due to AI advancements. Recommended to maintain a diversified portfolio.",
            "indices": market.get("indices", [])
        }

investment_agent = InvestmentAgent()
