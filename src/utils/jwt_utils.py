import hmac
import hashlib
import base64
import json
import time

JWT_SECRET = "agenticbank-super-secret-key-12345!"

def base64_url_encode(s: bytes) -> str:
    return base64.urlsafe_b64encode(s).decode("utf-8").replace("=", "")

def base64_url_decode(s: str) -> bytes:
    padding = len(s) % 4
    if padding:
        s += "=" * (4 - padding)
    return base64.urlsafe_b64decode(s.encode("utf-8"))

def sign_token(payload: dict, expires_in_ms: int = 86400000) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    exp = int(time.time() * 1000) + expires_in_ms
    payload_with_exp = {**payload, "exp": exp}
    
    encoded_header = base64_url_encode(json.dumps(header, separators=(',', ':')).encode("utf-8"))
    encoded_payload = base64_url_encode(json.dumps(payload_with_exp, separators=(',', ':')).encode("utf-8"))
    
    signature_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    
    sig = hmac.new(JWT_SECRET.encode("utf-8"), signature_input, hashlib.sha256).digest()
    encoded_signature = base64_url_encode(sig)
    
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

def verify_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_str, payload_str, signature = parts
        signature_input = f"{header_str}.{payload_str}".encode("utf-8")
        
        sig = hmac.new(JWT_SECRET.encode("utf-8"), signature_input, hashlib.sha256).digest()
        expected_signature = base64_url_encode(sig)
        
        if not hmac.compare_digest(signature, expected_signature):
            return None
            
        payload = json.loads(base64_url_decode(payload_str).decode("utf-8"))
        
        exp = payload.get("exp")
        if exp and int(time.time() * 1000) > exp:
            return None
            
        return payload
    except Exception:
        return None
