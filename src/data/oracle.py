import os
import json
import re
import oracledb
import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.utils.logger import logger

# Set output behavior
oracledb.defaults.fetch_lobs = True  # Automatically fetches CLOBs as strings

db_config = {
    "user": os.getenv("ORACLE_USER", "banking"),
    "password": os.getenv("ORACLE_PASSWORD", "oracle"),
    "dsn": os.getenv("ORACLE_CONNECT_STRING", "localhost:1521/FREEPDB1"),
    "wallet_location": os.getenv("TNS_ADMIN"),
    "wallet_password": os.getenv("WALLET_PASSWORD"),
    "min": 2,
    "max": 10,
    "increment": 1
}

pool = None
executor = ThreadPoolExecutor(max_workers=10)

def to_snake_case(str_val):
    if str_val == 'date':
        return 'DATE_VAL'
    # Convert camelCase to snake_case
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', str_val)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).upper()

def to_camel_case(str_val):
    if str_val == 'DATE_VAL':
        return 'date'
    parts = str_val.lower().split('_')
    return parts[0] + ''.join(x.title() for x in parts[1:])

JSON_KEYS = {'ADDRESS', 'HOLDINGS', 'DETAILS', 'MESSAGES', 'AGENT_HISTORIES', 'METADATA'}

def row_to_obj(row):
    if not row:
        return None
    obj = {}
    for key, val in row.items():
        # Read CLOBs if they aren't pre-fetched
        if hasattr(val, 'read'):
            val = val.read()
        if key in JSON_KEYS and isinstance(val, str):
            try:
                val = json.loads(val)
            except Exception:
                pass
        camel_key = to_camel_case(key)
        obj[camel_key] = val
    return obj

def _init_db_sync():
    global pool
    if pool is not None:
        return
    logger.info(f"Oracle DB: Initializing connection pool to {db_config['dsn']}...")
    
    kwargs = {
        "user": db_config["user"],
        "password": db_config["password"],
        "dsn": db_config["dsn"],
        "min": db_config["min"],
        "max": db_config["max"],
        "increment": db_config["increment"]
    }
    
    if db_config["wallet_location"]:
        kwargs["config_dir"] = db_config["wallet_location"]
        kwargs["wallet_location"] = db_config["wallet_location"]
        
    if db_config["wallet_password"]:
        kwargs["wallet_password"] = db_config["wallet_password"]
        
    pool = oracledb.create_pool(**kwargs)
    logger.info("Oracle DB: Connection pool created successfully.")

async def init_db():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, _init_db_sync)
    await initialize_schema()

def _execute_sync(sql, binds, options):
    global pool
    if pool is None:
        _init_db_sync()
    
    conn = pool.acquire()
    try:
        cursor = conn.cursor()
        
        auto_commit = options.get("auto_commit", True)
        
        if binds:
            # Oracle binds can be lists or dicts. Let's make sure binds are correct
            cursor.execute(sql, binds)
        else:
            cursor.execute(sql)
            
        # Configure output row type after execution when cursor.description is populated
        if cursor.description:
            cursor.rowfactory = lambda *args: dict(zip([d[0] for d in cursor.description], args))
            
        rows = cursor.fetchall() if cursor.description else None
        rows_affected = cursor.rowcount
        
        if auto_commit:
            conn.commit()
            
        return {
            "rows": rows if rows is not None else [],
            "rowsAffected": rows_affected
        }
    except Exception as e:
        logger.error(f"Oracle DB Execute Error: {str(e)} | SQL: {sql}")
        raise e
    finally:
        try:
            conn.close()
        except Exception:
            pass

async def execute(sql, binds=None, options=None):
    if options is None:
        options = {}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, _execute_sync, sql, binds, options)

