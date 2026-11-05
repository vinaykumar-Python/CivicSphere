from pydantic import BaseModel, EmailStr, Field


class EmailAddressRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(EmailAddressRequest):
    code: str = Field(pattern=r"^\d{6}$")
