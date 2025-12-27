"""
Tests for JWT token handling.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from jose import jwt


class TestJWTHandler:
    """Tests for JWT token creation and verification."""

    @pytest.fixture
    def jwt_settings(self):
        """Create JWT settings for tests."""
        return {
            "secret_key": "test-secret-key-for-testing",
            "algorithm": "HS256",
            "expire_minutes": 60,
        }

    def test_create_access_token(self, jwt_settings):
        """Test creating a JWT access token."""
        data = {"sub": "1"}
        expire = datetime.utcnow() + timedelta(minutes=jwt_settings["expire_minutes"])
        to_encode = data.copy()
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_custom_expiry(self, jwt_settings):
        """Test creating a token with custom expiration."""
        data = {"sub": "1"}
        custom_expire = datetime.utcnow() + timedelta(hours=2)
        to_encode = data.copy()
        to_encode.update({"exp": custom_expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        # Verify the token is valid
        payload = jwt.decode(
            token,
            jwt_settings["secret_key"],
            algorithms=[jwt_settings["algorithm"]]
        )
        assert payload is not None
        assert payload["sub"] == "1"

    def test_verify_token_valid(self, jwt_settings):
        """Test verifying a valid token."""
        data = {"sub": "123", "email": "test@example.com"}
        expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode = data.copy()
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        payload = jwt.decode(
            token,
            jwt_settings["secret_key"],
            algorithms=[jwt_settings["algorithm"]]
        )

        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload

    def test_verify_token_invalid(self, jwt_settings):
        """Test verifying an invalid token."""
        from jose import JWTError

        with pytest.raises(JWTError):
            jwt.decode(
                "invalid-token",
                jwt_settings["secret_key"],
                algorithms=[jwt_settings["algorithm"]]
            )

    def test_verify_token_tampered(self, jwt_settings):
        """Test verifying a tampered token."""
        from jose import JWTError

        data = {"sub": "1"}
        expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode = data.copy()
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        # Tamper with the token
        tampered_token = token[:-5] + "xxxxx"

        with pytest.raises(JWTError):
            jwt.decode(
                tampered_token,
                jwt_settings["secret_key"],
                algorithms=[jwt_settings["algorithm"]]
            )

    def test_verify_token_wrong_secret(self, jwt_settings):
        """Test verifying a token with wrong secret."""
        from jose import JWTError

        data = {"sub": "1"}
        expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode = data.copy()
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        # Try to decode with different secret
        with pytest.raises(JWTError):
            jwt.decode(
                token,
                "different-secret-key",
                algorithms=[jwt_settings["algorithm"]]
            )

    def test_token_includes_additional_data(self, jwt_settings):
        """Test that additional data is included in token."""
        data = {
            "sub": "1",
            "name": "Test User",
            "role": "admin",
        }
        expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode = data.copy()
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        payload = jwt.decode(
            token,
            jwt_settings["secret_key"],
            algorithms=[jwt_settings["algorithm"]]
        )

        assert payload["sub"] == "1"
        assert payload["name"] == "Test User"
        assert payload["role"] == "admin"

    def test_token_expiration(self, jwt_settings):
        """Test that expired tokens are rejected."""
        from jose import JWTError

        data = {"sub": "1"}
        # Set expiration in the past
        expire = datetime.utcnow() - timedelta(minutes=10)
        to_encode = data.copy()
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_settings["secret_key"],
            algorithm=jwt_settings["algorithm"]
        )

        with pytest.raises(JWTError):
            jwt.decode(
                token,
                jwt_settings["secret_key"],
                algorithms=[jwt_settings["algorithm"]]
            )
