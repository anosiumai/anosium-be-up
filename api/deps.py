from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError
from app.core.security import SECRET_KEY, ALGORITHM

def get_current_user(request: Request):
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(401, "Missing token")

    token = auth.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid token")

    request.state.user = payload
    return payload
