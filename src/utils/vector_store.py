import re
import math
import json
import random
import time
from datetime import datetime
from src.data import oracle
from src.utils.logger import logger

def generate_embedding(text):
    dimensions = 1536
    vector = [0.0] * dimensions
    if not text:
        return vector

    tokens = re.findall(r'\b\w+\b', text.lower())
    if not tokens:
        return vector

    for token in tokens:
        hash_val = 5381
        for char in token:
            val_33 = (hash_val * 33) & 0xFFFFFFFF
            hash_val = (val_33 ^ ord(char)) & 0xFFFFFFFF
            if hash_val & 0x80000000:
                hash_val = hash_val - 0x100000000
                
        idx = abs(hash_val) % dimensions
        vector[idx] += 1.0

    # L2 Normalization
    sum_sq = sum(val * val for val in vector)
    norm = math.sqrt(sum_sq)
    if norm > 0:
        vector = [val / norm for val in vector]

    return vector

class VectorStore:
    def __init__(self):
        self.is_mock = False

    async def init(self):
        try:
            logger.info('VectorStore: Initializing Oracle Vector Store...')
            
            res_episodic = await oracle.execute("SELECT count(*) as count FROM episodic_memory")
            res_txns = await oracle.execute("SELECT count(*) as count FROM transaction_embeddings")
            
            episodic_count = 0
            txn_count = 0
            
            if res_episodic.get("rows"):
                row = res_episodic["rows"][0]
                episodic_count = row.get("COUNT") or row.get("count") or 0
                
            if res_txns.get("rows"):
                row = res_txns["rows"][0]
                txn_count = row.get("COUNT") or row.get("count") or 0

            logger.info(f"VectorStore: Found {episodic_count} episodic memories and {txn_count} transaction embeddings in Oracle DB.")
            logger.info('VectorStore: Oracle Vector Store initialized successfully ✅')
            return True
        except Exception as error:
            logger.error(f"VectorStore initialization failed: {str(error)}")
            raise error

    async def add_episodic(self, user_id, event, metadata=None):
        if metadata is None:
            metadata = {}
        try:
            emb = generate_embedding(event)
            id_val = f"ep_{user_id}_{int(time.time()*1000)}_{str(random.random())[2:6]}"
            timestamp = datetime.utcnow().isoformat() + "Z"
            bind_vec = '[' + ','.join(map(str, emb)) + ']'
            
            # Simple insert is fine since episodic IDs are random and unique
            await oracle.execute(
                """INSERT INTO episodic_memory (id, user_id, document, metadata, timestamp, embedding)
                   VALUES (:id, :userId, :document, :metadata, :timestamp, to_vector(:embedding))""",
                {
                    "id": id_val,
                    "userId": user_id,
                    "document": event,
                    "metadata": json.dumps(metadata),
                    "timestamp": timestamp,
                    "embedding": bind_vec
                }
            )
        except Exception as e:
            logger.error(f"VectorStore add_episodic Error: {str(e)}")

    async def add_semantic(self, user_id, key, value, metadata=None):
        if metadata is None:
            metadata = {}
        fact = f"{key}: {json.dumps(value)}"
        try:
            emb = generate_embedding(fact)
            id_val = f"sem_{user_id}_{key}"
            bind_vec = '[' + ','.join(map(str, emb)) + ']'
            
            # Atomic MERGE statement to avoid ORA-00001 unique constraint violation
            await oracle.execute(
                """MERGE INTO semantic_memory t
                   USING (SELECT :id AS id FROM dual) s
                   ON (t.id = s.id)
                   WHEN MATCHED THEN
                     UPDATE SET user_id = :userId, key = :key, document = :document, metadata = :metadata, embedding = to_vector(:embedding)
                   WHEN NOT MATCHED THEN
                     INSERT (id, user_id, key, document, metadata, embedding)
                     VALUES (:id, :userId, :key, :document, :metadata, to_vector(:embedding))""",
                {
                    "id": id_val,
                    "userId": user_id,
                    "key": key,
                    "document": fact,
                    "metadata": json.dumps(metadata),
                    "embedding": bind_vec
                }
            )
        except Exception as e:
            logger.error(f"VectorStore add_semantic Error: {str(e)}")

    async def search_memory(self, user_id, query, limit=5):
        try:
            query_emb = generate_embedding(query)
            bind_vec = '[' + ','.join(map(str, query_emb)) + ']'
            
            e_res = await oracle.execute(
                """SELECT document FROM episodic_memory
                   WHERE user_id = :userId
                   ORDER BY vector_distance(embedding, to_vector(:queryEmb), COSINE)
                   FETCH FIRST :limit ROWS ONLY""",
                {"userId": user_id, "queryEmb": bind_vec, "limit": limit}
            )
            
            s_res = await oracle.execute(
                """SELECT document FROM semantic_memory
                   WHERE user_id = :userId
                   ORDER BY vector_distance(embedding, to_vector(:queryEmb), COSINE)
                   FETCH FIRST :limit ROWS ONLY""",
                {"userId": user_id, "queryEmb": bind_vec, "limit": limit}
            )

            episodic = [r.get("DOCUMENT") or r.get("document") for r in e_res.get("rows", [])]
            semantic = [r.get("DOCUMENT") or r.get("document") for r in s_res.get("rows", [])]
            
            return {"episodic": [e for e in episodic if e], "semantic": [s for s in semantic if s]}
        except Exception as e:
            logger.error(f"VectorStore search_memory Error: {str(e)}")
            return {"episodic": [], "semantic": []}

    async def index_transaction(self, user_id, txn):
        doc = f"Transaction [{txn['id']}]: {txn.get('date')} | Merchant: {txn.get('merchant')} | Amount: {txn.get('amount')} INR | Category: {txn.get('category')} | Description: {txn.get('description')}"
        try:
            emb = generate_embedding(doc)
            id_val = f"txn_{txn['id']}"
            bind_vec = '[' + ','.join(map(str, emb)) + ']'
            
            # Atomic MERGE statement
            await oracle.execute(
                """MERGE INTO transaction_embeddings t
                   USING (SELECT :id AS id FROM dual) s
                   ON (t.id = s.id)
                   WHEN MATCHED THEN
                     UPDATE SET user_id = :userId, document = :document, metadata = :metadata, embedding = to_vector(:embedding)
                   WHEN NOT MATCHED THEN
                     INSERT (id, user_id, document, metadata, embedding)
                     VALUES (:id, :userId, :document, :metadata, to_vector(:embedding))""",
                {
                    "id": id_val,
                    "userId": user_id,
                    "document": doc,
                    "metadata": json.dumps({"userId": user_id, "amount": txn.get("amount"), "merchant": txn.get("merchant"), "type": txn.get("type")}),
                    "embedding": bind_vec
                }
            )
        except Exception as e:
            logger.error(f"VectorStore index_transaction Error: {str(e)}")

    async def index_profile(self, user):
        doc = f"User Profile [{user['id']}]: {user.get('firstName')} {user.get('lastName')} | Occupation: {user.get('occupation')} | Income: {user.get('annualIncome')} INR | Credit Score: {user.get('creditScore')} | Risk: {user.get('riskProfile')} | Join Date: {user.get('joinDate')}"
        try:
            emb = generate_embedding(doc)
            id_val = f"profile_{user['id']}"
            bind_vec = '[' + ','.join(map(str, emb)) + ']'
            
            # Atomic MERGE statement
            await oracle.execute(
                """MERGE INTO semantic_memory t
                   USING (SELECT :id AS id FROM dual) s
                   ON (t.id = s.id)
                   WHEN MATCHED THEN
                     UPDATE SET user_id = :userId, key = :key, document = :document, metadata = :metadata, embedding = to_vector(:embedding)
                   WHEN NOT MATCHED THEN
                     INSERT (id, user_id, key, document, metadata, embedding)
                     VALUES (:id, :userId, :key, :document, :metadata, to_vector(:embedding))""",
                {
                    "id": id_val,
                    "userId": user["id"],
                    "key": "profile",
                    "document": doc,
                    "metadata": json.dumps({"userId": user["id"], "type": "profile"}),
                    "embedding": bind_vec
                }
            )
        except Exception as e:
            logger.error(f"VectorStore index_profile Error: {str(e)}")

    async def sync_all(self, store):
        logger.info('VectorStore: Performing Universal Synchronization to Oracle Vector Store...')
        try:
            users_list = store.get_users()
            for user in users_list:
                await self.index_profile(user)
                txns = store.get_transactions_by_user_id(user["id"], 100)
                for txn in txns:
                    await self.index_transaction(user["id"], txn)
            logger.info('VectorStore: Universal Sync Complete ✅')
        except Exception as err:
            logger.error(f"VectorStore sync_all Error: {str(err)}")

vector_store = VectorStore()
