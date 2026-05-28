import re

def validate_transfer_request(data):
    errors = []
    from_id = data.get("fromAccountId")
    to_id = data.get("toAccountId")
    amount = data.get("amount")
    
    try:
        amount_val = float(amount) if amount is not None else 0
    except (ValueError, TypeError):
        amount_val = 0
        errors.append("Amount must be a valid number")

    if not from_id:
        errors.append("Source account ID is required")
    if not to_id:
        errors.append("Destination account ID is required")
    if amount is None or amount_val <= 0:
        errors.append("Amount must be a positive number")
    elif amount_val > 5000000:
        errors.append("Amount exceeds maximum single transfer limit (₹50,00,000)")
    if from_id and to_id and from_id == to_id:
        errors.append("Source and destination accounts cannot be the same")

    return {"isValid": len(errors) == 0, "errors": errors}

def validate_loan_application(data):
    errors = []
    user_id = data.get("userId")
    amount = data.get("amount")
    purpose = data.get("purpose")
    term_months = data.get("termMonths")

    try:
        amount_val = float(amount) if amount is not None else 0
    except (ValueError, TypeError):
        amount_val = 0
        errors.append("Amount must be a valid number")

    try:
        term_val = int(term_months) if term_months is not None else 0
    except (ValueError, TypeError):
        term_val = 0
        errors.append("Term months must be a valid number")

    if not user_id:
        errors.append("User ID is required")
    if amount is None or amount_val <= 0:
        errors.append("Loan amount must be positive")
    elif amount_val > 10000000:
        errors.append("Loan amount exceeds maximum (₹1,00,00,000)")
    if not purpose:
        errors.append("Loan purpose is required")
    if term_months is None or term_val < 6 or term_val > 360:
        errors.append("Loan term must be between 6 and 360 months")

    return {"isValid": len(errors) == 0, "errors": errors}

def validate_trade_request(data):
    errors = []
    user_id = data.get("userId")
    symbol = data.get("symbol")
    action = data.get("action")
    quantity = data.get("quantity")

    try:
        qty_val = float(quantity) if quantity is not None else 0
    except (ValueError, TypeError):
        qty_val = 0
        errors.append("Quantity must be a valid number")

    if not user_id:
        errors.append("User ID is required")
    if not symbol:
        errors.append("Stock/fund symbol is required")
    if not action or action not in ["buy", "sell"]:
        errors.append('Action must be "buy" or "sell"')
    if quantity is None or qty_val <= 0:
        errors.append("Quantity must be a positive number")

    return {"isValid": len(errors) == 0, "errors": errors}

def sanitize_input(val):
    if not isinstance(val, str):
        return val
    # Remove angle brackets to prevent basic HTML injection
    return re.sub(r"[<>]", "", val).strip()

def format_currency(amount):
    try:
        val = int(round(float(amount)))
    except (ValueError, TypeError):
        return f"₹{amount}"
    
    sign = "-" if val < 0 else ""
    val = abs(val)
    s = str(val)
    if len(s) <= 3:
        return f"{sign}₹{s}"
    else:
        last_three = s[-3:]
        remaining = s[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        formatted_remaining = ",".join(groups)
        return f"{sign}₹{formatted_remaining},{last_three}"

def mask_account_number(account_number):
    if not account_number or len(account_number) < 4:
        return "****"
    return "****" + account_number[-4:]

def mask_ssn(ssn):
    if not ssn:
        return "***-**-****"
    return "***-**-" + ssn[-4:]
