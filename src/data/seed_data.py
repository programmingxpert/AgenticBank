import uuid
import random
from datetime import datetime, timedelta

# --- Users ---
users = [
    {
        "id": "USR-001", "firstName": "Sarah", "lastName": "Mitchell", "email": "sarah.mitchell@email.com",
        "phone": "+1-415-555-0142", "dob": "1988-03-15", "ssn": "***-**-4521",
        "address": { "street": "742 Evergreen Terrace", "city": "San Francisco", "state": "CA", "zip": "94102" },
        "occupation": "Software Engineering Manager", "employer": "Stripe Inc.",
        "annualIncome": 19600000, "creditScore": 782, "kycStatus": "verified", "kycDate": "2024-01-10",
        "riskProfile": "moderate", "joinDate": "2019-06-12"
    },
    {
        "id": "USR-002", "firstName": "James", "lastName": "Rodriguez", "email": "j.rodriguez@email.com",
        "phone": "+1-212-555-0198", "dob": "1975-11-22", "ssn": "***-**-8834",
        "address": { "street": "88 Central Park West", "city": "New York", "state": "NY", "zip": "10023" },
        "occupation": "Hedge Fund Partner", "employer": "Citadel Securities",
        "annualIncome": 71200000, "creditScore": 810, "kycStatus": "verified", "kycDate": "2023-08-05",
        "riskProfile": "aggressive", "joinDate": "2018-02-20"
    },
    {
        "id": "USR-003", "firstName": "Priya", "lastName": "Sharma", "email": "priya.s@email.com",
        "phone": "+1-512-555-0267", "dob": "1995-07-08", "ssn": "***-**-1156",
        "address": { "street": "2200 Lake Austin Blvd", "city": "Austin", "state": "TX", "zip": "78703" },
        "occupation": "Graduate Student", "employer": "UT Austin",
        "annualIncome": 2560000, "creditScore": 680, "kycStatus": "verified", "kycDate": "2024-05-18",
        "riskProfile": "conservative", "joinDate": "2023-09-01"
    },
    {
        "id": "USR-004", "firstName": "Robert", "lastName": "Chen", "email": "r.chen@email.com",
        "phone": "+1-206-555-0331", "dob": "1962-01-30", "ssn": "***-**-7743",
        "address": { "street": "456 Pine St", "city": "Seattle", "state": "WA", "zip": "98101" },
        "occupation": "Retired — Former CTO", "employer": "N/A",
        "annualIncome": 9600000, "creditScore": 805, "kycStatus": "verified", "kycDate": "2023-11-02",
        "riskProfile": "conservative", "joinDate": "2017-04-15"
    },
    {
        "id": "USR-005", "firstName": "Maria", "lastName": "Gonzalez", "email": "maria.g@email.com",
        "phone": "+1-305-555-0455", "dob": "1990-09-12", "ssn": "***-**-3390",
        "address": { "street": "1200 Brickell Ave", "city": "Miami", "state": "FL", "zip": "33131" },
        "occupation": "Restaurant Owner", "employer": "Casa de Maria LLC",
        "annualIncome": 14000000, "creditScore": 720, "kycStatus": "verified", "kycDate": "2024-02-14",
        "riskProfile": "moderate", "joinDate": "2020-11-08"
    },
    {
        "id": "USR-006", "firstName": "David", "lastName": "Okonkwo", "email": "d.okonkwo@email.com",
        "phone": "+1-312-555-0589", "dob": "1985-04-25", "ssn": "***-**-6618",
        "address": { "street": "333 N Michigan Ave", "city": "Chicago", "state": "IL", "zip": "60601" },
        "occupation": "Cardiologist", "employer": "Northwestern Memorial Hospital",
        "annualIncome": 33600000, "creditScore": 795, "kycStatus": "verified", "kycDate": "2024-03-20",
        "riskProfile": "moderate", "joinDate": "2019-01-30"
    },
    {
        "id": "USR-007", "firstName": "Emily", "lastName": "Watson", "email": "e.watson@email.com",
        "phone": "+1-720-555-0612", "dob": "1998-12-03", "ssn": "***-**-2247",
        "address": { "street": "1600 Champa St", "city": "Denver", "state": "CO", "zip": "80202" },
        "occupation": "Freelance Designer", "employer": "Self-employed",
        "annualIncome": 5440000, "creditScore": 695, "kycStatus": "pending", "kycDate": None,
        "riskProfile": "moderate", "joinDate": "2024-01-15"
    },
    {
        "id": "USR-008", "firstName": "Michael", "lastName": "Thompson", "email": "m.thompson@email.com",
        "phone": "+1-404-555-0778", "dob": "1970-06-18", "ssn": "***-**-9901",
        "address": { "street": "500 Peachtree St NE", "city": "Atlanta", "state": "GA", "zip": "30308" },
        "occupation": "Real Estate Developer", "employer": "Thompson Properties Group",
        "annualIncome": 44000000, "creditScore": 760, "kycStatus": "flagged", "kycDate": "2023-06-10",
        "riskProfile": "aggressive", "joinDate": "2018-08-22"
    }
]

