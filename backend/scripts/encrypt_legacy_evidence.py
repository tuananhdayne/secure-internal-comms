"""Mã hóa các tệp bằng chứng CŨ (lưu dạng rõ trong uploads/evidences/) sang định dạng .enc.

    python scripts/encrypt_legacy_evidence.py           # chạy thử: chỉ liệt kê
    python scripts/encrypt_legacy_evidence.py --apply   # thực hiện

Với mỗi bản ghi case_evidences có file_url "/uploads/evidences/...":
  1. đọc tệp rõ, kiểm tra SHA-256 khớp CSDL;
  2. ghi <uuid>.enc (envelope AES-256-GCM + ECIES, xem app/services/evidence.py);
  3. giải mã thử lại để chắc chắn, rồi cập nhật file_url = "enc:<uuid>.enc";
  4. sau khi commit CSDL mới ghi đè + xóa tệp rõ.
Tệp rõ không còn bản ghi nào trỏ tới (tệp mồ côi) cũng được ghi đè + xóa khi --apply.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.anonymous import CaseEvidence  # noqa: E402
from app.services.evidence import (  # noqa: E402
    ENCRYPTED_PREFIX, LEGACY_PREFIX, decrypt_blob, encrypt_blob, evidence_path, is_placeholder,
)


def _shred(path: Path) -> None:
    try:
        path.write_bytes(b"\0" * path.stat().st_size)
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Thực hiện (mặc định chỉ chạy thử)")
    args = ap.parse_args()
    ev_dir = settings.uploads_path / "evidences"
    done = skipped = 0
    to_shred: list[Path] = []

    with SessionLocal() as db:
        rows = db.query(CaseEvidence).filter(CaseEvidence.file_url.like(f"{LEGACY_PREFIX}%")).all()
        referenced = set()
        for ev in rows:
            src = evidence_path(ev.file_url)
            if src is None or not src.is_file():
                print(f"  bỏ qua id={ev.id}: không thấy tệp")
                skipped += 1
                continue
            referenced.add(src.resolve())
            data = src.read_bytes()
            if hashlib.sha256(data).hexdigest() != ev.file_sha256_hash:
                print(f"  bỏ qua id={ev.id}: SHA-256 không khớp CSDL (giữ nguyên để kiểm tra)")
                skipped += 1
                continue
            name = src.name[33:] if len(src.name) > 33 and src.name[32] == "_" else src.name
            print(f"  id={ev.id}: {len(data)} byte -> .enc")
            if not args.apply:
                continue
            dest_name = f"{uuid.uuid4().hex}.enc"
            dest = ev_dir / dest_name
            dest.write_bytes(encrypt_blob(data, name))
            if decrypt_blob(dest.read_bytes())[0] != data:
                dest.unlink(missing_ok=True)
                raise SystemExit(f"Giải mã thử thất bại cho id={ev.id} — dừng, không thay đổi gì thêm.")
            ev.file_url = f"{ENCRYPTED_PREFIX}{dest_name}"
            if is_placeholder(f"{LEGACY_PREFIX}{src.name}", ev.mime_type):
                ev.mime_type = "application/x-atbm-placeholder"
            to_shred.append(src)
            done += 1
        if args.apply:
            db.commit()

    orphans = [p for p in ev_dir.iterdir() if p.is_file() and p.suffix != ".enc" and p.resolve() not in referenced]
    for p in orphans:
        print(f"  tệp rõ mồ côi: {p.name}")
    if args.apply:
        for p in to_shred + orphans:
            _shred(p)
    print(f"{'Đã mã hóa' if args.apply else 'Sẽ mã hóa'}: {done if args.apply else len(rows) - skipped}, "
          f"bỏ qua: {skipped}, tệp mồ côi: {len(orphans)}{' (đã xóa)' if args.apply else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
