"""
Pydantic schemas for User registration and user data representations.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    """
    Schema for user registration requests.
    Validates required name, email, and password.
    """
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full name of the user",
        examples=["Jane Doe"],
    )
    email: EmailStr = Field(
        ...,
        description="Unique email address for user login",
        examples=["jane.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Plaintext password (minimum 6 characters)",
        examples=["SecurePass123!"],
    )


class UserResponse(BaseModel):
    """
    Safe public schema for user profile representations.
    Excludes sensitive fields like password_hash.
    """
    id: int
    name: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
