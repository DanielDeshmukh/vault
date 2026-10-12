from datetime import timedelta

from jose import JWTError, jwt

from app.config import settings
from app.auth.jwt import (
    get_password_hash,
    verify_password,
    create_access_token,
)


def decode_access_token(token: str) -> dict | None:
    """Decode a JWT, returning None on any invalid/expired token."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing produces a hash."""
        password = "testpassword123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_verify_correct_password(self):
        """Test correct password verification."""
        password = "testpassword123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Test incorrect password verification."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that hashing the same password produces different hashes (salt)."""
        password = "testpassword123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Different hashes due to random salt
        assert hash1 != hash2

        # But both verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_empty_password(self):
        """Test hashing empty password."""
        password = ""
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_special_characters_in_password(self):
        """Test password with special characters."""
        password = "P@$$w0rd!#%^&*()"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_long_password(self):
        """Test long password."""
        password = "a" * 1000
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True


class TestJWTToken:
    """Test JWT token creation and validation."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "user@example.com", "user_id": 1}
        token = create_access_token(data)

        assert token is not None
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test JWT token decoding."""
        data = {"sub": "user@example.com", "user_id": 1}
        token = create_access_token(data)

        decoded = decode_access_token(token)

        assert decoded is not None
        assert decoded["sub"] == "user@example.com"
        assert decoded["user_id"] == 1

    def test_token_expiration_claim(self):
        """Test token has expiration claim."""
        data = {"sub": "user@example.com"}
        token = create_access_token(data)

        decoded = decode_access_token(token)

        assert decoded is not None
        assert "exp" in decoded

    def test_custom_expiration(self):
        """Test custom token expiration."""
        import time

        data = {"sub": "user@example.com"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires_delta)

        decoded = decode_access_token(token)

        # exp is an absolute unix timestamp: ~30 minutes from now
        seconds_until_expiry = decoded["exp"] - time.time()

        # Allow 10 seconds tolerance
        assert 29 * 60 <= seconds_until_expiry <= 31 * 60

    def test_invalid_token(self):
        """Test decoding invalid token."""
        invalid_token = "invalid.token.here"

        decoded = decode_access_token(token=invalid_token)

        assert decoded is None

    def test_token_tampered_signature(self):
        """A token signed with the wrong key must not decode."""
        data = {"sub": "user@example.com"}
        token = create_access_token(data)
        tampered = token[:-4] + "AAAA" if not token.endswith("AAAA") else token[:-4] + "BBBB"

        assert decode_access_token(token=tampered) is None

    def test_token_with_extra_claims(self):
        """Test token with additional claims."""
        data = {
            "sub": "user@example.com",
            "user_id": 1,
            "department": "engineering",
            "is_admin": False,
        }
        token = create_access_token(data)

        decoded = decode_access_token(token)

        assert decoded["department"] == "engineering"
        assert decoded["is_admin"] is False


class TestTokenExpiration:
    """Test token expiration behavior."""

    def test_default_expiration_configured(self):
        """Default expiration must be a positive number of minutes."""
        assert settings.JWT_EXPIRATION_MINUTES > 0

    def test_expired_token_rejected(self):
        """An expired token must be rejected by the decoder."""
        data = {"sub": "user@example.com"}
        token = create_access_token(data, expires_delta=timedelta(minutes=-5))

        assert decode_access_token(token) is None
