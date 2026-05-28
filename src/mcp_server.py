"""
AgenticBank AI — MCP Server
========================
Exposes the AgenticBank AI banking backend as a set of MCP (Model Context Protocol) tools,
allowing external LLM clients (e.g., Claude Desktop, Cursor, custom AI agents) to
directly query, analyse, and act on banking data in real time.

Run this server from the project root:
    python src/mcp_server.py

Then register it in your MCP client config (see README for Claude Desktop example).
"""

import sys
import os
import json
import asyncio
import logging

# ── Path injection so imports work when run from project root ──────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from src.data.data_store import data_store
from src.utils.logger import logger

# Suppress noisy internal MCP/uvicorn logs so they don't corrupt stdio JSON-RPC
logging.getLogger("mcp").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)

# ── Initialize FastMCP Server ─────────────────────────────────────────────────
mcp = FastMCP(
    "AgenticBank AI",
    instructions=(
        "You are connected to the AgenticBank AI banking backend. "
        "You can query customer profiles, accounts, transactions, loans, portfolios, "
        "complaints, and the approval queue. You can also execute fund transfers "
        "and resolve pending approvals. Always confirm high-risk operations with the user."
    )
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _json(obj) -> str:
    """Serialize any object to a clean, indented JSON string."""
    def _default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, indent=2, default=_default)

def _strip_sensitive(user: dict) -> dict:
    """Remove fields that must never leave the backend."""
    sensitive = {"passwordHash", "password", "ssn", "pin"}
    return {k: v for k, v in user.items() if k not in sensitive}


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER & PROFILE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_user_profile(user_id: str) -> str:
    """
    Retrieve the complete profile for a customer including their name, contact
    information, KYC status, credit score, risk profile, employer details, and
    annual income. Sensitive fields like SSN and password hashes are stripped.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    user = data_store.get_user_by_id(user_id)
    if not user:
        return f"Error: No user found with ID '{user_id}'."
    return _json(_strip_sensitive(user))


@mcp.tool()
def list_all_users() -> str:
    """
    List all customers registered in the system with their IDs, names, KYC status,
    credit scores, and risk profiles. Sensitive fields are redacted.
    Useful for getting an overview of the customer base.
    """
    users = data_store.get_users()
    safe = [_strip_sensitive(u) for u in users]
    # Return a lightweight summary view
    summary = [
        {
            "id": u.get("id"),
            "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
            "email": u.get("email"),
            "kycStatus": u.get("kycStatus"),
            "creditScore": u.get("creditScore"),
            "riskProfile": u.get("riskProfile"),
        }
        for u in safe
    ]
    return _json(summary)


@mcp.tool()
def get_financial_intelligence(user_id: str) -> str:
    """
    Fetch a customer's computed financial intelligence report including:
    - Monthly income and total monthly debt obligations
    - Debt-to-Income (DTI) ratio
    - Existing mortgage details (if any)

    This is the primary tool to assess a customer's creditworthiness.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    intel = data_store.get_financial_intelligence(user_id)
    if not intel:
        return f"Error: No financial data found for user '{user_id}'."
    return _json(intel)


@mcp.tool()
def get_dashboard_stats(user_id: str) -> str:
    """
    Retrieve a user's dashboard summary: total balance across all accounts, total
    debt, net worth, 30-day spending and income totals, account count, pending
    approvals count, and the 10 most recent transactions.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    stats = data_store.get_dashboard_stats(user_id)
    return _json(stats)


# ══════════════════════════════════════════════════════════════════════════════
# ACCOUNT TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_accounts(user_id: str) -> str:
    """
    List all bank accounts belonging to a customer: checking, savings, and credit
    card accounts. Returns account IDs, names, balances, account numbers, status,
    interest rates, and credit limits where applicable.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    accounts = data_store.get_accounts_by_user_id(user_id)
    return _json(accounts)


