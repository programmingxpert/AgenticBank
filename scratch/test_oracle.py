import asyncio
from src.data import oracle
from src.utils.logger import logger

async def test():
    try:
        await oracle.init_db()
        print("Oracle connection initialized successfully!")
        res = await oracle.execute("SELECT count(*) as count FROM users")
        print("Test Query Result:", res)
    except Exception as e:
        print("Oracle connection error details:", str(e))

asyncio.run(test())
