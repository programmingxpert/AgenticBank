import asyncio
from src.config import validate_config
from src.data.data_store import data_store
from src.utils.logger import logger

async def test_startup():
    print("Validating config...")
    warnings, errors, is_valid = validate_config()
    print("is_valid:", is_valid)
    print("warnings:", warnings)
    print("errors:", errors)
    
    if not is_valid:
        print("Config invalid, exiting...")
        return
        
    try:
        print("Initializing data store...")
        await data_store.init()
        print("Data store initialized successfully!")
    except Exception as e:
        print("Data store initialization failed with exception:")
        import traceback
        traceback.print_exc()

asyncio.run(test_startup())
