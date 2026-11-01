from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class CaseCreateRequest(BaseModel):
    category: str
    encrypted_title: str
    encrypted_description: str
    payload_ephemeral_pub: str
    payload_iv: str
    payload_auth_tag: str
    case_token: str
    case_public_key: str
    unblinded_signature: str


class CaseEvidenceResponse(BaseModel):
    id: int
    file_url: str
    file_sha256_hash: str
    mime_type: str

    model_config = ConfigDict(from_attributes=True)


class MessageCreateRequest(BaseModel):
    ephemeral_pub_key: str
    nonce_iv: str
    encrypted_message: str
    auth_tag: str
    digital_signature: str


class CaseMessageResponse(BaseModel):
    id: int
    sender_type: str
    ephemeral_pub_key: str
    nonce_iv: str
    encrypted_message: str
    auth_tag: str
    digital_signature: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseStatusResponse(BaseModel):
    case_token: str
    category: str
    status: str
    created_bucket: datetime
    evidences: List[CaseEvidenceResponse] = []
    messages: List[CaseMessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CaseSubmitResponse(BaseModel):
    case_token: str
    status: str
    message: str
    created_bucket: datetime
