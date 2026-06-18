from slowapi import Limiter
from slowapi.util import get_remote_address
from core.config import settings

# ponytail: one object, main.py does the rest
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    enabled=settings.RATE_LIMIT_ENABLED,
)