# --- Accounts ---
accounts = [
    # Sarah Mitchell
    { "id": "ACC-1001", "userId": "USR-001", "type": "checking", "name": "Primary Checking", "balance": 1988053.60, "currency": "INR", "accountNumber": "****4521", "routingNumber": "****0108", "status": "active", "interestRate": 0.01, "creditLimit": 0.0 },
    { "id": "ACC-1002", "userId": "USR-001", "type": "savings", "name": "Emergency Fund", "balance": 6816000.0, "currency": "INR", "accountNumber": "****4522", "routingNumber": "****0108", "status": "active", "interestRate": 4.25, "creditLimit": 0.0 },
    { "id": "ACC-1003", "userId": "USR-001", "type": "credit", "name": "Platinum Visa", "balance": -3420.50, "currency": "INR", "accountNumber": "****7890", "creditLimit": 2000000.0, "status": "active", "interestRate": 18.99 },
    # James Rodriguez
    { "id": "ACC-2001", "userId": "USR-002", "type": "checking", "name": "Executive Checking", "balance": 27368036.0, "currency": "INR", "accountNumber": "****8834", "routingNumber": "****0202", "status": "active", "interestRate": 0.05, "creditLimit": 0.0 },
    { "id": "ACC-2002", "userId": "USR-002", "type": "savings", "name": "High-Yield Savings", "balance": 100000000.0, "currency": "INR", "accountNumber": "****8835", "routingNumber": "****0202", "status": "active", "interestRate": 4.50, "creditLimit": 0.0 },
    { "id": "ACC-2003", "userId": "USR-002", "type": "investment", "name": "Brokerage Account", "balance": 231200000.0, "currency": "INR", "accountNumber": "****8836", "routingNumber": "", "status": "active", "interestRate": 0.0, "creditLimit": 0.0 },
    # Priya Sharma
    { "id": "ACC-3001", "userId": "USR-003", "type": "checking", "name": "Student Checking", "balance": 187209.60, "currency": "INR", "accountNumber": "****1156", "routingNumber": "****0305", "status": "active", "interestRate": 0.0, "creditLimit": 0.0 },
    { "id": "ACC-3002", "userId": "USR-003", "type": "savings", "name": "Savings", "balance": 700000.0, "currency": "INR", "accountNumber": "****1157", "routingNumber": "****0305", "status": "active", "interestRate": 3.80, "creditLimit": 0.0 },
    # Robert Chen
    { "id": "ACC-4001", "userId": "USR-004", "type": "checking", "name": "Retirement Checking", "balance": 3648024.0, "currency": "INR", "accountNumber": "****7743", "routingNumber": "****0410", "status": "active", "interestRate": 0.02, "creditLimit": 0.0 },
    { "id": "ACC-4002", "userId": "USR-004", "type": "savings", "name": "Retirement Savings", "balance": 49600000.0, "currency": "INR", "accountNumber": "****7744", "routingNumber": "****0410", "status": "active", "interestRate": 4.50, "creditLimit": 0.0 },
    { "id": "ACC-4003", "userId": "USR-004", "type": "investment", "name": "IRA Account", "balance": 148000000.0, "currency": "INR", "accountNumber": "****7745", "routingNumber": "", "status": "active", "interestRate": 0.0, "creditLimit": 0.0 },
    # Maria Gonzalez
    { "id": "ACC-5001", "userId": "USR-005", "type": "checking", "name": "Business Checking", "balance": 5400064.0, "currency": "INR", "accountNumber": "****3390", "routingNumber": "****0515", "status": "active", "interestRate": 0.01, "creditLimit": 0.0 },
    { "id": "ACC-5002", "userId": "USR-005", "type": "savings", "name": "Personal Savings", "balance": 3360000.0, "currency": "INR", "accountNumber": "****3391", "routingNumber": "****0515", "status": "active", "interestRate": 4.00, "creditLimit": 0.0 },
    { "id": "ACC-5003", "userId": "USR-005", "type": "credit", "name": "Business Gold Card", "balance": -12800.00, "currency": "INR", "accountNumber": "****5567", "creditLimit": 4000000.0, "status": "active", "interestRate": 16.49 },
    # David Okonkwo
    { "id": "ACC-6001", "userId": "USR-006", "type": "checking", "name": "Premium Checking", "balance": 7144020.0, "currency": "INR", "accountNumber": "****6618", "routingNumber": "****0620", "status": "active", "interestRate": 0.03, "creditLimit": 0.0 },
    { "id": "ACC-6002", "userId": "USR-006", "type": "savings", "name": "High-Yield Savings", "balance": 25600000.0, "currency": "INR", "accountNumber": "****6619", "routingNumber": "****0620", "status": "active", "interestRate": 4.50, "creditLimit": 0.0 },
    { "id": "ACC-6003", "userId": "USR-006", "type": "investment", "name": "Investment Portfolio", "balance": 60000000.0, "currency": "INR", "accountNumber": "****6620", "routingNumber": "", "status": "active", "interestRate": 0.0, "creditLimit": 0.0 },
    # Emily Watson
    { "id": "ACC-7001", "userId": "USR-007", "type": "checking", "name": "Everyday Checking", "balance": 329672.0, "currency": "INR", "accountNumber": "****2247", "routingNumber": "****0725", "status": "active", "interestRate": 0.0, "creditLimit": 0.0 },
    { "id": "ACC-7002", "userId": "USR-007", "type": "savings", "name": "Rainy Day Fund", "balance": 1000000.0, "currency": "INR", "accountNumber": "****2248", "routingNumber": "****0725", "status": "active", "interestRate": 3.50, "creditLimit": 0.0 },
    # Michael Thompson
    { "id": "ACC-8001", "userId": "USR-008", "type": "checking", "name": "Business Premier", "balance": 18760000.0, "currency": "INR", "accountNumber": "****9901", "routingNumber": "****0830", "status": "active", "interestRate": 0.05, "creditLimit": 0.0 },
    { "id": "ACC-8002", "userId": "USR-008", "type": "savings", "name": "Development Reserve", "balance": 71200000.0, "currency": "INR", "accountNumber": "****9902", "routingNumber": "****0830", "status": "active", "interestRate": 4.25, "creditLimit": 0.0 },
    { "id": "ACC-8003", "userId": "USR-008", "type": "investment", "name": "Real Estate Fund", "balance": 256000000.0, "currency": "INR", "accountNumber": "****9903", "routingNumber": "", "status": "active", "interestRate": 0.0, "creditLimit": 0.0 },
    { "id": "ACC-8004", "userId": "USR-008", "type": "credit", "name": "Black Card", "balance": -45200.00, "currency": "INR", "accountNumber": "****1234", "creditLimit": 8000000.0, "status": "active", "interestRate": 14.99 }
]

