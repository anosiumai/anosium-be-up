# core/limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_real_ip(request):
    """Use X-Forwarded-For when behind a proxy, fall back to direct IP"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(
    key_func=get_real_ip,
    default_limits=["60/minute"]
)