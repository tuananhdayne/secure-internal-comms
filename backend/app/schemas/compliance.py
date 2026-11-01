from typing import Dict
from pydantic import BaseModel


class OfficerKeysResponse(BaseModel):
    blind_sign_pub: Dict[str, str]  # {"e": "...", "n": "..."}
    chat_pub_hex: str               # 130 ký tự hex khóa ECC P-256


class BlindSignRequest(BaseModel):
    blinded_hash: str               # Giá trị m* hex hoặc decimal string


class BlindSignResponse(BaseModel):
    blind_signature: str            # Giá trị s* hex
    remaining_quota: int            # Số lượt ký mù còn lại trong tuần