# --- Transactions template ---
txnTemplates = [
    { "merchant": "Whole Foods Market", "category": "Groceries", "range": [2800, 22400] },
    { "merchant": "Amazon.com", "category": "Shopping", "range": [960, 36000] },
    { "merchant": "Netflix", "category": "Entertainment", "range": [1279.2, 1839.20] },
    { "merchant": "Spotify", "category": "Entertainment", "range": [799.2, 1359.20] },
    { "merchant": "Shell Gas Station", "category": "Fuel", "range": [2000, 6800] },
    { "merchant": "Starbucks", "category": "Dining", "range": [320, 960] },
    { "merchant": "Uber", "category": "Transportation", "range": [640, 5200] },
    { "merchant": "AT&T Wireless", "category": "Utilities", "range": [6000, 9600] },
    { "merchant": "PG&E Energy", "category": "Utilities", "range": [7200, 20000] },
    { "merchant": "Target", "category": "Shopping", "range": [1600, 14400] },
    { "merchant": "CVS Pharmacy", "category": "Healthcare", "range": [640, 7600] },
    { "merchant": "Chipotle", "category": "Dining", "range": [800, 1760] },
    { "merchant": "Delta Airlines", "category": "Travel", "range": [16000, 96000] },
    { "merchant": "Marriott Hotels", "category": "Travel", "range": [12000, 36000] },
    { "merchant": "Apple Store", "category": "Electronics", "range": [2320, 120000] },
    { "merchant": "Home Depot", "category": "Home", "range": [1200, 48000] },
    { "merchant": "Costco Wholesale", "category": "Groceries", "range": [6400, 28000] },
    { "merchant": "Zelle Transfer", "category": "Transfer", "range": [4000, 160000] },
    { "merchant": "Venmo Payment", "category": "Transfer", "range": [800, 40000] },
    { "merchant": "IRS Tax Payment", "category": "Tax", "range": [40000, 1200000] }
]

