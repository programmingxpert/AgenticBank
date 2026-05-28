import asyncio
from src.data.data_store import data_store
from src.ai.orchestrator import route_message, route_banker_message
from src.utils.logger import logger

async def test_e2e():
    print("Initializing data store...")
    await data_store.init()
    
    # 1. Test user message: transaction balance check
    print("\n--- Testing User Balance Inquiry Route ---")
    session_id = "test-user-sess-1"
    user_id = "USR-001"
    msg = "What is my account balance?"
    
    try:
        res = await route_message(session_id, msg, user_id)
        print("Response received:")
        print(f"Content: {res.get('content')}")
        print(f"Agent: {res.get('displayName')} ({res.get('domain')})")
    except Exception as e:
        print("Failed user balance inquiry:")
        import traceback
        traceback.print_exc()

    # 2. Test banker message
    print("\n--- Testing Banker Copilot Route ---")
    banker_session_id = "test-banker-sess-1"
    banker_profile = {
        "id": "BNK-001",
        "username": "agent1",
        "name": "Jane Analyst",
        "role": "Fraud Analyst"
    }
    banker_msg = "Please analyze USR-001 accounts and check for suspicious activity."
    
    try:
        res = await route_banker_message(banker_session_id, banker_msg, "USR-001", banker_profile)
        print("Banker Response received:")
        print(f"Content: {res.get('content')}")
    except Exception as e:
        print("Failed banker copilot query:")
        import traceback
        traceback.print_exc()

asyncio.run(test_e2e())
