from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    employee_code: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    employee_code: str
    full_name: str
    department: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