def random_between(val1, val2):
    return round(random.uniform(val1, val2), 2)

def random_date(days_back):
    d = datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )
    return d.isoformat() + "Z"

def generate_transactions(account_id, count, days_back=90):
    txns = []
    for _ in range(count):
        t = random.choice(txnTemplates)
        amount = random_between(t["range"][0], t["range"][1])
        is_debit = random.random() > 0.15
        
        txns.append({
            "id": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "accountId": account_id,
            "type": "debit" if is_debit else "credit",
            "amount": -amount if is_debit else amount,
            "merchant": t["merchant"] if is_debit else random.choice(['Payroll Deposit', 'Interest Payment', 'Refund', 'Wire Transfer In']),
            "category": t["category"] if is_debit else "Income",
            "description": f"Purchase at {t['merchant']}" if is_debit else "Incoming deposit",
            "date": random_date(days_back),
            "status": "completed",
            "riskScore": random_between(0.6, 0.95) if random.random() > 0.92 else random_between(0.01, 0.3)
        })
    txns.sort(key=lambda x: x["date"], reverse=True)
    return txns

transactions = (
    generate_transactions("ACC-1001", 45) +
    generate_transactions("ACC-2001", 60) +
    generate_transactions("ACC-3001", 25) +
    generate_transactions("ACC-4001", 30) +
    generate_transactions("ACC-5001", 50) +
    generate_transactions("ACC-6001", 40) +
    generate_transactions("ACC-7001", 20) +
    generate_transactions("ACC-8001", 55)
)

