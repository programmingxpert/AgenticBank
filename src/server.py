import os
import sys
# Automatically append the project root to sys.path so 'from src import...' works without PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core.utils.pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import json
import time
import math
import datetime
import asyncio
import hashlib
import uvicorn
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from contextlib import asynccontextmanager

from src.config import config, validate_config
from src.utils.logger import logger
from src.utils.jwt_utils import sign_token, verify_token
from src.data.data_store import data_store
from src.middleware.auth_middleware import get_current_banker, get_optional_banker, require_role
from src.middleware.human_approval import execute_approved_action, handle_rejection
from src.ai.orchestrator import route_message, route_banker_message, get_agent_info, AGENT_INFO
from src.ai.deepseek_client import is_api_configured, chat_completion
from src.ai.memory_agent import memory_agent
from src.agents.fraud_agent import fraud_agent
from src.agents.payment_orchestrator_agent import payment_orchestrator_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    warnings_list, errors, is_valid = validate_config()
    if not is_valid:
        for err in errors:
            logger.error(err, {"agent": "system"})
        os._exit(1)
        
    for warn in warnings_list:
        logger.warn(warn, {"agent": "system"})
        
    try:
        await data_store.init()
        
        import sys
        ai_status = '[CONNECTED]' if is_api_configured() else '[NOT CONFIGURED]'
        port = config.server['port']
        banner = (
            "\n  AgenticBank AI -- Autonomous Banking POC v2.2\n"
            f"  URL:  http://localhost:{port}\n"
            f"  Hub:  http://localhost:{port}/payment-hub\n"
            f"  AI:   DeepSeek {ai_status}\n"
        )
        try:
            sys.stdout.buffer.write(banner.encode('utf-8'))
            sys.stdout.buffer.flush()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Startup error: {e}", {"agent": "system"})
        os._exit(1)
    
    yield

