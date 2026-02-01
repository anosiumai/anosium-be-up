from fastapi import Request, HTTPException

async def tenant_middleware(request: Request, call_next):
    if request.url.path.startswith("/auth"):
        return await call_next(request)

    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(401, "Unauthorized")

    clinic_id = user.get("clinic_id")

    if user["role"] != "super_admin" and not clinic_id:
        raise HTTPException(403, "Clinic context missing")

    request.state.clinic_id = clinic_id
    return await call_next(request)