# --- Loans ---
loans = [
    { "id": "LOAN-001", "userId": "USR-001", "type": "mortgage", "amount": 52000000.0, "remainingBalance": 46400000.0, "interestRate": 6.25, "termMonths": 360, "monthlyPayment": 320206.4, "status": "active", "startDate": "2022-03-15", "purpose": "Primary residence purchase" },
    { "id": "LOAN-002", "userId": "USR-003", "type": "student", "amount": 3600000.0, "remainingBalance": 3056000.0, "interestRate": 5.50, "termMonths": 120, "monthlyPayment": 39060.8, "status": "active", "startDate": "2023-09-01", "purpose": "Graduate education - Computer Science" },
    { "id": "LOAN-003", "userId": "USR-005", "type": "business", "amount": 20000000.0, "remainingBalance": 15600000.0, "interestRate": 7.75, "termMonths": 60, "monthlyPayment": 403373.6, "status": "active", "startDate": "2023-01-20", "purpose": "Restaurant expansion and renovation" },
    { "id": "LOAN-004", "userId": "USR-006", "type": "auto", "amount": 6800000.0, "remainingBalance": 4960000.0, "interestRate": 4.90, "termMonths": 72, "monthlyPayment": 109104.0, "status": "active", "startDate": "2023-06-10", "purpose": "BMW X5 purchase" },
    { "id": "LOAN-005", "userId": "USR-008", "type": "commercial", "amount": 200000000.0, "remainingBalance": 168000000.0, "interestRate": 8.25, "termMonths": 240, "monthlyPayment": 1713600.0, "status": "active", "startDate": "2022-11-05", "purpose": "Commercial property development - Midtown Atlanta" },
    { "id": "LOAN-006", "userId": "USR-002", "type": "personal", "amount": 4000000.0, "remainingBalance": 0.0, "interestRate": 9.50, "termMonths": 36, "monthlyPayment": 128200.0, "status": "paid_off", "startDate": "2021-04-12", "purpose": "Home renovation" }
]

