import asyncio
from datetime import datetime
from src.data.data_store import data_store
from src.utils.logger import logger

async def execute_approved_action(approval):
    approval_type = approval.get("type")
    details = approval.get("details", {})
    user_id = approval.get("userId")

    try:
        if approval_type == 'large_transfer':
            result = data_store.transfer_funds(
                details.get("fromAccountId"),
                details.get("toAccountId"),
                details.get("amount"),
                details.get("description")
            )
            logger.info(f"Approved transfer executed: {details.get('amount')}", {"agent": "approval"})
            return {
                "success": True,
                "message": f"Transfer of {details.get('amount'):,} has been executed and logged.",
                "result": result
            }

        elif approval_type == 'account_freeze':
            account = data_store.get_account_by_id(details.get("accountId"))
            if account:
                account["status"] = 'frozen'
                data_store.save()
                logger.info(f"Account {details.get('accountId')} frozen", {"agent": "approval"})
                return {"success": True, "message": f"Account {details.get('accountId')} has been frozen."}
            return {"success": False, "message": "Account not found."}

        elif approval_type in ('loan_approval', 'loan_application'):
            loan_id = details.get("loanId")
            loan = data_store.get_loan_by_id(loan_id)
            if loan:
                loan["status"] = 'active'
                # Disperse funds to primary checking account
                accounts = data_store.get_accounts_by_user_id(loan.get("userId"))
                checking = next((a for a in accounts if a.get("type") == 'checking'), None)
                if not checking and accounts:
                    checking = accounts[0]
                if checking:
                    checking["balance"] += loan.get("amount")
                    data_store.create_transaction(
                        account_id=checking.get("id"),
                        user_id=loan.get("userId"),
                        type_val='credit',
                        amount=loan.get("amount"),
                        merchant='AgenticBank Loan Dispersal',
                        category='Income',
                        description=f"Loan {loan.get('id')} funds dispersed after banker approval."
                    )
                data_store.save()
                logger.info(f"Loan {loan_id} activated and funds dispersed", {"agent": "approval"})
                return {
                    "success": True,
                    "message": f"Loan {loan_id} for ₹{loan.get('amount'):,} has been activated. Funds dispersed to {checking.get('name') if checking else 'account'}."
                }
            return {"success": False, "message": "Loan not found."}

        elif approval_type == 'high_value_trade':
            data_store.execute_trade(
                user_id,
                details.get("symbol"),
                details.get("action"),
                details.get("quantity"),
                details.get("price")
            )
            logger.info(f"Trade executed: {details.get('action')} {details.get('quantity')} {details.get('symbol')}", {"agent": "approval"})
            return {
                "success": True,
                "message": f"Trade executed: {details.get('action').upper()} {details.get('quantity')} {details.get('symbol')} @ ${details.get('price')}"
            }

        elif approval_type == 'kyc_review':
            user = data_store.get_user_by_id(user_id)
            if user:
                user["kycStatus"] = 'verified'
                user["kycDate"] = datetime.utcnow().strftime("%Y-%m-%d")
                data_store.save()
                logger.info(f"KYC verified for {user_id}", {"agent": "approval"})
                return {"success": True, "message": f"KYC verification completed for {user.get('firstName')} {user.get('lastName')}."}
            return {"success": False, "message": "User not found."}

        else:
            return {"success": False, "message": f"Unknown approval type: {approval_type}"}

    except Exception as error:
        logger.error(f"Approval execution failed: {str(error)}", {"agent": "approval"})
        return {"success": False, "message": str(error)}

def handle_rejection(approval):
    approval_type = approval.get("type")
    details = approval.get("details", {})

    if approval_type in ('loan_approval', 'loan_application') and details.get("loanId"):
        loan = data_store.get_loan_by_id(details.get("loanId"))
        if loan:
            loan["status"] = 'rejected'
            data_store.save()

    logger.info(f"Approval {approval.get('id')} rejected", {"agent": "approval"})
    return {"success": True, "message": f"Action {approval.get('id')} has been rejected."}
