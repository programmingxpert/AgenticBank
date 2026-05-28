import datetime
from src.agents.base_agent import BaseAgent
from src.data.data_store import data_store

class CustomerServiceAgent(BaseAgent):
    def __init__(self):
        super().__init__('customer-service', 'Customer Service Agent', '🎧')
        self.use_reasoning = False
        
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "file_complaint",
                    "description": "File a customer complaint or support ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "Subject of the complaint"},
                            "description": {"type": "string", "description": "Detailed description of the issue"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Priority level"}
                        },
                        "required": ["subject", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_profile",
                    "description": "Update the customer's profile information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "description": "New email address"},
                            "phone": {"type": "string", "description": "New phone number"},
                            "occupation": {"type": "string", "description": "New occupation"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_callback",
                    "description": "Request a phone callback from a human support representative.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {"type": "string", "description": "Preferred phone number for callback"},
                            "topic": {"type": "string", "description": "Topic of the callback"}
                        },
                        "required": ["phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "alert_banker",
                    "description": "Send a high-priority alert to the banker if the customer is extremely upset or threatening to leave.",
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
            "file_complaint": self.file_complaint,
            "update_profile": self.update_profile,
            "request_callback": self.request_callback,
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
        complaints = data_store.get_complaints_by_user_id(user_id)
        loans = data_store.get_loans_by_user_id(user_id)

        complaints_str = ""
        if complaints:
            items = "\n".join(
                f"  - {c['id']} | {c['subject']} | Status: {c['status']} | {c['date']}"
                for c in complaints
            )
            complaints_str = f"COMPLAINTS:\n{items}"

        context_data = f"""
CUSTOMER: {user['firstName']} {user['lastName']} | Member since: {user.get('joinDate')}
EMAIL: {user.get('email')} | PHONE: {user.get('phone')}
ADDRESS: {user.get('address', {}).get('street')}, {user.get('address', {}).get('city')}, {user.get('address', {}).get('state')} {user.get('address', {}).get('zip')}
ACCOUNTS: {len(accounts)} ({', '.join(a['type'] for a in accounts)})
ACTIVE LOANS: {len([l for l in loans if l['status'] == 'active'])}
OPEN COMPLAINTS: {len([c for c in complaints if c['status'] != 'resolved'])}
{complaints_str}"""

        return await super().process(session_id, user_message, params, context_data)

    def file_complaint(self, **params):
        complaint = data_store.create_complaint(
            user_id=params.get("userId"),
            subject=params.get("subject"),
            description=params.get("description"),
            priority=params.get("priority", "medium")
        )

        return {
            "success": True,
            "ticketId": complaint["id"],
            "status": 'Open',
            "priority": complaint["priority"],
            "message": "Complaint filed successfully."
        }

    def update_profile(self, **params):
        user_id = params.get("userId")
        email = params.get("email")
        phone = params.get("phone")
        occupation = params.get("occupation")
        
        updates = {}
        if email:
            updates["email"] = email
        if phone:
            updates["phone"] = phone
        if occupation:
            updates["occupation"] = occupation
        
        if updates:
            data_store.update_user(user_id, updates)
            return {"success": True, "updatedFields": list(updates.keys()), "message": "Profile updated successfully."}
            
        return {"success": False, "message": "No valid fields provided to update."}

    def request_callback(self, **params):
        phone = params.get("phone")
        topic = params.get("topic", "your inquiry")
        return {
            "success": True,
            "message": f"A callback has been scheduled for {phone}. A representative will call you within 30 minutes regarding {topic}."
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

customer_service_agent = CustomerServiceAgent()