# --- Investment Portfolios ---
portfolios = [
    {
        "userId": "USR-002", "accountId": "ACC-2003", "riskTolerance": "aggressive", "totalValue": 231200000.0,
        "holdings": [
            { "symbol": "AAPL", "name": "Apple Inc.", "shares": 500, "avgCost": 11616.0, "currentPrice": 15880.0, "change": "+2.3%" },
            { "symbol": "NVDA", "name": "NVIDIA Corp", "shares": 300, "avgCost": 17600.0, "currentPrice": 70432.0, "change": "+4.1%" },
            { "symbol": "MSFT", "name": "Microsoft", "shares": 400, "avgCost": 22440.0, "currentPrice": 33216.0, "change": "+0.8%" },
            { "symbol": "GOOGL", "name": "Alphabet Inc", "shares": 200, "avgCost": 9600.0, "currentPrice": 13784.0, "change": "-0.5%" },
            { "symbol": "AMZN", "name": "Amazon.com", "shares": 250, "avgCost": 10400.0, "currentPrice": 14848.0, "change": "+1.2%" },
            { "symbol": "VOO", "name": "Vanguard S&P 500 ETF", "shares": 100, "avgCost": 30400.0, "currentPrice": 38816.0, "change": "+0.6%" }
        ]
    },
    {
        "userId": "USR-004", "accountId": "ACC-4003", "riskTolerance": "conservative", "totalValue": 148000000.0,
        "holdings": [
            { "symbol": "BND", "name": "Vanguard Total Bond ETF", "shares": 2000, "avgCost": 5800.0, "currentPrice": 5904.0, "change": "+0.1%" },
            { "symbol": "VTI", "name": "Vanguard Total Stock ETF", "shares": 1500, "avgCost": 14400.0, "currentPrice": 20432.0, "change": "+0.4%" },
            { "symbol": "SCHD", "name": "Schwab US Dividend ETF", "shares": 1200, "avgCost": 5200.0, "currentPrice": 6336.0, "change": "+0.3%" },
            { "symbol": "VNQ", "name": "Vanguard Real Estate ETF", "shares": 800, "avgCost": 6560.0, "currentPrice": 6848.0, "change": "-0.2%" },
            { "symbol": "TLT", "name": "iShares 20+ Year Treasury", "shares": 1000, "avgCost": 7600.0, "currentPrice": 7392.0, "change": "-0.4%" }
        ]
    },
    {
        "userId": "USR-006", "accountId": "ACC-6003", "riskTolerance": "moderate", "totalValue": 60000000.0,
        "holdings": [
            { "symbol": "VOO", "name": "Vanguard S&P 500 ETF", "shares": 400, "avgCost": 28000.0, "currentPrice": 38816.0, "change": "+0.6%" },
            { "symbol": "QQQ", "name": "Invesco QQQ Trust", "shares": 200, "avgCost": 25600.0, "currentPrice": 35664.0, "change": "+1.1%" },
            { "symbol": "JNJ", "name": "Johnson & Johnson", "shares": 300, "avgCost": 12400.0, "currentPrice": 12992.0, "change": "-0.3%" },
            { "symbol": "VXUS", "name": "Vanguard Intl Stock ETF", "shares": 500, "avgCost": 4160.0, "currentPrice": 4584.0, "change": "+0.5%" }
        ]
    },
    {
        "userId": "USR-008", "accountId": "ACC-8003", "riskTolerance": "aggressive", "totalValue": 256000000.0,
        "holdings": [
            { "symbol": "SPY", "name": "SPDR S&P 500 ETF", "shares": 1000, "avgCost": 33600.0, "currentPrice": 41624.0, "change": "+0.7%" },
            { "symbol": "TSLA", "name": "Tesla Inc", "shares": 800, "avgCost": 14400.0, "currentPrice": 19648.0, "change": "+3.2%" },
            { "symbol": "META", "name": "Meta Platforms", "shares": 500, "avgCost": 22400.0, "currentPrice": 38872.0, "change": "+1.8%" },
            { "symbol": "IYR", "name": "iShares US Real Estate", "shares": 2000, "avgCost": 6800.0, "currentPrice": 7368.0, "change": "+0.2%" },
            { "symbol": "XLF", "name": "Financial Select SPDR", "shares": 1500, "avgCost": 2720.0, "currentPrice": 3296.0, "change": "+0.9%" }
        ]
    }
]

# --- Complaints ---
complaints = [
    { "id": "CMP-001", "userId": "USR-003", "subject": "ATM fee dispute", "description": "Charged $5 ATM fee at partner bank location which should be free", "status": "open", "date": "2025-04-28", "priority": "medium" },
    { "id": "CMP-002", "userId": "USR-007", "subject": "Delayed direct deposit", "description": "Freelance payment from client not reflected after 5 business days", "status": "investigating", "date": "2025-05-01", "priority": "high" }
]

# --- Market Data ---
marketData = {
    "indices": [
        { "symbol": "SPX", "name": "S&P 500", "value": 5285.40, "change": "+0.82%" },
        { "symbol": "DJI", "name": "Dow Jones", "value": 39872.15, "change": "+0.45%" },
        { "symbol": "IXIC", "name": "NASDAQ", "value": 16742.80, "change": "+1.12%" }
    ],
    "rates": {
        "federalFunds": 5.25, "prime": 8.50, "mortgage30yr": 6.85, "mortgage15yr": 6.10, "savings": 4.50
    },
    "lastUpdated": datetime.utcnow().isoformat() + "Z"
}

# --- Bankers ---
bankers = [
    { 'username': 'agent1', 'name': 'Alex Rivera', 'role': 'Compliance Officer', 'passwordHash': '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92' }, # password: password
    { 'username': 'agent2', 'name': 'Sarah Chen', 'role': 'Fraud Analyst', 'passwordHash': '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92' }  # password: password
]

