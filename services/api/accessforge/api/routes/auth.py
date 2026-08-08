from fastapi import APIRouter, Depends

from accessforge.core.security import Principal, get_current_principal

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/whoami")
async def whoami(principal: Principal = Depends(get_current_principal)) -> dict[str, str | None]:
    return {"id": principal.subject, "email": principal.email, "role": principal.role}