async def initialize_schema():
    # Check if USERS table exists
    schema_exists = False
    try:
        res = await execute("SELECT table_name FROM user_tables WHERE table_name = 'USERS'")
        if res.get("rows") and len(res["rows"]) > 0:
            schema_exists = True
    except Exception as err:
        logger.warn(f"Oracle DB Check error: {str(err)}. Assuming schema needs initialization.")

    if schema_exists:
        logger.info("Oracle DB: Tables already exist. Skipping table creation.")
        return

    logger.info("Oracle DB: Creating schema tables...")
    
    # 1. Bankers
    await execute("""
        CREATE TABLE bankers (
          id VARCHAR2(50) PRIMARY KEY,
          username VARCHAR2(50) UNIQUE,
          password_hash VARCHAR2(128),
          name VARCHAR2(100),
          role VARCHAR2(50)
        )
    """)

    # 2. Users
    await execute("""
        CREATE TABLE users (
          id VARCHAR2(50) PRIMARY KEY,
          first_name VARCHAR2(50),
          last_name VARCHAR2(50),
          email VARCHAR2(100),
          phone VARCHAR2(30),
          dob VARCHAR2(30),
          ssn VARCHAR2(20),
          address CLOB,
          occupation VARCHAR2(100),
          employer VARCHAR2(100),
          annual_income NUMBER,
          credit_score NUMBER,
          kyc_status VARCHAR2(30),
          kyc_date VARCHAR2(30),
          risk_profile VARCHAR2(30),
          join_date VARCHAR2(30)
        )
    """)

    # 3. Accounts
    await execute("""
        CREATE TABLE accounts (
          id VARCHAR2(50) PRIMARY KEY,
          user_id VARCHAR2(50),
          type VARCHAR2(30),
          name VARCHAR2(100),
          balance NUMBER,
          currency VARCHAR2(10),
          account_number VARCHAR2(30),
          routing_number VARCHAR2(30),
          status VARCHAR2(30),
          interest_rate NUMBER,
          credit_limit NUMBER
        )
    """)

    # 4. Transactions
    await execute("""
        CREATE TABLE transactions (
          id VARCHAR2(50) PRIMARY KEY,
          account_id VARCHAR2(50),
          type VARCHAR2(30),
          amount NUMBER,
          merchant VARCHAR2(100),
          category VARCHAR2(50),
          description VARCHAR2(500),
          date_val VARCHAR2(50),
          status VARCHAR2(30),
          risk_score NUMBER
        )
    """)

    # 5. Loans
    await execute("""
        CREATE TABLE loans (
          id VARCHAR2(50) PRIMARY KEY,
          user_id VARCHAR2(50),
          type VARCHAR2(30),
          amount NUMBER,
          remaining_balance NUMBER,
          interest_rate NUMBER,
          term_months NUMBER,
          monthly_payment NUMBER,
          status VARCHAR2(30),
          start_date VARCHAR2(30),
          purpose VARCHAR2(500)
        )
    """)

    # 6. Portfolios
    await execute("""
        CREATE TABLE portfolios (
          user_id VARCHAR2(50) PRIMARY KEY,
          account_id VARCHAR2(50),
          risk_tolerance VARCHAR2(30),
          total_value NUMBER,
          holdings CLOB
        )
    """)

    # 7. Complaints
    await execute("""
        CREATE TABLE complaints (
          id VARCHAR2(50) PRIMARY KEY,
          user_id VARCHAR2(50),
          subject VARCHAR2(200),
          description VARCHAR2(1000),
          status VARCHAR2(30),
          date_val VARCHAR2(30),
          priority VARCHAR2(20)
        )
    """)

    # 8. Approval Queue
    await execute("""
        CREATE TABLE approval_queue (
          id VARCHAR2(50) PRIMARY KEY,
          user_id VARCHAR2(50),
          type VARCHAR2(30),
          status VARCHAR2(30),
          reason VARCHAR2(500),
          details CLOB,
          requested_at VARCHAR2(50),
          resolved_at VARCHAR2(50),
          reviewer_note VARCHAR2(500)
        )
    """)

    # 9. Audit Logs
    await execute("""
        CREATE TABLE audit_logs (
          id VARCHAR2(50) PRIMARY KEY,
          action VARCHAR2(100),
          timestamp VARCHAR2(50),
          metadata CLOB
        )
    """)

    # 10. Sessions
    await execute("""
        CREATE TABLE sessions (
          id VARCHAR2(100) PRIMARY KEY,
          user_id VARCHAR2(50),
          title VARCHAR2(200),
          updated_at VARCHAR2(50),
          messages CLOB,
          agent_histories CLOB
        )
    """)

    # 11. Vector episodic memory
    await execute("""
        CREATE TABLE episodic_memory (
          id VARCHAR2(100) PRIMARY KEY,
          user_id VARCHAR2(50),
          document CLOB,
          metadata CLOB,
          timestamp VARCHAR2(50),
          embedding VECTOR(1536, FLOAT32)
        )
    """)

    # 12. Vector semantic memory
    await execute("""
        CREATE TABLE semantic_memory (
          id VARCHAR2(100) PRIMARY KEY,
          user_id VARCHAR2(50),
          key VARCHAR2(100),
          document CLOB,
          metadata CLOB,
          embedding VECTOR(1536, FLOAT32)
        )
    """)

    # 13. Vector transaction embeddings
    await execute("""
        CREATE TABLE transaction_embeddings (
          id VARCHAR2(100) PRIMARY KEY,
          user_id VARCHAR2(50),
          document CLOB,
          metadata CLOB,
          embedding VECTOR(1536, FLOAT32)
        )
    """)

    logger.info("Oracle DB: Tables created successfully. Seeding initial data will be executed by data store.")
