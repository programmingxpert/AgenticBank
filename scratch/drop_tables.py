import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["TNS_ADMIN"] = os.getenv("TNS_ADMIN", "")

from src.data import oracle

async def drop_all():
    print("Connecting to Oracle...")
    await oracle._execute_sync("SELECT 1 FROM dual", None, {})
    
    tables = [
        "users", "bankers", "accounts", "transactions", "loans", 
        "portfolios", "complaints", "approval_queue", "audit_logs", 
        "sessions", "episodic_memory", "semantic_memory", "transaction_embeddings"
    ]
    
    print("Dropping tables...")
    for table in tables:
        try:
            await oracle.execute(f"DROP TABLE {table} CASCADE CONSTRAINTS")
            print(f"Dropped {table}")
        except Exception as e:
            print(f"Skipped {table}: {e}")
            
    print("Done! You can now restart your server to cleanly initialize the schema.")

if __name__ == "__main__":
    asyncio.run(drop_all())
