"""Pydantic schemas for auth HTTP endpoints (input validation)."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Audience = Literal["school", "company", "personal"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    audience: Audience | None = None

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()
