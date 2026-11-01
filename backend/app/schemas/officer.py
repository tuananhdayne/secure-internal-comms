from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.anonymous import CaseEvidenceResponse, CaseMessageResponse


class CaseStatusUpdate(BaseModel):
    status: str  # PENDING, INVESTIGATING, RESOLVED, REJECTED


class OfficerReplyRequest(BaseModel):
    ephemeral_pub_key: str
    nonce_iv: str
    encrypted_message: str
    auth_tag: str
    digital_signature: str


class OfficerCaseSummary(BaseModel):
    id: int
    case_token: str
    category: str
    status: str
    created_bucket: datetime
    evidences_count: int

    model_config = ConfigDict(from_attributes=True)


class DecryptedCaseResponse(BaseModel):
    id: int
    case_token: str
    category: str
    status: str
    decrypted_title: str
    decrypted_description: str
    created_bucket: datetime
    evidences: List[CaseEvidenceResponse] = []
    messages: List[CaseMessageResponse] = []