@mcp.tool()
def get_account_details(account_id: str) -> str:
    """
    Retrieve the full details of a single bank account by its ID.

    Args:
        account_id: The account identifier (e.g. 'ACC-1001').
    """
    account = data_store.get_account_by_id(account_id)
    if not account:
        return f"Error: No account found with ID '{account_id}'."
    return _json(account)


@mcp.tool()
def get_total_balance(user_id: str) -> str:
    """
    Calculate and return the total combined balance across all non-credit accounts
    for a user (sum of checking + savings balances).

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    total = data_store.get_total_balance(user_id)
    return _json({"userId": user_id, "totalBalance": total, "currency": "INR"})


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_transactions(user_id: str, limit: int = 20) -> str:
    """
    Retrieve a list of recent transactions across all of a user's accounts,
    sorted by date descending. Returns type, amount, description, date, and status.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
        limit: Maximum number of transactions to return (default: 20, max: 50).
    """
    limit = min(max(1, limit), 50)
    txns = data_store.get_transactions_by_user_id(user_id, limit)
    return _json(txns)


@mcp.tool()
def get_account_transactions(account_id: str, limit: int = 20) -> str:
    """
    Retrieve transactions for a specific account (rather than all user accounts).

    Args:
        account_id: The account identifier (e.g. 'ACC-1001').
        limit: Maximum number of transactions to return (default: 20, max: 50).
    """
    limit = min(max(1, limit), 50)
    txns = data_store.get_transactions_by_account_id(account_id, limit)
    return _json(txns)


@mcp.tool()
def transfer_funds(
    from_account_id: str,
    to_account_id: str,
    amount: float,
    description: str = "MCP-Initiated Transfer"
) -> str:
    """
    Execute a fund transfer between two accounts and persist it to the Oracle
    ledger. The transfer is written immediately to the in-memory cache and
    asynchronously to the database.

    ⚠️  HUMAN-IN-THE-LOOP RULE: Any transfer exceeding ₹10,000 is automatically
    blocked and placed into the pending approval queue. A banker must manually
    approve it from the Banker Command Center before funds are moved.

    Args:
        from_account_id: Source account ID (e.g. 'ACC-1001').
        to_account_id: Destination account ID (e.g. 'ACC-1002').
        amount: Amount to transfer in INR (must be positive).
        description: Optional memo/description for the transfer.
    """
    if amount <= 0:
        return "Error: Transfer amount must be a positive number."
    try:
        result = data_store.transfer_funds(from_account_id, to_account_id, amount, description)
        if result.get("status") == "pending_approval":
            return _json({
                "status": "pending_approval",
                "message": f"Transfer of ₹{amount:,.2f} exceeds the ₹10,000 threshold and requires banker approval.",
                "approvalId": result.get("approvalId"),
                "transactionId": result.get("id"),
            })
        return _json({
            "status": "success",
            "message": f"₹{amount:,.2f} transferred successfully.",
            "transactionId": result.get("id"),
        })
    except Exception as e:
        return f"Error executing transfer: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# LOAN TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_loans(user_id: str) -> str:
    """
    Retrieve all loan records for a customer, including loan type, amount,
    remaining balance, interest rate, monthly payment, status, and start date.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    loans = data_store.get_loans_by_user_id(user_id)
    return _json(loans)


@mcp.tool()
def get_loan_details(loan_id: str) -> str:
    """
    Retrieve the full details of a specific loan by its ID.

    Args:
        loan_id: The loan identifier (e.g. 'LOAN-AB12CD').
    """
    loan = data_store.get_loan_by_id(loan_id)
    if not loan:
        return f"Error: No loan found with ID '{loan_id}'."
    return _json(loan)


