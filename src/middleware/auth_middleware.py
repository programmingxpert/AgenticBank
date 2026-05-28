from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.utils.jwt_utils import verify_token
from src.data.data_store import data_store

security = HTTPBearer(auto_error=False)

async def get_current_banker(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing token")
        
    token = credentials.credentials
    decoded = verify_token(token)
    if not decoded or not decoded.get("bankerId"):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or expired token")
        
    banker = data_store.get_banker_by_id(decoded.get("bankerId"))
    if not banker:
        raise HTTPException(status_code=401, detail="Unauthorized: Agent profile not found")
        
    return banker

def require_role(allowed_roles):
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
        
    async def role_checker(banker: dict = Depends(get_current_banker)):
        if banker.get("role") not in allowed_roles:
            role_names = " or ".join(allowed_roles)
            raise HTTPException(status_code=403, detail=f"Forbidden: Insufficient privileges. Required role: {role_names}")
        return banker
        
    return role_checker
