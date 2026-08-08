from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from accessforge.core.config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str | None
    role: str


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        )
    try:
        header = jwt.get_unverified_header(credentials.credentials)
        key_id = header.get("kid")
        if not isinstance(key_id, str):
            raise InvalidTokenError("Missing key ID")
        public_key = settings.public_key_map.get(key_id)
        if public_key is None:
            raise InvalidTokenError("Unknown key ID")
        payload = jwt.decode(
            credentials.credentials,
            public_key,
            algorithms=["ES256"],
            audience=settings.backend_token_audience,
            issuer=settings.backend_token_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud", "jti"]},
        )
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token."
        ) from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token subject."
        )
    email = payload.get("email")
    return Principal(
        subject=subject,
        email=email if isinstance(email, str) else None,
        role=str(payload.get("role", "member")),
    )