# ══════════════════════════════════════════════════════════════════════════════
# INVESTMENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_portfolio(user_id: str) -> str:
    """
    Retrieve a customer's investment portfolio, including all stock holdings,
    quantities (shares), average cost basis, current prices, and total portfolio value.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    portfolio = data_store.get_portfolio_by_user_id(user_id)
    if not portfolio:
        return f"Error: No investment portfolio found for user '{user_id}'."
    return _json(portfolio)


@mcp.tool()
def get_market_data() -> str:
    """
    Retrieve current market data for all stocks tracked by the system, including
    symbols, company names, current prices, day change percentages, and sector.
    Useful for evaluating investment decisions or monitoring positions.
    """
    data = data_store.get_market_data()
    return _json(data)


# ══════════════════════════════════════════════════════════════════════════════
# COMPLAINT TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_complaints(user_id: str) -> str:
    """
    Retrieve all support complaints or service requests filed by a customer.
    Returns complaint ID, subject, description, priority, status, and date.

    Args:
        user_id: The unique user identifier (e.g. 'USR-001').
    """
    complaints = data_store.get_complaints_by_user_id(user_id)
    return _json(complaints)


@mcp.tool()
def create_complaint(user_id: str, subject: str, description: str) -> str:
    """
    File a new customer support complaint or service request on behalf of a user.
    The complaint is automatically assigned 'open' status with 'medium' priority.

    Args:
        user_id: The user filing the complaint (e.g. 'USR-001').
        subject: A short title describing the issue.
        description: Full detailed description of the complaint.
    """
    try:
        complaint = data_store.create_complaint({
            "userId": user_id,
            "subject": subject,
            "description": description,
        })
        return _json({
            "status": "success",
            "complaintId": complaint.get("id"),
            "message": f"Complaint '{subject}' filed successfully.",
        })
    except Exception as e:
        return f"Error creating complaint: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# APPROVAL QUEUE TOOLS (Banker / Compliance Operations)
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_pending_approvals() -> str:
    """
    Fetch the complete list of items currently in the human approval queue.
    These are high-value transactions, loan applications, or flagged compliance
    actions that require a banker's review before execution.

    Only users with the Compliance Officer or Manager role should action these.
    """
    approvals = data_store.get_pending_approvals()
    if not approvals:
        return _json({"message": "No items are currently pending approval.", "count": 0})
    return _json({"count": len(approvals), "items": approvals})


@mcp.tool()
def resolve_approval(approval_id: str, decision: str, reviewer_note: str = "") -> str:
    """
    Approve or reject an item in the human approval queue. This is a privileged
    action — the decision is logged in the audit trail and the associated
    transaction/loan is updated accordingly.

    ⚠️  This action is irreversible once committed.

    Args:
        approval_id: The approval queue item ID (e.g. 'APR-12345678').
        decision: Either 'approved' or 'rejected'.
        reviewer_note: Optional explanation for the decision (recommended).
    """
    if decision not in ("approved", "rejected"):
        return "Error: Decision must be either 'approved' or 'rejected'."
    try:
        result = data_store.resolve_approval(approval_id, decision, reviewer_note)
        return _json({
            "status": "success",
            "approvalId": approval_id,
            "decision": decision,
            "resolvedAt": result.get("resolvedAt"),
        })
    except Exception as e:
        return f"Error resolving approval: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT & COMPLIANCE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_audit_log(limit: int = 30) -> str:
    """
    Retrieve the most recent entries from the system audit log. Every state-changing
    operation (transfers, trades, loan applications, approvals) generates an audit
    entry with a timestamp, action type, and full data snapshot.

    Args:
        limit: Number of recent log entries to return (default: 30, max: 100).
    """
    limit = min(max(1, limit), 100)
    log = data_store.get_audit_log(limit)
    return _json(log)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def _init_db():
    """Initialize Oracle DB connection pool and load all data into cache."""
    logger.info("MCP Server: Initializing data store...", {"agent": "system"})
    await data_store.init()
    logger.info("MCP Server: Data store ready. Starting MCP stdio loop.", {"agent": "system"})

def main():
    asyncio.run(_init_db())
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
