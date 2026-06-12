from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
import pyotp

from app.config import settings
from app.domain.services import MfaService, PasswordHasher, TokenPair, TokenService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)


class JwtTokenService(TokenService):
    def create_access_token(self, user_id: UUID, email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {"sub": str(user_id), "email": email, "exp": expire, "type": "access"}
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    def create_refresh_token(self, user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    def decode_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        except JWTError:
            return None

    def create_token_pair(self, user_id: UUID, email: str) -> TokenPair:
        return TokenPair(
            access_token=self.create_access_token(user_id, email),
            refresh_token=self.create_refresh_token(user_id),
        )


class TotpMfaService(MfaService):
    def generate_secret(self) -> str:
        return pyotp.random_base32()

    def get_provisioning_uri(self, secret: str, email: str) -> str:
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=settings.mfa_issuer)

    def verify_code(self, secret: str, code: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
