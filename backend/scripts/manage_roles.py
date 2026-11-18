"""Quản lý tài khoản ĐẶC QUYỀN (Cán bộ Thanh tra, Quản trị viên) — chỉ chạy trên máy chủ.

Theo app/core/permissions.py, các vai trò này KHÔNG được cấp / khóa qua cổng web để bảo đảm
tách bạch nhiệm vụ (Quản trị không thể tự tạo tài khoản Thanh tra để đọc tố giác).

    python scripts/manage_roles.py list
    python scripts/manage_roles.py create TT002 "Nguyễn Văn B" "Ban Thanh tra" COMPLIANCE_OFFICER
    python scripts/manage_roles.py set-role NV005 COMPLIANCE_OFFICER
    python scripts/manage_roles.py set-role TT002 EMPLOYEE          # thu hồi quyền Thanh tra
    python scripts/manage_roles.py lock TT002 | unlock TT002
    python scripts/manage_roles.py reset-password TT002

Mật khẩu luôn được hỏi qua getpass (không nhận từ tham số dòng lệnh để không lưu vào history).
Mỗi thao tác được ghi vào log ứng dụng (logger "atbm.roles").
"""
from __future__ import annotations

import argparse
import getpass
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.constants import Role  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models.identified import User  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("atbm.roles")

ROLE_CHOICES = sorted(Role.ALL)
MIN_PASSWORD = 10


def _ask_password() -> str:
    while True:
        pw = getpass.getpass("Mật khẩu mới: ")
        if len(pw) < MIN_PASSWORD:
            print(f"Mật khẩu tối thiểu {MIN_PASSWORD} ký tự.")
            continue
        if pw != getpass.getpass("Nhập lại: "):
            print("Hai lần nhập không khớp.")
            continue
        return pw


def _get(db, code: str) -> User:
    user = db.query(User).filter(User.employee_code == code).first()
    if not user:
        sys.exit(f"Không tìm thấy tài khoản {code}")
    return user


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Quản lý tài khoản Thanh tra / Quản trị (chạy trên máy chủ)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="Liệt kê tài khoản đặc quyền")
    c = sub.add_parser("create", help="Tạo tài khoản mới")
    c.add_argument("code"); c.add_argument("full_name"); c.add_argument("department")
    c.add_argument("role", choices=ROLE_CHOICES)
    r = sub.add_parser("set-role", help="Đổi vai trò")
    r.add_argument("code"); r.add_argument("role", choices=ROLE_CHOICES)
    for name in ("lock", "unlock", "reset-password"):
        sub.add_parser(name).add_argument("code")
    args = p.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if args.cmd == "list":
            for u in db.query(User).filter(User.role.in_([Role.COMPLIANCE_OFFICER, Role.SYSTEM_ADMIN])).all():
                print(f"{u.employee_code:10} {u.role:20} {'hoạt động' if u.is_active else 'ĐÃ KHÓA':10} {u.full_name}")
            return 0
        if args.cmd == "create":
            if db.query(User).filter(User.employee_code == args.code).first():
                sys.exit(f"Mã {args.code} đã tồn tại")
            db.add(User(employee_code=args.code, full_name=args.full_name, department=args.department,
                        role=args.role, password_hash=get_password_hash(_ask_password()), is_active=True))
            db.commit()
            log.info("create user=%s role=%s", args.code, args.role)
        else:
            user = _get(db, args.code)
            if args.cmd == "set-role":
                old = user.role
                user.role = args.role
                log.info("set-role user=%s %s -> %s", args.code, old, args.role)
            elif args.cmd in ("lock", "unlock"):
                user.is_active = args.cmd == "unlock"
                log.info("%s user=%s", args.cmd, args.code)
            elif args.cmd == "reset-password":
                user.password_hash = get_password_hash(_ask_password())
                log.info("reset-password user=%s", args.code)
            db.commit()
    print("Đã thực hiện.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
