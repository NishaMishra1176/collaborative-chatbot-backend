"""
Pydantic schemas for authentication and token responses.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """
    Schema for user login credentials.
    """
    email: EmailStr = Field(
        ...,
        description="Registered account email",
        examples=["jane.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
        examples=["SecurePass123!"],
    )


class TokenResponse(BaseModel):
    """
    Schema for successful authentication response containing JWT access token.
    Never exposes internal signing secrets or password hashes.
    """
    access_token: str = Field(
        ...,
        description="Signed JWT access token",
    )
    token_type: str = Field(
        default="bearer",
        description="Type of the authentication token",
    )
    expires_in: int = Field(
        ...,
        description="Token expiration duration in seconds",
    )