app = FastAPI(title="AgenticBank AI", version="2.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── WebSocket Connection Manager ───────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug("WebSocket client connected", {"agent": "system"})
        try:
            await websocket.send_json({
                "event": "system:init",
                "data": {
                    "agentsActive": 6,
                    "mcpEnabled": True,
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                },
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            })
        except Exception as e:
            logger.error(f"WebSocket init send failed: {str(e)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event: str, data: Any):
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# ─── Event Forwarders ───────────────────────────────────────────────────────

async def on_transaction_created(txn):
    await manager.broadcast('transaction', txn)

async def on_transfer_completed(data):
    await manager.broadcast('transfer', data)

async def on_approval_pending(approval):
    await manager.broadcast('approval:pending', approval)

async def on_approval_approved(approval):
    await manager.broadcast('approval:resolved', {**approval, "decision": "approved"})

async def on_approval_rejected(approval):
    await manager.broadcast('approval:resolved', {**approval, "decision": "rejected"})

async def on_loan_created(loan):
    await manager.broadcast('loan', loan)

async def on_trade_executed(trade):
    await manager.broadcast('trade', trade)

async def on_agent_alert(alert):
    await manager.broadcast('agent:alert', alert)

async def on_agent_trace(trace):
    await manager.broadcast('agent:trace', trace)

async def on_memory_update(update):
    await manager.broadcast('memory:update', update)

data_store.on('transaction:created', on_transaction_created)
data_store.on('transfer:completed', on_transfer_completed)
data_store.on('approval:pending', on_approval_pending)
data_store.on('approval:approved', on_approval_approved)
data_store.on('approval:rejected', on_approval_rejected)
data_store.on('loan:created', on_loan_created)
data_store.on('trade:executed', on_trade_executed)
data_store.on('agent:alert', on_agent_alert)
data_store.on('agent:trace', on_agent_trace)
data_store.on('memory:update', on_memory_update)

async def on_transaction_high_risk(txn):
    logger.warn(f"High risk transaction detected! Triggering Fraud Agent.", {"agent": "system", "txnId": txn.get("id")})
    try:
        account = data_store.get_account_by_id(txn.get("accountId"))
        if account:
            data_store.emit('agent:alert', {
                "agent": 'Fraud Detection Agent',
                "userId": account.get("userId"),
                "message": f"Automated Alert: High risk transaction ({(txn.get('riskScore', 0) * 100):.1f}%) detected on account {account.get('accountNumber') or account.get('id')} for ₹{abs(txn.get('amount', 0)):,} at {txn.get('merchant')}. Please review immediately.",
                "severity": 'critical',
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
    except Exception as e:
        logger.error(f"Failed to process high risk transaction: {str(e)}", {"agent": "system"})

data_store.on('transaction:high_risk', on_transaction_high_risk)

# ─── WebSocket Endpoint ─────────────────────────────────────────────────────

@app.websocket("/")
async def root_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.websocket("/ws")
async def ws_alias(websocket: WebSocket):
    """Alias for / — accepts connections from any client using /ws path."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# ─── Pydantic Models ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class OAuthTokenRequest(BaseModel):
    code: str

class ChatRequest(BaseModel):
    message: str
    userId: str
    sessionId: Optional[str] = None

class BankerChatRequest(BaseModel):
    message: str
    userId: Optional[str] = None
    sessionId: Optional[str] = None

class UpdateUserRequest(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    occupation: Optional[str] = None
    riskProfile: Optional[str] = None

class FreezeUserRequest(BaseModel):
    reason: Optional[str] = None

class UpdateAccountRequest(BaseModel):
    status: Optional[str] = None
    balance: Optional[float] = None

class SimulateTransactionRequest(BaseModel):
    accountId: str
    amount: float
    type: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    riskScore: Optional[float] = None

class TransferRequest(BaseModel):
    fromAccountId: str
    toAccountId: str
    amount: float
    description: Optional[str] = None

class WorkingMemoryUpdateRequest(BaseModel):
    intent: Optional[str] = None
    entities: Optional[dict] = None
    cognitiveLoad: Optional[int] = None
    activeAgent: Optional[str] = None
    sessionStarted: Optional[str] = None
    lastQuery: Optional[str] = None

class LoanPipelineRequest(BaseModel):
    userId: Optional[str] = None
    applicationText: Optional[str] = None
    amount: Optional[float] = None
    purpose: Optional[str] = None

class ApprovalResolutionRequest(BaseModel):
    reviewerNote: Optional[str] = ""

class McpInvokeRequest(BaseModel):
    tool: str
    parameters: Optional[dict] = None

# ─── Auth API Routes ────────────────────────────────────────────────────────

@app.post("/api/auth/login")
async def post_login(req: LoginRequest):
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    try:
        banker = data_store.get_banker_by_username(req.username)
        if not banker:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        input_hash = hashlib.sha256(req.password.encode("utf-8")).hexdigest()
        if input_hash != banker.get("passwordHash"):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = sign_token({"bankerId": banker["id"], "username": banker["username"]})
        logger.info(f"Agent login successful: {banker['name']} ({banker['role']})")
        return {
            "success": True,
            "token": token,
            "banker": {
                "id": banker["id"],
                "username": banker["username"],
                "name": banker["name"],
                "role": banker["role"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during banker login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/auth/oauth-url")
async def get_oauth_url():
    return {"success": True, "url": "/oauth-mock.html"}

@app.post("/api/auth/oauth-token")
async def post_oauth_token(req: OAuthTokenRequest):
    if not req.code:
        raise HTTPException(status_code=400, detail="Authorization code is required")
    try:
        banker_username = 'agent1'
        if 'agent2' in req.code:
            banker_username = 'agent2'
        elif 'agent1' in req.code:
            banker_username = 'agent1'

        banker = data_store.get_banker_by_username(banker_username)
        if not banker:
            raise HTTPException(status_code=404, detail="Agent profile not found")

        token = sign_token({"bankerId": banker["id"], "username": banker["username"]})
        logger.info(f"Agent OAuth SSO login successful: {banker['name']} ({banker['role']})")
        return {
            "success": True,
            "token": token,
            "banker": {
                "id": banker["id"],
                "username": banker["username"],
                "name": banker["name"],
                "role": banker["role"]
            }
        }
    except Exception as e:
        logger.error(f"Error during OAuth token exchange: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ─── Chat API Routes ────────────────────────────────────────────────────────

@app.get("/api/chat/sessions")
async def get_chat_sessions(userId: str = Query(...)):
    try:
        sessions = data_store.get_sessions(userId)
        return {"success": True, "sessions": sessions}
    except Exception as e:
        logger.error(f"Failed to get sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sessions")

@app.get("/api/chat/sessions/{sessionId}")
async def get_chat_session_details(sessionId: str):
    try:
        session = data_store.get_session(sessionId)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "session": session}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session details")

@app.post("/api/chat/sessions")
async def post_chat_sessions(req: Dict[str, Any]):
    userId = req.get("userId")
    title = req.get("title")
    if not userId:
        raise HTTPException(status_code=400, detail="userId is required")
    try:
        session = data_store.create_session(id_val=None, user_id=userId, title=title)
        return {"success": True, "session": session}
    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@app.put("/api/chat/sessions/{sessionId}")
async def put_chat_sessions(sessionId: str, req: Dict[str, Any]):
    try:
        session = data_store.update_session(sessionId, req)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "session": session}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update session")

@app.delete("/api/chat/sessions/{sessionId}")
async def delete_chat_sessions(sessionId: str):
    try:
        deleted = data_store.delete_session(sessionId)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

@app.post("/api/chat")
async def post_chat(req: ChatRequest):
    if not req.message:
        raise HTTPException(status_code=400, detail="Message is required")
    if not req.userId:
        raise HTTPException(status_code=400, detail="userId is required")

    sid = req.sessionId or f"session-{int(time.time() * 1000)}"
    try:
        result = await route_message(sid, req.message, req.userId)
        return {
            "success": True,
            "sessionId": sid,
            "response": result,
            "apiConfigured": is_api_configured(),
        }
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", {"agent": "system"})
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

@app.post("/api/chat/banker")
async def post_chat_banker(req: BankerChatRequest, banker: dict = Depends(get_current_banker)):
    if not req.message:
        raise HTTPException(status_code=400, detail="Message is required")

    sid = req.sessionId or f"banker-session-{int(time.time() * 1000)}"
    try:
        result = await route_banker_message(sid, req.message, req.userId, banker)
        return {
            "success": True,
            "sessionId": sid,
            "response": result,
            "apiConfigured": is_api_configured(),
        }
    except Exception as e:
        logger.error(f"Banker Chat error: {str(e)}", {"agent": "system"})
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

@app.get("/api/agents")
async def get_agents():
    return {
        "agents": get_agent_info(),
        "apiConfigured": is_api_configured(),
    }

@app.get("/api/logs")
async def get_logs(count: int = 50):
    return {"logs": logger.get_recent_logs(count)}

# ─── Banking API Routes ─────────────────────────────────────────────────────

@app.get("/api/banking/users")
async def get_banking_users():
    users = [{
        "id": u["id"],
        "firstName": u["firstName"],
        "lastName": u["lastName"],
        "email": u["email"],
        "occupation": u["occupation"],
        "creditScore": u["creditScore"],
        "kycStatus": u["kycStatus"],
        "riskProfile": u["riskProfile"],
        "joinDate": u["joinDate"]
    } for u in data_store.get_users()]
    return {"users": users}

@app.get("/api/banking/users/{userId}")
async def get_banking_user_by_id(userId: str):
    user = data_store.get_user_by_id(userId)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": user}

@app.put("/api/banking/users/{userId}")
async def put_banking_user(userId: str, req: UpdateUserRequest, banker: dict = Depends(get_current_banker)):
    user = data_store.update_user(userId, req.dict(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "user": user}

@app.post("/api/banking/users/{userId}/freeze")
async def post_banking_user_freeze(userId: str, req: FreezeUserRequest, banker: dict = Depends(get_current_banker)):
    accounts = data_store.get_accounts_by_user_id(userId)
    if not accounts:
        raise HTTPException(status_code=404, detail="No accounts found for user")

    for acc in accounts:
        data_store.update_account(acc["id"], {"status": "frozen"})

    data_store._audit('banker_freeze_user', {
        "userId": userId,
        "reason": req.reason or "Fraud Analyst/Compliance action"
    })
    data_store.emit('transaction', {"userId": userId})
    return {"success": True, "message": f"Successfully froze {len(accounts)} account(s) for user {userId}."}

@app.get("/api/banking/accounts/{userId}")
async def get_banking_accounts(userId: str):
    accounts = data_store.get_accounts_by_user_id(userId)
    return {"accounts": accounts}

@app.put("/api/banking/accounts/{accountId}")
async def put_banking_account(accountId: str, req: UpdateAccountRequest, banker: dict = Depends(get_current_banker)):
    account = data_store.update_account(accountId, req.dict(exclude_unset=True))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    data_store.emit('transaction', {"userId": account["userId"]})
    return {"success": True, "account": account}

@app.delete("/api/banking/accounts/{accountId}")
async def delete_banking_account(accountId: str, banker: dict = Depends(require_role("Compliance Officer"))):
    account = data_store.get_account_by_id(accountId)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    data_store.accounts = [a for a in data_store.accounts if a["id"] != accountId]
    data_store.save()
    data_store.emit('transaction', {"userId": account["userId"]})
    return {"success": True}

@app.get("/api/banking/transactions/{accountId}")
async def get_banking_transactions(accountId: str, limit: int = 50):
    transactions = data_store.get_transactions_by_account_id(accountId, limit)
    return {"transactions": transactions}

@app.get("/api/banking/user-transactions/{userId}")
async def get_banking_user_transactions(userId: str, limit: int = 50):
    transactions = data_store.get_transactions_by_user_id(userId, limit)
    return {"transactions": transactions}

@app.post("/api/banking/transactions/simulate")
async def post_transactions_simulate(req: SimulateTransactionRequest):
    if not req.accountId or req.amount is None:
        raise HTTPException(status_code=400, detail="accountId and amount are required")
    try:
        txn = data_store.create_transaction(
            account_id=req.accountId,
            type_val=req.type or ("debit" if req.amount < 0 else "credit"),
            amount=req.amount,
            merchant=req.merchant or "Simulated Transaction",
            category=req.category or "Simulation",
            description=req.description or "Manually simulated transaction",
            risk_score=0.1
        )
        # Async background execution of fraud check
        asyncio.create_task(fraud_agent.evaluate_risk(txn))
        return {"success": True, "transaction": txn}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/banking/transactions/transfer")
async def post_transactions_transfer(req: TransferRequest):
    try:
        threshold = config.approval_thresholds["transfer"]
        if req.amount > threshold:
            from_account = data_store.get_account_by_id(req.fromAccountId)
            if not from_account:
                return {"success": False, "error": "Invalid origin account"}
            if from_account.get("balance", 0) < req.amount:
                return {"success": False, "error": "Insufficient funds"}

            approval = data_store.add_approval({
                "type": 'large_transfer',
                "agentName": 'System Simulator',
                "userId": from_account.get("userId", "unknown"),
                "details": {
                    "fromAccountId": req.fromAccountId,
                    "toAccountId": req.toAccountId,
                    "amount": req.amount
                },
                "reason": f"Simulator transfer of {req.amount} exceeds threshold of {threshold}",
            })
            return {
                "success": True,
                "requiresApproval": True,
                "message": f"Transfer requires human approval. ID: {approval['id']}"
            }

        result = data_store.transfer_funds(req.fromAccountId, req.toAccountId, req.amount, req.description)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/banking/dashboard/{userId}")
async def get_banking_dashboard(userId: str):
    stats = data_store.get_dashboard_stats(userId)
    user = data_store.get_user_by_id(userId)
    loans = data_store.get_loans_by_user_id(userId)
    portfolio = data_store.get_portfolio_by_user_id(userId)
    market = data_store.get_market_data()

    # Async seed semantic memory
    asyncio.create_task(memory_agent.seed_semantic_from_banking(userId, {
        "user": user,
        "accounts": data_store.get_accounts_by_user_id(userId),
        "stats": stats
    }))

    return {"stats": stats, "user": user, "loans": loans, "portfolio": portfolio, "market": market}

@app.get("/api/system-stats")
@app.get("/api/banking/system-stats")
async def get_system_stats():
    all_users = data_store.get_users()
    all_accounts = data_store.accounts or []
    all_loans = data_store.loans or []
    pending_approvals = data_store.get_pending_approvals()

    total_deposits = sum(a.get("balance", 0) for a in all_accounts if a.get("type") != 'credit')
    active_loans = sum(l.get("remainingBalance", 0) for l in all_loans if l.get("status") == 'active')
    
    all_txns = data_store.transactions or []
    fraud_alerts = len([t for t in all_txns if t.get("riskScore", 0) > 0.6])

    return {
        "totalUsers": len(all_users),
        "totalDeposits": round(total_deposits, 2),
        "activeLoans": round(active_loans, 2),
        "pendingApprovals": len(pending_approvals),
        "fraudAlerts": fraud_alerts,
        "systemHealth": 'OPTIMAL',
        "agentsActive": 6,
        "mcpEnabled": True
    }

@app.get("/api/banking/loans/all")
async def get_all_loans(banker: dict = Depends(get_current_banker)):
    return {"loans": data_store.loans or []}

@app.get("/api/banking/loans/{userId}")
async def get_user_loans(userId: str):
    loans = data_store.get_loans_by_user_id(userId)
    return {"loans": loans}

@app.get("/api/banking/market")
async def get_market():
    return data_store.get_market_data()

@app.get("/api/banking/memory/{userId}")
async def get_banking_memory(userId: str):
    memory = memory_agent.get_full_memory(userId)
    return {"memory": memory}

@app.post("/api/banking/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    import speech_recognition as sr
    import tempfile
    
    # Save to a temporary file
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await audio.read())
            
        r = sr.Recognizer()
        with sr.AudioFile(temp_path) as source:
            audio_data = r.record(source)
            
        text = r.recognize_google(audio_data)
        return {"text": text}
    except sr.UnknownValueError:
        return {"text": ""}
    except Exception as e:
        logger.error(f"STT Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

try:
    from vosk import Model, KaldiRecognizer
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model")
    if os.path.exists(model_path):
        vosk_model = Model(model_path)
    else:
        vosk_model = None
except ImportError:
    vosk_model = None

@app.websocket("/api/banking/transcribe/stream")
async def transcribe_stream(websocket: WebSocket):
    await websocket.accept()
    if vosk_model is None:
        await websocket.send_text(json.dumps({"error": "Vosk model not loaded"}))
        await websocket.close()
        return

    rec = KaldiRecognizer(vosk_model, 16000)
    try:
        while True:
            data = await websocket.receive_bytes()
            if len(data) == 0:
                break
            
            is_final = await asyncio.to_thread(rec.AcceptWaveform, data)
            
            if is_final:
                res = json.loads(rec.Result())
                if res.get("text"):
                    await websocket.send_text(json.dumps({"final": res["text"]}))
            else:
                res = json.loads(rec.PartialResult())
                if res.get("partial"):
                    await websocket.send_text(json.dumps({"partial": res["partial"]}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Vosk WS error: {e}")
    finally:
        res = json.loads(rec.FinalResult())
        if res.get("text"):
            try:
                await websocket.send_text(json.dumps({"final": res["text"]}))
            except:
                pass
        try:
            await websocket.close()
        except:
            pass

@app.post("/api/banking/memory/{userId}/working")
async def post_banking_memory_working(userId: str, req: WorkingMemoryUpdateRequest):
    updated = memory_agent.update_working_memory(userId, req.dict(exclude_unset=True))
    data_store.emit('memory:update', {"userId": userId, "type": "working", "data": updated})
    return {"success": True, "working": updated}

@app.get("/api/banking/audit")
async def get_audit_log(limit: int = 50, banker: dict = Depends(get_current_banker)):
    return {"auditLog": data_store.get_audit_log(limit)}

@app.get("/api/banking/complaints/all")
async def get_all_complaints(banker: dict = Depends(require_role("Compliance Officer"))):
    return {"complaints": data_store.get_all_complaints()}

# ─── Payment Hub APIs ────────────────────────────────────────────────────────

class PaymentInitiateRequest(BaseModel):
    userId: str
    fromAccountId: str
    beneficiaryName: str
    beneficiaryAccount: str
    amount: float
    currency: str = "INR"
    paymentType: str = "domestic"
    urgency: str = "standard"
    rail: Optional[str] = None
    reference: Optional[str] = None
    description: Optional[str] = None

@app.post("/api/payments/initiate")
async def initiate_payment(req: PaymentInitiateRequest, banker: dict = Depends(get_optional_banker)):
    try:
        session_id = f"payment-{req.userId}-{int(time.time())}"
        # Must create session so agent history read/write works correctly
        data_store.create_session(id_val=session_id, user_id=req.userId, title=f"Payment to {req.beneficiaryName}")
        user_msg = (
            f"Initiate {req.paymentType} payment of \u20b9{req.amount:,.2f} to {req.beneficiaryName} "
            f"({req.beneficiaryAccount}) via {req.rail or 'auto-select'} rail. "
            f"Reference: {req.reference or 'N/A'}. Priority: {req.urgency}."
        )
        result = await payment_orchestrator_agent.process(session_id, user_msg, {
            "userId": req.userId,
            "fromAccountId": req.fromAccountId,
            "beneficiaryName": req.beneficiaryName,
            "beneficiaryAccount": req.beneficiaryAccount,
            "amount": req.amount,
            "currency": req.currency,
            "paymentType": req.paymentType,
            "urgency": req.urgency,
            "rail": req.rail,
            "reference": req.reference,
            "description": req.description,
        })
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Payment initiate error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payments/queue")
async def get_payment_queue(status: Optional[str] = None, banker: dict = Depends(get_optional_banker)):
    payments = data_store.get_all_payments(status=status)
    return {"payments": payments}

@app.get("/api/payments/analytics")
async def get_payment_analytics(banker: dict = Depends(get_optional_banker)):
    return data_store.get_payment_analytics()

@app.get("/api/payments/{payment_id}")
async def get_payment(payment_id: str, banker: dict = Depends(get_optional_banker)):
    payment = data_store.get_payment_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"payment": payment}

@app.post("/api/payments/{payment_id}/cancel")
async def cancel_payment(payment_id: str, banker: dict = Depends(get_optional_banker)):
    payment = data_store.update_payment(payment_id, {"status": "cancelled"})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    banker_name = banker.get("username") if banker else "Customer"
    data_store._audit("payment_cancelled", {"id": payment_id, "banker": banker_name})
    return {"success": True, "payment": payment}

class PaymentChatRequest(BaseModel):
    message: str
    userId: Optional[str] = None
    sessionId: Optional[str] = None

@app.post("/api/chat/payment")
async def payment_chat(req: PaymentChatRequest, banker: dict = Depends(get_optional_banker)):
    try:
        session_id = req.sessionId or f"pay-chat-{req.userId}-{int(time.time())}"
        # Ensure session exists in data_store so agent history works
        existing = data_store.get_session(session_id)
        if not existing:
            data_store.create_session(id_val=session_id, user_id=req.userId or "", title="Payment AI Copilot")
        result = await payment_orchestrator_agent.process(session_id, req.message, {"userId": req.userId or ""})
        return {"success": True, "response": result.get("content", ""), "agent": result.get("displayName")}
    except Exception as e:
        logger.error(f"Payment chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payment-hub")
async def payment_hub_page():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'public', 'payment-hub.html')
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

# ─── SSE Loan Pipeline ──────────────────────────────────────────────────────

LOAN_PIPELINE_NODES = [
  { "id": 'extractor', "name": 'Data Extractor', "icon": '📄', "description": 'Extracts applicant name and loan amount from application text' },
  { "id": 'database_lookup', "name": 'Database Lookup', "icon": '🗄️', "description": 'Queries internal customer database for records' },
  { "id": 'compliance', "name": 'Compliance / KYC', "icon": '📋', "description": 'KYC/AML screening and regulatory compliance check' },
  { "id": 'analyst', "name": 'Credit Analyst', "icon": '📊', "description": 'Evaluates financial health and debt-to-income ratio' },
  { "id": 'risk', "name": 'Risk Assessment', "icon": '⚖️', "description": 'Calculates risk level and flags high-risk applications' },
  { "id": 'underwriter', "name": 'Underwriter', "icon": '🔍', "description": 'Deep-dive manual review for high-risk applications' },
  { "id": 'decision', "name": 'Decision Engine', "icon": '⚡', "description": 'Final loan approval or rejection decision' },
]

@app.post("/api/banking/loan-pipeline")
async def post_loan_pipeline(req: LoanPipelineRequest):
    user_id = req.userId
    user = data_store.get_user_by_id(user_id) if user_id else None
    
    app_text = req.applicationText
    if not app_text and req.amount:
        app_text = f"I am {user['firstName'] + ' ' + user['lastName'] if user else 'a customer'} and I would like to apply for a loan of ₹{req.amount} for {req.purpose or 'personal use'}."

    if not app_text:
        raise HTTPException(status_code=400, detail="applicationText or amount is required")

    async def event_generator():
        # Started event
        start_evt = {
            "status": "started",
            "nodes": LOAN_PIPELINE_NODES,
            "application": app_text
        }
        yield f"data: {json.dumps(start_evt)}\n\n"
        
        data_store.emit('agent:trace', {
            "agent": 'Loan Pipeline Orchestrator',
            "content": f"Starting multi-agent loan pipeline for: \"{app_text[:80]}...\"",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

        try:
            if user_id:
                memory_agent.start_workflow(user_id, 'LOAN_APPLICATION', len(LOAN_PIPELINE_NODES))

            state = {"application_text": app_text}
            
            # Step 1: Extractor
            yield f"data: {json.dumps({'node': 'extractor', 'status': 'processing'})}\n\n"
            data_store.emit('agent:trace', {
                "agent": 'Data Extractor',
                "content": f"Analyzing raw application input to extract entities: \"{app_text}\"",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
            await asyncio.sleep(0.6)
            
            extract_prompt = "You are a Data Extractor Agent for a bank. Extract the applicant's name and requested loan amount from the text. Format as JSON with fields: name, amount (number only), requested_loan_amount, status (COMPLETE if both found, INCOMPLETE if missing)."
            extract_resp = await chat_completion([
                {"role": "system", "content": extract_prompt},
                {"role": "user", "content": app_text}
            ], {"agentName": "extractor", "temperature": 0})
            
            extracted = {}
            data_status = 'INCOMPLETE'
            try:
                # regex to extract json block
                import re
                m = re.search(r"\{[\s\S]*\}", extract_resp.get("content", ""))
                json_str = m.group(0) if m else "{}"
                extracted = json.loads(json_str)
                data_status = 'COMPLETE' if extracted.get("status") == 'COMPLETE' else 'INCOMPLETE'
            except Exception:
                extracted = {"raw": extract_resp.get("content"), "name": f"{user['firstName']} {user['lastName']}" if user else None, "amount": req.amount}
                data_status = 'COMPLETE' if user else 'INCOMPLETE'
                
            state["extracted_data"] = extracted
            state["data_status"] = data_status
            
            yield f"data: {json.dumps({'node': 'extractor', 'status': 'complete', 'result': {'extracted': extracted, 'dataStatus': data_status}})}\n\n"
            data_store.emit('agent:trace', {
                "agent": 'Data Extractor',
                "content": f"Extracted: {json.dumps(extracted)}",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
            if user_id:
                memory_agent.advance_workflow_step(user_id)
            await asyncio.sleep(0.4)

            # Step 2: Database Lookup
            yield f"data: {json.dumps({'node': 'database_lookup', 'status': 'processing'})}\n\n"
            await asyncio.sleep(0.8)
            
            if user:
                user_accounts = data_store.get_accounts_by_user_id(user_id)
                loans = data_store.get_loans_by_user_id(user_id)
                total_debt = sum(l.get("remainingBalance", 0) for l in loans)
                db_records = {
                    "status": "FOUND",
                    "name": f"{user['firstName']} {user['lastName']}",
                    "credit_score": user.get("creditScore"),
                    "annual_income": user.get("annualIncome"),
                    "monthly_income": user.get("monthlyIncome"),
                    "dti_ratio": user.get("dtiRatio"),
                    "mortgage_status": "ACTIVE" if user.get("existingMortgage") else "NONE",
                    "total_debt": round(total_debt),
                    "missed_payments": 0,
                    "active_credit_lines": len(user_accounts),
                    "kyc_status": user.get("kycStatus"),
                }
            else:
                db_records = {"status": "NOT_FOUND", "note": "No internal records found"}
                
            state["database_records"] = db_records
            yield f"data: {json.dumps({'node': 'database_lookup', 'status': 'complete', 'result': db_records})}\n\n"
            data_store.emit('agent:trace', {
                "agent": 'Database Lookup',
                "content": f"DB Records: {json.dumps(db_records)}",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
            if user_id:
                memory_agent.advance_workflow_step(user_id)
            await asyncio.sleep(0.4)

            # Step 3: Compliance Check
            yield f"data: {json.dumps({'node': 'compliance', 'status': 'processing', 'reason': 'Performing AML/KYC screening...'})}\n\n"
            await asyncio.sleep(1.0)
            
            compliance_result = {"halted": False, "reason": "AML/KYC cleared. Identity verified against internal ledger."}
            if db_records.get("status") == 'NOT_FOUND':
                compliance_result = {"halted": True, "reason": "Application halted: No matching customer record found. Potential identity fraud."}
            elif db_records.get("kyc_status") != 'verified':
                compliance_result = {"halted": True, "reason": f"Application halted: Customer KYC status is {db_records.get('kyc_status', 'PENDING').upper()}. Verification required."}
            elif data_status == 'INCOMPLETE':
                compliance_result = {"halted": True, "reason": "Application halted: Incomplete identity data in request. Manual verification required."}
                
            state["compliance_check"] = compliance_result["reason"]
            yield f"data: {json.dumps({'node': 'compliance', 'status': 'complete', 'result': compliance_result})}\n\n"
            data_store.emit('agent:trace', {
                "agent": 'Compliance Agent',
                "content": compliance_result["reason"],
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            })
            if user_id:
                memory_agent.advance_workflow_step(user_id)
            await asyncio.sleep(0.4)

            if compliance_result["halted"]:
                state["decision"] = f"REJECTED: {compliance_result['reason']}"
                yield f"data: {json.dumps({'node': 'decision', 'status': 'complete', 'result': {'decision': state['decision'], 'approved': False}})}\n\n"
                approved = False
            else:
                # Step 4: Credit Analyst
                yield f"data: {json.dumps({'node': 'analyst', 'status': 'processing'})}\n\n"
                
                analyst_prompt = "You are a Credit Analyst. Evaluate financial health based on DB records and requested loan amount. Keep it brief (2 sentences max)."
                analyst_context = f"Requested: ₹{extracted.get('amount') or req.amount}\nDB Records: {json.dumps(db_records)}"
                
                data_store.emit('agent:trace', {
                    "agent": 'Credit Analyst',
                    "content": f"Evaluating financial health against request of ₹{extracted.get('amount') or req.amount}...",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                })
                await asyncio.sleep(0.9)
                
                analyst_resp = await chat_completion([
                    {"role": "system", "content": analyst_prompt},
                    {"role": "user", "content": analyst_context}
                ], {"agentName": "analyst", "temperature": 0.2})
                
                state["credit_analysis"] = analyst_resp.get("content")
                yield f"data: {json.dumps({'node': 'analyst', 'status': 'complete', 'result': {'analysis': analyst_resp.get('content')}})}\n\n"
                data_store.emit('agent:trace', {
                    "agent": 'Credit Analyst',
                    "content": analyst_resp.get("content"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                })
                if user_id:
                    memory_agent.advance_workflow_step(user_id)
                await asyncio.sleep(0.4)

                # Step 5: Risk Assessment
                yield f"data: {json.dumps({'node': 'risk', 'status': 'processing'})}\n\n"
                
                requested_amt = extracted.get('amount') or req.amount
                risk_prompt = "You are a Risk Assessment Agent. Output JSON with: 'risk_notes' (1-2 bullet points) and 'risk_level' (exactly 'HIGH' or 'LOW'). Rule: credit score < 650, or missed_payments > 0, or requested loan > (0.5 * annual_income) = HIGH."
                risk_context = f"Requested Loan Amount: ₹{requested_amt}\nDB Records: {json.dumps(db_records)}\nAnalyst Notes: {state['credit_analysis']}"
                
                data_store.emit('agent:trace', {
                    "agent": 'Risk Assessment',
                    "content": f"Calculating risk parameters. Request=₹{requested_amt}, Income=₹{db_records.get('annual_income')}, Credit={db_records.get('credit_score')}.",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                })
                await asyncio.sleep(0.9)
                
                risk_resp = await chat_completion([
                    {"role": "system", "content": risk_prompt},
                    {"role": "user", "content": risk_context}
                ], {"agentName": "risk", "temperature": 0, "responseFormat": {"type": "json_object"}})
                
                risk_level = 'HIGH'
                risk_notes = ''
                try:
                    import re
                    m = re.search(r"\{[\s\S]*\}", risk_resp.get("content", ""))
                    json_str = m.group(0) if m else "{}"
                    parsed = json.loads(json_str)
                    risk_level = 'LOW' if parsed.get("risk_level") == 'LOW' else 'HIGH'
                    risk_notes = parsed.get("risk_notes", risk_resp.get("content"))
                except Exception:
                    risk_notes = risk_resp.get("content")
                    
                state["risk_level"] = risk_level
                state["risk_assessment"] = risk_notes
                yield f"data: {json.dumps({'node': 'risk', 'status': 'complete', 'result': {'riskLevel': risk_level, 'notes': risk_notes}})}\n\n"
                data_store.emit('agent:trace', {
                    "agent": 'Risk Assessment',
                    "content": f"Risk Level: {risk_level}. Notes: {json.dumps(risk_notes)}",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                })
                if user_id:
                    memory_agent.advance_workflow_step(user_id)
                await asyncio.sleep(0.4)

                # Step 6: Underwriter
                if risk_level == 'HIGH':
                    yield f"data: {json.dumps({'node': 'underwriter', 'status': 'processing'})}\n\n"
                    
                    underwriter_prompt = "You are a Senior Underwriter. This application is HIGH RISK. Explain the severe risk factors and outline strict conditions for potential approval (collateral, higher rate, etc.)."
                    underwriter_context = f"Requested Loan: ₹{requested_amt}\nData: {json.dumps(db_records)}\nRisk Notes: {json.dumps(risk_notes)}"
                    
                    data_store.emit('agent:trace', {
                        "agent": 'Senior Underwriter',
                        "content": "FLAG: High Risk Detected. Initiating manual deep-dive review and calculating stricter collateral/rate conditions.",
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                    })
                    await asyncio.sleep(1.0)
                    
                    underw_resp = await chat_completion([
                        {"role": "system", "content": underwriter_prompt},
                        {"role": "user", "content": underwriter_context}
                    ], {"agentName": "underwriter", "temperature": 0.3})
                    
                    state["underwriter_review"] = underw_resp.get("content")
                    yield f"data: {json.dumps({'node': 'underwriter', 'status': 'complete', 'result': {'review': underw_resp.get('content')}})}\n\n"
                    data_store.emit('agent:trace', {
                        "agent": 'Underwriter',
                        "content": underw_resp.get("content")[:200],
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                    })
                    if user_id:
                        memory_agent.advance_workflow_step(user_id)
                    await asyncio.sleep(0.4)

                # Step 7: Decision Engine
                yield f"data: {json.dumps({'node': 'decision', 'status': 'processing'})}\n\n"
                await asyncio.sleep(1.0)
                
                decision_prompt = "You are the Final Decision Maker. Review all prior analyses. Output APPROVED or REJECTED on the first line, followed by a concise 2-3 sentence justification. Mention values in ₹ (Rupees)."
                decision_context = f"Application: {app_text}\n"
                if state.get("compliance_check"):
                    decision_context += f"Compliance Issue: {state.get('compliance_check')}\n"
                if state.get("database_records"):
                    decision_context += f"DB Records: {json.dumps(state.get('database_records'))}\n"
                if state.get("credit_analysis"):
                    decision_context += f"Credit Analysis: {state.get('credit_analysis')}\n"
                if state.get("risk_level"):
                    decision_context += f"Risk Level: {state.get('risk_level')}\nRisk Notes: {json.dumps(state.get('risk_assessment'))}\n"
                if state.get("underwriter_review"):
                    decision_context += f"Underwriter: {state.get('underwriter_review')}\n"
                    
                decision_resp = await chat_completion([
                    {"role": "system", "content": decision_prompt},
                    {"role": "user", "content": decision_context}
                ], {"agentName": "decision", "temperature": 0.1})
                
                decision_text = decision_resp.get("content", "")
                approved = decision_text.strip().upper().startswith('APPROVED')
                state["decision"] = decision_text
                
                yield f"data: {json.dumps({'node': 'decision', 'status': 'complete', 'result': {'decision': decision_text, 'approved': approved}})}\n\n"
                data_store.emit('agent:trace', {
                    "agent": 'Decision Engine',
                    "content": decision_text[:200],
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                })

            if approved and user_id:
                try:
                    loan_amount = float(extracted.get("amount") or req.amount or 0)
                except ValueError:
                    loan_amount = 0
                    
                if loan_amount > 0:
                    loan = data_store.create_loan({
                        "userId": user_id,
                        "amount": loan_amount,
                        "purpose": req.purpose or extracted.get("purpose") or "Personal Loan",
                        "type": "personal",
                        "interestRate": 5.5 if db_records.get("credit_score", 700) >= 750 else 9.5,
                        "monthlyPayment": round(loan_amount / 60, 2),
                        "termMonths": 60,
                        "status": "pending_approval"
                    })
                    data_store.add_approval({
                        "type": 'loan_application',
                        "agentName": 'Loan Pipeline',
                        "userId": user_id,
                        "details": {
                            "loanId": loan["id"],
                            "amount": loan_amount,
                            "decision": 'APPROVED',
                            "pipeline": 'multi-agent'
                        },
                        "reason": 'Loan pipeline approved — awaiting human counter-signature',
                    })
                    
            if user_id:
                await memory_agent.add_episodic_event(
                    user_id,
                    f"Loan pipeline {'APPROVED' if approved else 'REJECTED'} for ₹{extracted.get('amount') or req.amount}. {'Pending human approval.' if approved else 'Application declined.'}",
                    7 if approved else 6,
                    'positive' if approved else 'negative'
                )
                
            yield f"data: {json.dumps({'status': 'completed', 'approved': approved, 'fullState': state})}\n\n"

        except Exception as e:
            logger.error(f"Loan pipeline error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e), 'status': 'error'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ─── Approvals API Routes ───────────────────────────────────────────────────

@app.get("/api/approvals")
@app.get("/api/approvals/all")
async def get_approvals(banker: dict = Depends(get_current_banker)):
    return {"approvals": data_store.approval_queue}

@app.get("/api/approvals/pending")
async def get_pending_approvals(banker: dict = Depends(get_current_banker)):
    pending = data_store.get_pending_approvals()
    return {"approvals": pending, "count": len(pending)}

@app.post("/api/approvals/{id}/approve")
@app.post("/api/approvals/{id}/approved")
async def post_approve(id: str, req: ApprovalResolutionRequest, banker: dict = Depends(require_role("Compliance Officer"))):
    try:
        approval = data_store.resolve_approval(id, "approved", req.reviewerNote or "")
        result = await execute_approved_action(approval)
        return {"success": True, "approval": approval, "executionResult": result}
    except Exception as e:
        logger.error(f"Approval error: {str(e)}", {"agent": "approval"})
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/approvals/{id}/reject")
@app.post("/api/approvals/{id}/rejected")
async def post_reject(id: str, req: ApprovalResolutionRequest, banker: dict = Depends(require_role("Compliance Officer"))):
    try:
        approval = data_store.resolve_approval(id, "rejected", req.reviewerNote or "")
        result = handle_rejection(approval)
        return {"success": True, "approval": approval, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ─── MCP Tool API Registry ──────────────────────────────────────────────────

MCP_TOOLS = [
  {
    "name": 'check_balance',
    "description": 'Check the current balance of a given account.',
    "category": 'account',
    "icon": '💰',
    "parameters": {
      "type": 'object',
      "properties": {
        "accountId": { "type": 'string', "description": 'The ID of the account (e.g., ACC-001)', "required": True },
      },
      "required": ['accountId'],
    },
  },
  {
    "name": 'transfer_funds',
    "description": 'Transfer money between two accounts. Triggers human approval for large amounts.',
    "category": 'transaction',
    "icon": '💸',
    "parameters": {
      "type": 'object',
      "properties": {
        "fromAccountId": { "type": 'string', "description": 'Source account ID', "required": True },
        "toAccountId": { "type": 'string', "description": 'Destination account ID', "required": True },
        "amount": { "type": 'number', "description": 'Amount to transfer (positive number)', "required": True },
        "description": { "type": 'string', "description": 'Transfer description', "required": False },
      },
      "required": ['fromAccountId', 'toAccountId', 'amount'],
    },
  },
  {
    "name": 'apply_for_loan',
    "description": 'Submit a loan application for a given account. Requires human review.',
    "category": 'lending',
    "icon": '🏦',
    "parameters": {
      "type": 'object',
      "properties": {
        "userId": { "type": 'string', "description": 'The ID of the user applying', "required": True },
        "amount": { "type": 'number', "description": 'The requested loan amount', "required": True },
        "purpose": { "type": 'string', "description": 'Loan purpose (e.g., home, auto, personal)', "required": True },
        "termMonths": { "type": 'number', "description": 'Loan term in months', "required": False },
      },
      "required": ['userId', 'amount', 'purpose'],
    },
  },
  {
    "name": 'get_account_info',
    "description": 'Get detailed information about a specific account.',
    "category": 'account',
    "icon": '📋',
    "parameters": {
      "type": 'object',
      "properties": {
        "accountId": { "type": 'string', "description": 'The account ID', "required": True },
      },
      "required": ['accountId'],
    },
  },
  {
    "name": 'analyze_transactions',
    "description": 'Run a fraud and anomaly analysis on recent transactions for a user.',
    "category": 'fraud',
    "icon": '🛡️',
    "parameters": {
      "type": 'object',
      "properties": {
        "userId": { "type": 'string', "description": 'The user ID to analyze', "required": True },
        "limit": { "type": 'number', "description": 'Number of recent transactions to analyze (default: 30)', "required": False },
      },
      "required": ['userId'],
    },
  },
  {
    "name": 'freeze_account',
    "description": 'Request an account freeze due to suspected fraud. Requires human approval.',
    "category": 'fraud',
    "icon": '🔒',
    "parameters": {
      "type": 'object',
      "properties": {
        "accountId": { "type": 'string', "description": 'The ID of the account to freeze', "required": True },
        "reason": { "type": 'string', "description": 'Reason for the freeze', "required": True },
      },
      "required": ['accountId', 'reason'],
    },
  },
  {
    "name": 'get_loan_status',
    "description": 'Check the status of a loan application.',
    "category": 'lending',
    "icon": '📄',
    "parameters": {
      "type": 'object',
      "properties": {
        "loanId": { "type": 'string', "description": 'The loan application ID', "required": True },
      },
      "required": ['loanId'],
    },
  },
  {
    "name": 'get_user_profile',
    "description": 'Retrieve full profile information for a user including KYC and risk status.',
    "category": 'compliance',
    "icon": '👤',
    "parameters": {
      "type": 'object',
      "properties": {
        "userId": { "type": 'string', "description": 'The user ID', "required": True },
      },
      "required": ['userId'],
    },
  },
  {
    "name": 'get_market_data',
    "description": 'Fetch current market data including stock prices and market indices.',
    "category": 'investment',
    "icon": '📈',
    "parameters": {
      "type": 'object',
      "properties": {},
      "required": [],
    },
  },
]

def mcp_check_balance(parameters):
    account_id = parameters.get("accountId")
    account = data_store.get_account_by_id(account_id)
    if not account:
        return {"success": False, "error": f"Account {account_id} not found"}
    return {
        "success": True,
        "accountId": account_id,
        "accountName": account.get("name") or account.get("type"),
        "balance": account.get("balance"),
        "currency": 'USD',
        "status": account.get("status"),
    }

def mcp_transfer_funds(parameters):
    from_account_id = parameters.get("fromAccountId")
    to_account_id = parameters.get("toAccountId")
    amount = float(parameters.get("amount", 0))
    description = parameters.get("description", "MCP Transfer")
    
    from_account = data_store.get_account_by_id(from_account_id)
    if not from_account:
        return {"success": False, "error": f"Source account {from_account_id} not found"}
    if from_account.get("balance", 0) < amount:
        return {"success": False, "error": 'Insufficient funds'}

    TRANSFER_THRESHOLD = 10000
    if amount > TRANSFER_THRESHOLD:
        approval = data_store.add_approval({
            "type": 'large_transfer',
            "agentName": 'MCP Tool',
            "userId": from_account.get("userId"),
            "details": {
                "fromAccountId": from_account_id,
                "toAccountId": to_account_id,
                "amount": amount,
                "description": description
            },
            "reason": f"MCP-initiated transfer of ${amount} exceeds threshold of ${TRANSFER_THRESHOLD}",
        })
        return {
            "success": True,
            "requiresApproval": True,
            "approvalId": approval["id"],
            "message": f"Transfer requires human approval. Approval ID: {approval['id']}"
        }

    result = data_store.transfer_funds(from_account_id, to_account_id, amount, description)
    return {
        "success": True,
        "debitTxnId": result.get("debit", {}).get("id"),
        "creditTxnId": result.get("credit", {}).get("id"),
        "amount": amount
    }

def mcp_apply_for_loan(parameters):
    user_id = parameters.get("userId")
    user = data_store.get_user_by_id(user_id)
    if not user:
        return {"success": False, "error": f"User {user_id} not found"}
        
    amount = float(parameters.get("amount", 0))
    purpose = parameters.get("purpose")
    term_months = int(parameters.get("termMonths", 60))
    
    credit_score = user.get("creditScore", 700)
    interest_rate = 5.5 if credit_score >= 750 else 7.5 if credit_score >= 700 else 10.5 if credit_score >= 650 else 15.0
    r = interest_rate / 100 / 12
    emi = amount * r * math.pow(1 + r, term_months) / (math.pow(1 + r, term_months) - 1)
    emi_rounded = round(emi, 2)

    approval = data_store.add_approval({
        "type": 'loan_application',
        "agentName": 'MCP Tool',
        "userId": user_id,
        "details": {
            "amount": amount,
            "purpose": purpose,
            "termMonths": term_months,
            "interestRate": interest_rate,
            "emi": emi_rounded
        },
        "reason": f"Loan application for ${amount} submitted via MCP",
    })

    loan = data_store.create_loan(
        user_id=user_id,
        amount=amount,
        purpose=purpose,
        type_val='personal',
        interest_rate=interest_rate,
        monthly_payment=emi_rounded,
        term_months=term_months,
        status='pending_approval'
    )
    
    return {
        "success": True,
        "loanId": loan["id"],
        "approvalId": approval["id"],
        "interestRate": interest_rate,
        "monthlyPayment": emi_rounded,
        "termMonths": term_months
    }

def mcp_get_account_info(parameters):
    account_id = parameters.get("accountId")
    account = data_store.get_account_by_id(account_id)
    if not account:
        return {"success": False, "error": f"Account {account_id} not found"}
    recent_txns = data_store.get_transactions_by_account_id(account_id, 5)
    return {"success": True, "account": account, "recentTransactions": recent_txns}

def mcp_analyze_transactions(parameters):
    user_id = parameters.get("userId")
    limit = int(parameters.get("limit", 30))
    txns = data_store.get_transactions_by_user_id(user_id, limit)
    if not txns:
        return {"success": False, "error": 'No transactions found'}
        
    amounts = [abs(t.get("amount", 0)) for t in txns]
    avg = sum(amounts) / len(amounts) if amounts else 0
    anomalies = [
        t for t in txns
        if abs(t.get("amount", 0)) > avg * 3 or t.get("riskScore", 0) > 0.6
    ]
    risk_level = 'HIGH' if len(anomalies) > 5 else 'MEDIUM' if len(anomalies) > 2 else 'LOW'
    
    return {
        "success": True,
        "riskLevel": risk_level,
        "transactionsAnalyzed": len(txns),
        "anomaliesDetected": len(anomalies),
        "averageTransaction": round(avg, 2),
        "flaggedTransactions": [
            {
                "id": t["id"],
                "merchant": t["merchant"],
                "amount": t["amount"],
                "riskScore": t.get("riskScore", 0)
            } for t in anomalies
        ]
    }

def mcp_freeze_account(parameters):
    account_id = parameters.get("accountId")
    reason = parameters.get("reason")
    
    account = data_store.get_account_by_id(account_id)
    if not account:
        return {"success": False, "error": f"Account {account_id} not found"}
        
    approval = data_store.add_approval({
        "type": 'account_freeze',
        "agentName": 'MCP Tool',
        "userId": account.get("userId"),
        "details": {"accountId": account_id, "reason": reason},
        "reason": 'Account freeze requires human authorization',
    })
    
    return {
        "success": True,
        "requiresApproval": True,
        "approvalId": approval["id"],
        "message": f"Freeze request submitted. Approval ID: {approval['id']}"
    }

def mcp_get_loan_status(parameters):
    loan_id = parameters.get("loanId")
    loan = data_store.get_loan_by_id(loan_id)
    if not loan:
        return {"success": False, "error": f"Loan {loan_id} not found"}
    return {"success": True, "loan": loan}

def mcp_get_user_profile(parameters):
    user_id = parameters.get("userId")
    user = data_store.get_user_by_id(user_id)
    if not user:
        return {"success": False, "error": f"User {user_id} not found"}
        
    safe_user = user.copy()
    safe_user.pop("password", None)
    safe_user.pop("passwordHash", None)
    accounts = data_store.get_accounts_by_user_id(user_id)
    
    return {"success": True, "user": safe_user, "accountCount": len(accounts)}

def mcp_get_market_data(parameters):
    return {"success": True, "data": data_store.get_market_data()}

mcp_tool_handlers = {
    "check_balance": mcp_check_balance,
    "transfer_funds": mcp_transfer_funds,
    "apply_for_loan": mcp_apply_for_loan,
    "get_account_info": mcp_get_account_info,
    "analyze_transactions": mcp_analyze_transactions,
    "freeze_account": mcp_freeze_account,
    "get_loan_status": mcp_get_loan_status,
    "get_user_profile": mcp_get_user_profile,
    "get_market_data": mcp_get_market_data,
}

@app.get("/api/mcp/tools")
async def get_mcp_tools(banker: dict = Depends(get_optional_banker)):
    return {
        "version": "1.0.0",
        "serverName": "AgenticBank-MCP-Server",
        "tools": MCP_TOOLS
    }

@app.post("/api/mcp/invoke")
async def post_mcp_invoke(req: McpInvokeRequest, banker: dict = Depends(get_optional_banker)):
    if not req.tool:
        raise HTTPException(status_code=400, detail="tool name is required")
        
    handler = mcp_tool_handlers.get(req.tool)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool}' not found")
        
    # Parameter check
    tool_def = next((t for t in MCP_TOOLS if t["name"] == req.tool), None)
    if tool_def and tool_def.get("parameters", {}).get("required"):
        params = req.parameters or {}
        for req_param in tool_def["parameters"]["required"]:
            if params.get(req_param) is None or params.get(req_param) == "":
                raise HTTPException(status_code=400, detail=f"Missing required parameter: {req_param}")

    try:
        start_time = time.time()
        result = handler(req.parameters or {})
        duration = int((time.time() - start_time) * 1000)

        logger.info(f"MCP tool invoked: {req.tool}", {"agent": "mcp", "parameters": req.parameters})

        data_store.emit('agent:trace', {
            "agent": "MCP Tool Registry",
            "content": f"Tool invoked: {req.tool}({json.dumps(req.parameters)}) → {'SUCCESS' if result.get('success', True) else 'ERROR'}",
            "toolCalls": [{"name": req.tool, "args": json.dumps(req.parameters)}],
            "toolResult": {"name": req.tool, "result": json.dumps(result)[:200]},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

        return {"success": True, "tool": req.tool, "result": result, "executionMs": duration}
    except Exception as error:
        logger.error(f"MCP tool error: {req.tool} — {str(error)}")
        raise HTTPException(status_code=500, detail=str(error))

# ─── System Health API ──────────────────────────────────────────────────────

@app.get("/api/health")
async def get_health():
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "version": "2.2.0",
        "features": {
            "multiAgentOrchestration": True,
            "loanPipeline": True,
            "mcpToolRegistry": True,
            "memorySystem": True,
            "webSocketLive": True,
            "humanInTheLoop": True,
            "reactTrace": True,
        },
        "apiConfigured": is_api_configured()
    }

# ─── SPA/Static Files Routing fallback ──────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app.mount("/css", StaticFiles(directory=os.path.join(PUBLIC_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(PUBLIC_DIR, "js")), name="js")

@app.get("/")
async def get_root_index():
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

@app.get("/{filename}")
async def get_top_level_static_file(filename: str):
    path = os.path.join(PUBLIC_DIR, filename)
    if os.path.exists(path) and os.path.isfile(path):
        return FileResponse(path)
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

# ─── Startup and Port Initialization ────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=config.server["port"], reload=True)
