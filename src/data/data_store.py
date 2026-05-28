import uuid
import json
import asyncio
from datetime import datetime
from src.data import oracle
from src.data.seed_data import marketData, users, accounts, transactions, loans, portfolios, complaints, bankers
from src.utils.event_emitter import EventEmitter
from src.utils.logger import logger
from src.utils.vector_store import vector_store

class DataStore(EventEmitter):
    def __init__(self):
        super().__init__()
        self.users = []
        self.accounts = []
        self.transactions = []
        self.loans = []
        self.portfolios = []
        self.complaints = []
        self.market_data = json.loads(json.dumps(marketData))
        self.approval_queue = []
        self.audit_log = []
        self.sessions = []
        self.bankers = []
        self.payments = []

    async def init(self):
        try:
            # 1. Initialize Oracle pool and create tables
            await oracle.init_db()
            
            # 2. Populate the read cache from Oracle
            await self.load_all()
            logger.info('DataStore: Read-through cache populated from Oracle DB.')
            
            # 3. Initialize the Vector Store
            await vector_store.init()
            
            # Seed vector store if episodic memory is empty
            res_episodic = await oracle.execute("SELECT count(*) as count FROM episodic_memory")
            row = res_episodic["rows"][0] if res_episodic.get("rows") else {}
            count = row.get("COUNT") or row.get("count") or 0
            
            if count == 0:
                logger.info('DataStore: Vector memory tables are empty. Running initial sync_all...')
                await vector_store.sync_all(self)
                
            logger.info('DataStore: Oracle DB system initialized successfully ✅')
        except Exception as error:
            logger.error(f"DataStore initialization failed: {str(error)}")
            raise error

    async def load_all(self):
        logger.info('DataStore: Fetching all records from Oracle DB...')
        
        res_users = await oracle.execute("SELECT * FROM users")
        self.users = [oracle.row_to_obj(r) for r in res_users["rows"]]

        if not self.users:
            logger.info('DataStore: Database is empty! Running self-healing seed sequence...')
            await self.seed_db()
            res_users = await oracle.execute("SELECT * FROM users")
            self.users = [oracle.row_to_obj(r) for r in res_users["rows"]]

        res_accounts = await oracle.execute("SELECT * FROM accounts")
        self.accounts = [oracle.row_to_obj(r) for r in res_accounts["rows"]]

        res_txns = await oracle.execute("SELECT * FROM transactions ORDER BY date_val DESC")
        self.transactions = [oracle.row_to_obj(r) for r in res_txns["rows"]]

        res_loans = await oracle.execute("SELECT * FROM loans")
        self.loans = [oracle.row_to_obj(r) for r in res_loans["rows"]]

        res_portfolios = await oracle.execute("SELECT * FROM portfolios")
        self.portfolios = [oracle.row_to_obj(r) for r in res_portfolios["rows"]]

        res_complaints = await oracle.execute("SELECT * FROM complaints")
        self.complaints = [oracle.row_to_obj(r) for r in res_complaints["rows"]]

        res_approvals = await oracle.execute("SELECT * FROM approval_queue")
        self.approval_queue = [oracle.row_to_obj(r) for r in res_approvals["rows"]]

        res_audit = await oracle.execute("SELECT * FROM audit_logs ORDER BY timestamp ASC")
        self.audit_log = [oracle.row_to_obj(r) for r in res_audit["rows"]]

        res_sessions = await oracle.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
        self.sessions = [oracle.row_to_obj(r) for r in res_sessions["rows"]]

        res_bankers = await oracle.execute("SELECT * FROM bankers")
        self.bankers = [oracle.row_to_obj(r) for r in res_bankers["rows"]]
        
        logger.info(f"DataStore Loaded: {len(self.users)} users, {len(self.accounts)} accounts, {len(self.transactions)} txns, {len(self.sessions)} sessions, {len(self.bankers)} bankers.")

    async def seed_db(self):
        logger.info("DataStore: Seeding Oracle tables with initial data...")
        for u in users:
            sql = """INSERT INTO users (id, first_name, last_name, email, phone, dob, ssn, address, occupation, employer, annual_income, credit_score, risk_profile, kyc_status, join_date) 
                     VALUES (:id, :firstName, :lastName, :email, :phone, :dob, :ssn, :address, :occupation, :employer, :annualIncome, :creditScore, :riskProfile, :kycStatus, :joinDate)"""
            binds = {
                "id": u["id"], "firstName": u["firstName"], "lastName": u["lastName"], "email": u["email"],
                "phone": u.get("phone", ""), "dob": u.get("dob", ""), "ssn": u.get("ssn", ""), "address": json.dumps(u.get("address", {})),
                "occupation": u.get("occupation", ""), "employer": u.get("employer", ""), "annualIncome": u.get("annualIncome", 0),
                "creditScore": u.get("creditScore", 0), "riskProfile": u.get("riskProfile", ""), "kycStatus": u.get("kycStatus", ""),
                "joinDate": u.get("joinDate", "")
            }
            await oracle.execute(sql, binds)
            
        for a in accounts:
            sql = """INSERT INTO accounts (id, user_id, type, name, balance, currency, account_number, routing_number, status, interest_rate, credit_limit) 
                     VALUES (:id, :userId, :type, :name, :balance, :currency, :accountNumber, :routingNumber, :status, :interestRate, :creditLimit)"""
            binds = {
                "id": a["id"], "userId": a["userId"], "type": a["type"], "name": a["name"], "balance": a["balance"], "currency": a.get("currency", "INR"),
                "accountNumber": a.get("accountNumber", ""), "routingNumber": a.get("routingNumber", ""), "status": a.get("status", "active"),
                "interestRate": a.get("interestRate", 0.0), "creditLimit": a.get("creditLimit")
            }
            await oracle.execute(sql, binds)

        for t in transactions:
            sql = """INSERT INTO transactions (id, user_id, account_id, type, amount, currency, merchant, category, date_val, status, risk_score, latitude, longitude) 
                     VALUES (:id, :userId, :accountId, :type, :amount, :currency, :merchant, :category, :date_val, :status, :riskScore, :latitude, :longitude)"""
            binds = {
                "id": t["id"], "userId": t["userId"], "accountId": t["accountId"], "type": t["type"], "amount": t["amount"], "currency": t.get("currency", "INR"),
                "merchant": t["merchant"], "category": t["category"], "date_val": t["date"], "status": t.get("status", "completed"),
                "riskScore": t.get("riskScore", 0.0), "latitude": t.get("location", {}).get("lat", 0.0), "longitude": t.get("location", {}).get("lng", 0.0)
            }
            await oracle.execute(sql, binds)

        for l in loans:
            sql = """INSERT INTO loans (id, user_id, type, purpose, amount, currency, status, interest_rate, term_months, start_date, remaining_balance, monthly_payment, next_payment_date) 
                     VALUES (:id, :userId, :type, :purpose, :amount, :currency, :status, :interestRate, :termMonths, :startDate, :remainingBalance, :monthlyPayment, :nextPaymentDate)"""
            binds = {
                "id": l["id"], "userId": l["userId"], "type": l.get("type", "personal"), "purpose": l.get("purpose", ""), "amount": l["amount"], "currency": l.get("currency", "INR"),
                "status": l["status"], "interestRate": l.get("interestRate", 0.0), "termMonths": l.get("termMonths", 0), "startDate": l.get("startDate", ""),
                "remainingBalance": l.get("remainingBalance", 0.0), "monthlyPayment": l.get("monthlyPayment", 0.0), "nextPaymentDate": l.get("nextPaymentDate", "")
            }
            await oracle.execute(sql, binds)

        for p in portfolios:
            sql = """INSERT INTO portfolios (user_id, account_id, risk_tolerance, total_value, holdings) 
                     VALUES (:userId, :accountId, :riskTolerance, :totalValue, :holdings)"""
            binds = {
                "userId": p["userId"], "accountId": p["accountId"], "riskTolerance": p["riskTolerance"], "totalValue": p["totalValue"], "holdings": json.dumps(p["holdings"])
            }
            await oracle.execute(sql, binds)

        for c in complaints:
            sql = """INSERT INTO complaints (id, user_id, subject, description, status, date_val, priority) 
                     VALUES (:id, :userId, :subject, :description, :status, :date_val, :priority)"""
            binds = {
                "id": c["id"], "userId": c["userId"], "subject": c["subject"], "description": c["description"], "status": c["status"], "date_val": c["date"], "priority": c.get("priority", "medium")
            }
            await oracle.execute(sql, binds)
            
        for b in bankers:
            sql = """INSERT INTO bankers (username, name, role, password_hash) VALUES (:username, :name, :role, :passwordHash)"""
            binds = {
                "username": b["username"], "name": b["name"], "role": b["role"], "passwordHash": b["passwordHash"]
            }
            await oracle.execute(sql, binds)

        await oracle.execute("COMMIT")
        logger.info("DataStore: Database seeding completed.")

    def save(self):
        pass  # Synchronous save stub

    # ─── Users ───
    def get_users(self):
        return self.users

    def get_user_by_id(self, user_id):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return None
        intel = self.get_financial_intelligence(user_id)
        return {**user, **intel}

    def get_financial_intelligence(self, user_id):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return {}
        
        user_loans = self.get_loans_by_user_id(user_id)
        monthly_income = user.get("annualIncome", 0) / 12
        total_monthly_debt = sum(l.get("monthlyPayment", 0) for l in user_loans if l.get("status") == "active")
        
        dti_ratio = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else 0
        existing_mortgage = next((l for l in user_loans if l.get("type") == "mortgage" and l.get("status") == "active"), None)
        
        return {
            "monthlyIncome": monthly_income,
            "totalMonthlyDebt": total_monthly_debt,
            "dtiRatio": round(dti_ratio, 2),
            "existingMortgage": {
                "amount": existing_mortgage.get("amount"),
                "balance": existing_mortgage.get("remainingBalance"),
                "payment": existing_mortgage.get("monthlyPayment")
            } if existing_mortgage else None
        }

    def update_user(self, user_id, updates):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return None
        user.update(updates)
        self.emit('user:updated', user)
        
        # Async background write
        sql = """UPDATE users SET 
                   first_name = :firstName, 
                   last_name = :lastName, 
                   email = :email, 
                   phone = :phone, 
                   dob = :dob, 
                   ssn = :ssn, 
                   address = :address, 
                   occupation = :occupation, 
                   employer = :employer, 
                   annual_income = :annualIncome, 
                   credit_score = :creditScore, 
                   kyc_status = :kycStatus, 
                   kyc_date = :kycDate, 
                   risk_profile = :riskProfile, 
                   join_date = :joinDate 
                 WHERE id = :id"""
                 
        binds = {
            "firstName": user.get("firstName"),
            "lastName": user.get("lastName"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "dob": user.get("dob"),
            "ssn": user.get("ssn"),
            "address": json.dumps(user.get("address")),
            "occupation": user.get("occupation"),
            "employer": user.get("employer"),
            "annualIncome": user.get("annualIncome"),
            "creditScore": user.get("creditScore"),
            "kycStatus": user.get("kycStatus"),
            "kycDate": user.get("kycDate"),
            "riskProfile": user.get("riskProfile"),
            "joinDate": user.get("joinDate"),
            "id": user_id
        }
        
        asyncio.create_task(oracle.execute(sql, binds))
        asyncio.create_task(vector_store.index_profile(user))
        
        return user

    # ─── Accounts ───
    def get_accounts_by_user_id(self, user_id):
        return [a for a in self.accounts if a["userId"] == user_id]

    def get_account_by_id(self, account_id):
        return next((a for a in self.accounts if a["id"] == account_id), None)

    def update_account(self, account_id, updates):
        account = self.get_account_by_id(account_id)
        if not account:
            return None
        account.update(updates)
        self.emit('account:updated', account)
        
        sql = """UPDATE accounts SET 
                   user_id = :userId,
                   type = :type,
                   name = :name,
                   balance = :balance,
                   currency = :currency,
                   account_number = :accountNumber,
                   routing_number = :routingNumber,
                   status = :status,
                   interest_rate = :interestRate,
                   credit_limit = :creditLimit
                 WHERE id = :id"""
                 
        binds = {
            "userId": account.get("userId"),
            "type": account.get("type"),
            "name": account.get("name"),
            "balance": account.get("balance"),
            "currency": account.get("currency"),
            "accountNumber": account.get("accountNumber"),
            "routingNumber": account.get("routingNumber"),
            "status": account.get("status"),
            "interestRate": account.get("interestRate"),
            "creditLimit": account.get("creditLimit"),
            "id": account_id
        }
        
        asyncio.create_task(oracle.execute(sql, binds))
        return account

    def get_total_balance(self, user_id):
        return sum(a["balance"] for a in self.get_accounts_by_user_id(user_id) if a["type"] != "credit")

    # ─── Transactions ───
    def get_transactions_by_account_id(self, account_id, limit=50):
        txns = [t for t in self.transactions if t["accountId"] == account_id]
        txns.sort(key=lambda x: x["date"], reverse=True)
        return txns[:limit]

    def get_transactions_by_user_id(self, user_id, limit=50):
        account_ids = [a["id"] for a in self.get_accounts_by_user_id(user_id)]
        txns = [t for t in self.transactions if t["accountId"] in account_ids]
        txns.sort(key=lambda x: x["date"], reverse=True)
        return txns[:limit]

    def create_transaction(self, data):
        txn = {
            "id": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "date": datetime.utcnow().isoformat() + "Z",
            "status": "completed",
            "riskScore": data.get("riskScore", random_between(0.01, 0.3)),
            **data
        }
        
        account = self.get_account_by_id(txn["accountId"])
        if account:
            account["balance"] += txn["amount"]
            account["balance"] = round(account["balance"], 2)

        self.transactions.insert(0, txn)
        self.emit('transaction:created', txn)
        
        if txn["riskScore"] > 0.6:
            self.emit('transaction:high_risk', txn)
            self.emit('agent:trace', {
                "agent": "System Monitor",
                "content": f"🚨 High risk transaction detected: {txn.get('merchant')} ({txn['id']}). Risk Score: {txn['riskScore']:.2f}",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            
        self._audit('transaction_created', txn)
        logger.info(f"Transaction created: {txn['id']} | ₹{abs(txn['amount'])}", {"agent": "transaction"})

        # Background writes
        sql_txn = """INSERT INTO transactions (id, account_id, type, amount, merchant, category, description, date_val, status, risk_score) 
                     VALUES (:id, :accountId, :type, :amount, :merchant, :category, :description, :date_val, :status, :riskScore)"""
                     
        binds_txn = {
            "id": txn["id"],
            "accountId": txn["accountId"],
            "type": txn["type"],
            "amount": txn["amount"],
            "merchant": txn["merchant"],
            "category": txn["category"],
            "description": txn["description"],
            "date_val": txn["date"],
            "status": txn["status"],
            "riskScore": txn["riskScore"]
        }
        asyncio.create_task(oracle.execute(sql_txn, binds_txn))

        if account:
            asyncio.create_task(oracle.execute(
                "UPDATE accounts SET balance = :balance WHERE id = :id",
                {"balance": account["balance"], "id": account["id"]}
            ))
            
        user_id = txn.get("userId") or (account.get("userId") if account else None)
        if user_id:
            asyncio.create_task(vector_store.index_transaction(user_id, txn))

        return txn

    def transfer_funds(self, from_account_id, to_account_id, amount, description='Fund Transfer'):
        from_account = self.get_account_by_id(from_account_id)
        if not from_account:
            raise ValueError('Invalid source account')
        if from_account["balance"] < amount:
            raise ValueError('Insufficient funds')
        
        to_account = self.get_account_by_id(to_account_id)
        to_name = to_account["name"] if to_account else f"External Account {to_account_id}"

        debit = self.create_transaction({
            "accountId": from_account_id, "type": "debit", "amount": -amount,
            "merchant": f"Transfer to {to_name}", "category": "Transfer",
            "description": f"Transfer to {to_account_id}: {description}"
        })

        credit = None
        if to_account:
            credit = self.create_transaction({
                "accountId": to_account_id, "type": "credit", "amount": amount,
                "merchant": f"Transfer from {from_account['name']}", "category": "Transfer",
                "description": f"Transfer from {from_account_id}: {description}"
            })

        self.emit('transfer:completed', {"debit": debit, "credit": credit, "amount": amount})
        return {"debit": debit, "credit": credit}

    # ─── Loans ───
    def get_loans_by_user_id(self, user_id):
        return [l for l in self.loans if l["userId"] == user_id]

    def get_loan_by_id(self, loan_id):
        return next((l for l in self.loans if l["id"] == loan_id), None)

    def create_loan(self, data):
        loan = {
            "id": f"LOAN-{str(uuid.uuid4())[:6].upper()}",
            "status": "pending_approval",
            "startDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "remainingBalance": data.get("amount"),
            **data
        }
        self.loans.append(loan)
        self.emit('loan:created', loan)
        self._audit('loan_application', loan)

        sql = """INSERT INTO loans (id, user_id, type, amount, remaining_balance, interest_rate, term_months, monthly_payment, status, start_date, purpose) 
                 VALUES (:id, :userId, :type, :amount, :remainingBalance, :interestRate, :termMonths, :monthlyPayment, :status, :startDate, :purpose)"""
                 
        binds = {
            "id": loan["id"],
            "userId": loan["userId"],
            "type": loan["type"],
            "amount": loan["amount"],
            "remainingBalance": loan["remainingBalance"],
            "interestRate": loan["interestRate"],
            "termMonths": loan["termMonths"],
            "monthlyPayment": loan["monthlyPayment"],
            "status": loan["status"],
            "startDate": loan["startDate"],
            "purpose": loan["purpose"]
        }
        asyncio.create_task(oracle.execute(sql, binds))
        return loan

    # ─── Portfolios ───
    def get_portfolio_by_user_id(self, user_id):
        return next((p for p in self.portfolios if p["userId"] == user_id), None)

    def execute_trade(self, user_id, symbol, action, quantity, price):
        portfolio = self.get_portfolio_by_user_id(user_id)
        if not portfolio:
            raise ValueError('No portfolio found')

        holding = next((h for h in portfolio["holdings"] if h["symbol"] == symbol), None)
        if action == 'sell' and (not holding or holding["shares"] < quantity):
            raise ValueError('Insufficient shares')

        total_value = quantity * price
        if action == 'buy':
            if holding:
                cost = (holding["shares"] * holding["avgCost"]) + total_value
                holding["shares"] += quantity
                holding["avgCost"] = round(cost / holding["shares"], 2)
            else:
                portfolio["holdings"].append({
                    "symbol": symbol, "name": symbol, "shares": quantity,
                    "avgCost": price, "currentPrice": price, "change": "0.0%"
                })
            portfolio["totalValue"] += total_value
        else:
            holding["shares"] -= quantity
            portfolio["totalValue"] -= total_value
            if holding["shares"] == 0:
                portfolio["holdings"] = [h for h in portfolio["holdings"] if h["symbol"] != symbol]

        trade = {
            "userId": user_id, "symbol": symbol, "action": action,
            "quantity": quantity, "price": price, "totalValue": total_value,
            "date": datetime.utcnow().isoformat() + "Z"
        }
        
        self.emit('trade:executed', trade)
        self._audit('trade_executed', trade)

        # Background Update with MERGE
        sql = """MERGE INTO portfolios t
                 USING (SELECT :userId AS user_id FROM dual) s
                 ON (t.user_id = s.user_id)
                 WHEN MATCHED THEN
                   UPDATE SET total_value = :totalValue, holdings = :holdings
                 WHEN NOT MATCHED THEN
                   INSERT (user_id, account_id, risk_tolerance, total_value, holdings)
                   VALUES (:userId, :accountId, :riskTolerance, :totalValue, :holdings)"""
                   
        binds = {
            "userId": user_id,
            "accountId": portfolio.get("accountId"),
            "riskTolerance": portfolio.get("riskTolerance"),
            "totalValue": portfolio["totalValue"],
            "holdings": json.dumps(portfolio["holdings"])
        }
        asyncio.create_task(oracle.execute(sql, binds))

        return trade

    # ─── Complaints ───
    def get_complaints_by_user_id(self, user_id):
        return [c for c in self.complaints if c["userId"] == user_id]

    def create_complaint(self, data):
        complaint = {
            "id": f"CMP-{str(uuid.uuid4())[:6].upper()}",
            "status": "open",
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "priority": "medium",
            **data
        }
        self.complaints.append(complaint)
        self.emit('complaint:created', complaint)
        self._audit('complaint_created', complaint)

        sql = """INSERT INTO complaints (id, user_id, subject, description, status, date_val, priority) 
                 VALUES (:id, :userId, :subject, :description, :status, :date_val, :priority)"""
        binds = {
            "id": complaint["id"],
            "userId": complaint["userId"],
            "subject": complaint["subject"],
            "description": complaint["description"],
            "status": complaint["status"],
            "date_val": complaint["date"],
            "priority": complaint["priority"]
        }
        asyncio.create_task(oracle.execute(sql, binds))
        return complaint

    def get_all_complaints(self):
        return self.complaints

    def update_complaint(self, complaint_id, updates):
        complaint = next((c for c in self.complaints if c["id"] == complaint_id), None)
        if not complaint:
            return None
        complaint.update(updates)
        self._audit('complaint_updated', complaint)

        sql = """UPDATE complaints SET 
                   status = :status, 
                   priority = :priority, 
                   subject = :subject, 
                   description = :description 
                 WHERE id = :id"""
        binds = {
            "status": complaint.get("status"),
            "priority": complaint.get("priority"),
            "subject": complaint.get("subject"),
            "description": complaint.get("description"),
            "id": complaint_id
        }
        asyncio.create_task(oracle.execute(sql, binds))
        return complaint

    # ─── Approval Queue ───
    def add_approval(self, data):
        approval = {
            "id": f"APR-{str(uuid.uuid4())[:8].upper()}",
            "status": "pending",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            **data
        }
        self.approval_queue.append(approval)
        self.emit('approval:pending', approval)
        self.emit('agent:trace', {
            "agent": data.get("agentName", "System"),
            "content": f"✋ Human approval requested for {data.get('type')}: {approval['id']}. Reason: {data.get('reason')}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        logger.warn(f"Human approval required: {approval['id']} — {approval.get('type')}", {"agent": "approval"})

        sql = """INSERT INTO approval_queue (id, user_id, type, status, reason, details, requested_at, resolved_at, reviewer_note) 
                 VALUES (:id, :userId, :type, :status, :reason, :details, :requestedAt, :resolvedAt, :reviewerNote)"""
        binds = {
            "id": approval["id"],
            "userId": approval.get("userId"),
            "type": approval.get("type"),
            "status": approval["status"],
            "reason": approval.get("reason"),
            "details": json.dumps(approval.get("details")),
            "requestedAt": approval["createdAt"],
            "resolvedAt": approval.get("resolvedAt"),
            "reviewerNote": approval.get("reviewerNote")
        }
        asyncio.create_task(oracle.execute(sql, binds))
        return approval

    def get_pending_approvals(self):
        return [a for a in self.approval_queue if a["status"] == "pending"]

    def resolve_approval(self, approval_id, decision, reviewer_note=''):
        approval = next((a for a in self.approval_queue if a["id"] == approval_id), None)
        if not approval:
            raise ValueError('Approval not found')
        
        approval["status"] = decision  # 'approved' or 'rejected'
        approval["resolvedAt"] = datetime.utcnow().isoformat() + "Z"
        approval["reviewerNote"] = reviewer_note
        
        self.emit(f"approval:{decision}", approval)
        self._audit(f"approval_{decision}", approval)
        logger.info(f"Approval {approval_id} {decision}", {"agent": "approval"})

        sql = """UPDATE approval_queue SET 
                   status = :status, 
                   resolved_at = :resolvedAt, 
                   reviewer_note = :reviewerNote 
                 WHERE id = :id"""
        binds = {
            "status": approval["status"],
            "resolvedAt": approval["resolvedAt"],
            "reviewerNote": approval["reviewerNote"],
            "id": approval_id
        }
        asyncio.create_task(oracle.execute(sql, binds))
        return approval

    # ─── Dashboard Stats ───
    def get_dashboard_stats(self, user_id):
        user_accounts = self.get_accounts_by_user_id(user_id)
        user_txns = self.get_transactions_by_user_id(user_id, 100)
        
        now = datetime.utcnow()
        limit_date = now - timedelta_days(30)
        
        recent_txns = []
        for t in user_txns:
            try:
                txn_date = parse_iso_datetime(t["date"])
                if txn_date and txn_date > limit_date:
                    recent_txns.append(t)
            except Exception:
                pass

        total_balance = sum(a["balance"] for a in user_accounts if a["type"] != "credit")
        total_debt = sum(abs(a["balance"]) for a in user_accounts if a["type"] == "credit")
        
        monthly_spending = sum(abs(t["amount"]) for t in recent_txns if t["amount"] < 0)
        monthly_income = sum(t["amount"] for t in recent_txns if t["amount"] > 0)

        return {
            "totalBalance": round(total_balance, 2),
            "totalDebt": round(total_debt, 2),
            "netWorth": round(total_balance - total_debt, 2),
            "monthlySpending": round(monthly_spending, 2),
            "monthlyIncome": round(monthly_income, 2),
            "accountCount": len(user_accounts),
            "recentTransactions": user_txns[:10],
            "pendingApprovals": len(self.get_pending_approvals()),
        }

    # ─── Audit ───
    def _audit(self, action, data):
        audit_id = f"AUD-{int(time_time_ms())}-{str(uuid.uuid4())[:4]}".upper()
        timestamp = datetime.utcnow().isoformat() + "Z"
        audit_item = {"id": audit_id, "action": action, "timestamp": timestamp, "data": data}
        
        self.audit_log.append(audit_item)
        if len(self.audit_log) > 1000:
            self.audit_log.pop(0)

        sql = """INSERT INTO audit_logs (id, action, timestamp, metadata) 
                 VALUES (:id, :action, :timestamp, :metadata)"""
        binds = {
            "id": audit_id,
            "action": action,
            "timestamp": timestamp,
            "metadata": json.dumps(data)
        }
        asyncio.create_task(oracle.execute(sql, binds))

    def get_audit_log(self, limit=50):
        return self.audit_log[-limit:]

    # ─── Market Data ───
    def get_market_data(self):
        return self.market_data

    # ─── Sessions ───
    def get_sessions(self, user_id):
        user_sess = [s for s in self.sessions if s["userId"] == user_id]
        user_sess.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
        return user_sess

    def get_session(self, session_id):
        return next((s for s in self.sessions if s["id"] == session_id), None)

    def create_session(self, id_val=None, user_id=None, title='New Chat'):
        session_id = id_val or f"sess-{str(uuid.uuid4())[:8]}"
        session = {
            "id": session_id,
            "userId": user_id,
            "title": title,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z",
            "lastAgent": None,
            "messages": [],
            "agentHistories": {}
        }
        self.sessions.append(session)
        
        # Use MERGE to prevent duplicate session errors
        sql = """MERGE INTO sessions t
                 USING (SELECT :id AS id FROM dual) s
                 ON (t.id = s.id)
                 WHEN MATCHED THEN
                   UPDATE SET user_id = :userId, title = :title, updated_at = :updatedAt, messages = :messages, agent_histories = :agentHistories
                 WHEN NOT MATCHED THEN
                   INSERT (id, user_id, title, updated_at, messages, agent_histories)
                   VALUES (:id, :userId, :title, :updatedAt, :messages, :agentHistories)"""
                   
        binds = {
            "id": session["id"],
            "userId": session["userId"],
            "title": session["title"],
            "updatedAt": session["updatedAt"],
            "messages": json.dumps(session["messages"]),
            "agentHistories": json.dumps(session["agentHistories"])
        }
        asyncio.create_task(oracle.execute(sql, binds))
        return session

    def delete_session(self, session_id):
        session = self.get_session(session_id)
        if session:
            self.sessions.remove(session)
            asyncio.create_task(oracle.execute(
                "DELETE FROM sessions WHERE id = :id",
                {"id": session_id}
            ))
            return True
        return False

    def update_session(self, session_id, updates):
        session = self.get_session(session_id)
        if session:
            session.update(updates)
            session["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            
            sql = """UPDATE sessions SET 
                       title = :title, 
                       updated_at = :updatedAt, 
                       messages = :messages, 
                       agent_histories = :agentHistories 
                     WHERE id = :id"""
            binds = {
                "title": session["title"],
                "updatedAt": session["updatedAt"],
                "messages": json.dumps(session["messages"]),
                "agentHistories": json.dumps(session["agentHistories"]),
                "id": session_id
            }
            asyncio.create_task(oracle.execute(sql, binds))
            return session
        return None

    def add_message_to_session(self, session_id, message):
        session = self.get_session(session_id)
        if session:
            new_msg = {
                "id": f"msg-{str(uuid.uuid4())[:8]}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                **message
            }
            session["messages"].append(new_msg)
            if len(session["messages"]) > 200:
                session["messages"].pop(0)
            session["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            
            sql = """UPDATE sessions SET 
                       messages = :messages, 
                       updated_at = :updatedAt 
                     WHERE id = :id"""
            binds = {
                "messages": json.dumps(session["messages"]),
                "updatedAt": session["updatedAt"],
                "id": session_id
            }
            asyncio.create_task(oracle.execute(sql, binds))
            return session
        return None

    def get_agent_history(self, session_id, agent_name):
        session = self.get_session(session_id)
        if session and "agentHistories" in session:
            return session["agentHistories"].get(agent_name) or []
        return []

    def save_agent_history(self, session_id, agent_name, history):
        session = self.get_session(session_id)
        if session:
            if "agentHistories" not in session or session["agentHistories"] is None:
                session["agentHistories"] = {}
            session["agentHistories"][agent_name] = history
            session["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            
            sql = """UPDATE sessions SET 
                       agent_histories = :agentHistories, 
                       updated_at = :updatedAt 
                     WHERE id = :id"""
            binds = {
                "agentHistories": json.dumps(session["agentHistories"]),
                "updatedAt": session["updatedAt"],
                "id": session_id
            }
            asyncio.create_task(oracle.execute(sql, binds))
            return True
        return False

    # ─── Bankers ───
    def get_banker_by_username(self, username):
        return next((b for b in self.bankers if b["username"] == username), None)

    def get_banker_by_id(self, banker_id):
        return next((b for b in self.bankers if b["id"] == banker_id), None)

    # ─── Payments ─────────────────────────────────────────────────────────

    def create_payment(self, data):
        payment = {
            "id": f"PAY-{str(uuid.uuid4())[:8].upper()}",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z",
            "status": "processing",
            **data
        }
        self.payments.insert(0, payment)
        self.emit('payment:created', payment)
        self._audit('payment_created', {"id": payment["id"], "amount": payment.get("amount"), "status": payment["status"]})
        return payment

    def get_payment_by_id(self, payment_id):
        return next((p for p in self.payments if p["id"] == payment_id), None)

    def update_payment(self, payment_id, updates):
        payment = self.get_payment_by_id(payment_id)
        if payment:
            payment.update(updates)
            payment["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            self.emit('payment:updated', payment)
        return payment

    def get_payments_by_user_id(self, user_id, limit=50):
        pays = [p for p in self.payments if p.get("userId") == user_id]
        pays.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return pays[:limit]

    def get_all_payments(self, status=None, limit=100):
        pays = self.payments[:]
        if status:
            pays = [p for p in pays if p.get("status") == status]
        pays.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return pays[:limit]

    def get_payment_analytics(self):
        from collections import Counter
        pays = self.payments
        total = len(pays)
        total_volume = sum(p.get("amount", 0) for p in pays)
        by_status = dict(Counter(p.get("status", "unknown") for p in pays))
        by_rail = dict(Counter(p.get("rail", "unknown") for p in pays if p.get("rail")))
        completed = [p for p in pays if p.get("status") == "completed"]
        success_rate = round(len(completed) / total * 100, 1) if total > 0 else 0
        return {
            "total": total,
            "totalVolume": round(total_volume, 2),
            "byStatus": by_status,
            "byRail": by_rail,
            "successRate": success_rate
        }


# Helper function mocks/stubs
def random_between(val1, val2):
    import random
    return round(random.uniform(val1, val2), 2)

def timedelta_days(days):
    from datetime import timedelta
    return timedelta(days=days)

def time_time_ms():
    import time
    return int(time.time() * 1000)

def parse_iso_datetime(iso_str):
    try:
        # Strip trailing Z if present and parse
        s = iso_str.replace("Z", "")
        return datetime.fromisoformat(s)
    except Exception:
        return None

data_store = DataStore()

# ─── Seed sample payments for demo ─────────────────────────────────────────
def _seed_payments():
    from datetime import timedelta
    now = datetime.utcnow()

    _sample_payments = [
        {
            "id": "PAY-DEMO0001",
            "userId": "user-001",
            "fromAccountId": "acc-001",
            "toAccountId": "acc-ext-001",
            "beneficiaryName": "Infosys Ltd",
            "beneficiaryAccount": "1234567890",
            "amount": 75000.00,
            "currency": "INR",
            "paymentType": "domestic",
            "urgency": "standard",
            "rail": "IMPS",
            "estimatedFee": 5.90,
            "settlementTime": "Instant (<30s)",
            "reference": "INV-2025-0042",
            "description": "Vendor payment for IT services",
            "status": "completed",
            "reconciliationStatus": "reconciled",
            "transactionId": "TXN-DEMO0001",
            "completedAt": (now - timedelta(hours=2)).isoformat() + "Z",
            "createdAt": (now - timedelta(hours=2, minutes=1)).isoformat() + "Z",
            "updatedAt": (now - timedelta(hours=2)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0002",
            "userId": "user-001",
            "fromAccountId": "acc-001",
            "toAccountId": "acc-ext-002",
            "beneficiaryName": "Tata Consultancy Services",
            "beneficiaryAccount": "9876543210",
            "amount": 1500000.00,
            "currency": "INR",
            "paymentType": "domestic",
            "urgency": "urgent",
            "rail": "RTGS",
            "estimatedFee": 59.00,
            "settlementTime": "Real-time (30 min cutoff)",
            "reference": "PO-2025-0099",
            "description": "Large vendor settlement — Q2 contract",
            "status": "held",
            "approvalId": "APR-DEMO0001",
            "holdReason": "Amount ₹15,00,000.00 exceeds ₹5,00,000 HITL threshold",
            "createdAt": (now - timedelta(hours=1)).isoformat() + "Z",
            "updatedAt": (now - timedelta(hours=1)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0003",
            "userId": "user-002",
            "fromAccountId": "acc-002",
            "toAccountId": "acc-ext-003",
            "beneficiaryName": "Global Tech Inc",
            "beneficiaryAccount": "US987654321",
            "amount": 250000.00,
            "currency": "USD",
            "paymentType": "international",
            "urgency": "standard",
            "rail": "SWIFT",
            "estimatedFee": 1180.00,
            "settlementTime": "1-3 business days",
            "reference": "WIRE-2025-0012",
            "description": "International software license fee",
            "status": "held",
            "approvalId": "APR-DEMO0002",
            "holdReason": "SWIFT/international payment requires compliance approval",
            "createdAt": (now - timedelta(minutes=45)).isoformat() + "Z",
            "updatedAt": (now - timedelta(minutes=45)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0004",
            "userId": "user-003",
            "fromAccountId": "acc-003",
            "toAccountId": "acc-004",
            "beneficiaryName": "Priya Sharma (Internal)",
            "beneficiaryAccount": "acc-004",
            "amount": 25000.00,
            "currency": "INR",
            "paymentType": "internal",
            "urgency": "standard",
            "rail": "Internal",
            "estimatedFee": 0,
            "settlementTime": "Instant",
            "reference": "SPLIT-042",
            "description": "Rent split — June",
            "status": "completed",
            "reconciliationStatus": "reconciled",
            "transactionId": "TXN-DEMO0002",
            "completedAt": (now - timedelta(days=1)).isoformat() + "Z",
            "createdAt": (now - timedelta(days=1, minutes=1)).isoformat() + "Z",
            "updatedAt": (now - timedelta(days=1)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0005",
            "userId": "user-001",
            "fromAccountId": "acc-001",
            "toAccountId": "acc-ext-005",
            "beneficiaryName": "HDFC Bank EMI",
            "beneficiaryAccount": "5556667778",
            "amount": 12500.00,
            "currency": "INR",
            "paymentType": "domestic",
            "urgency": "standard",
            "rail": "NEFT",
            "estimatedFee": 17.70,
            "settlementTime": "30 minutes (batch)",
            "reference": "EMI-JUNE-2025",
            "description": "Home loan EMI — June 2025",
            "status": "completed",
            "reconciliationStatus": "reconciled",
            "transactionId": "TXN-DEMO0003",
            "completedAt": (now - timedelta(days=2)).isoformat() + "Z",
            "createdAt": (now - timedelta(days=2, minutes=2)).isoformat() + "Z",
            "updatedAt": (now - timedelta(days=2)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0006",
            "userId": "user-002",
            "fromAccountId": "acc-002",
            "toAccountId": "acc-ext-006",
            "beneficiaryName": "Rajesh Kumar",
            "beneficiaryAccount": "7778889990",
            "amount": 5000.00,
            "currency": "INR",
            "paymentType": "domestic",
            "urgency": "standard",
            "rail": "UPI",
            "estimatedFee": 0,
            "settlementTime": "Instant (<10s)",
            "reference": "UPI-REF-8821",
            "description": "Freelance payment — logo design",
            "status": "failed",
            "rejectionReason": "Beneficiary UPI handle inactive",
            "createdAt": (now - timedelta(days=3)).isoformat() + "Z",
            "updatedAt": (now - timedelta(days=3)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0007",
            "userId": "user-003",
            "fromAccountId": "acc-003",
            "toAccountId": "acc-ext-007",
            "beneficiaryName": "Amazon Seller Services",
            "beneficiaryAccount": "1112223334",
            "amount": 98500.00,
            "currency": "INR",
            "paymentType": "domestic",
            "urgency": "urgent",
            "rail": "IMPS",
            "estimatedFee": 5.90,
            "settlementTime": "Instant (<30s)",
            "reference": "ORDER-AMZ-2025-5523",
            "description": "Marketplace settlement — May batch",
            "status": "completed",
            "reconciliationStatus": "exception",
            "exceptionType": "AMOUNT",
            "exceptionReason": "Settlement amount mismatch — received ₹97,500 vs expected ₹98,500",
            "transactionId": "TXN-DEMO0004",
            "completedAt": (now - timedelta(days=1, hours=5)).isoformat() + "Z",
            "createdAt": (now - timedelta(days=1, hours=5, minutes=1)).isoformat() + "Z",
            "updatedAt": (now - timedelta(days=1, hours=5)).isoformat() + "Z",
        },
        {
            "id": "PAY-DEMO0008",
            "userId": "user-001",
            "fromAccountId": "acc-001",
            "toAccountId": "acc-ext-008",
            "beneficiaryName": "Zomato Corporate",
            "beneficiaryAccount": "9998887776",
            "amount": 3200.00,
            "currency": "INR",
            "paymentType": "domestic",
            "urgency": "standard",
            "rail": "UPI",
            "estimatedFee": 0,
            "settlementTime": "Instant (<10s)",
            "reference": "CORP-MEAL-JUN25",
            "description": "Corporate meal allowance reimbursement",
            "status": "processing",
            "createdAt": (now - timedelta(minutes=5)).isoformat() + "Z",
            "updatedAt": (now - timedelta(minutes=5)).isoformat() + "Z",
        },
    ]

    for p in _sample_payments:
        data_store.payments.append(p)

_seed_payments()
