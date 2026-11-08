#!/usr/bin/env python3
"""LOAD TESTING & HIGH-CONCURRENCY STRESS TEST - ATBM ENGINE.
Học viện Kỹ thuật Mật mã (KMA) - Khóa Đồ Án ATBM.

Kiểm thử khả năng chịu tải đồng thời (50 workers) trên FastAPI & SQLite WAL:
1. Benchmark Concurrent Read: GET /health và GET /api/v1/posts/ (200 requests, 50 threads).
2. Benchmark Concurrent Blind Signing: POST /api/v1/compliance/blind-sign (50 threads).
3. Test Spam Protection & Quota Rate Limiter: Kiểm tra chặn HTTP 429 khi vượt quá hạn ngạch tuần.
"""

import concurrent.futures
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.identified import User, BlindSignQuota
from app.core.security import create_access_token, get_password_hash
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import simulate_client_blinding

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_load_test(
    name: str,
    worker_fn,
    total_requests: int = 200,
    concurrency: int = 50
) -> Dict[str, Any]:
    """Chạy đồng thời total_requests bằng ThreadPoolExecutor với số workers = concurrency."""
    latencies_ms: List[float] = []
    status_codes: List[int] = []

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker_fn, i) for i in range(total_requests)]
        for f in concurrent.futures.as_completed(futures):
            status_code, dur_ms = f.result()
            status_codes.append(status_code)
            latencies_ms.append(dur_ms)
    t_end = time.perf_counter()

    total_time_sec = t_end - t_start
    rps = total_requests / total_time_sec if total_time_sec > 0 else 0

    latencies_ms.sort()
    n = len(latencies_ms)
    p50 = latencies_ms[int(n * 0.50)]
    p95 = latencies_ms[int(n * 0.95)]
    p99 = latencies_ms[int(n * 0.99)]
    mean_val = statistics.mean(latencies_ms)

    success_count = sum(1 for c in status_codes if 200 <= c < 300)
    client_error_count = sum(1 for c in status_codes if 400 <= c < 500)
    server_error_count = sum(1 for c in status_codes if c >= 500)

    return {
        "name": name,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "total_time_sec": total_time_sec,
        "rps": rps,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "mean": mean_val,
        "success": success_count,
        "client_error": client_error_count,
        "server_error": server_error_count,
    }


def setup_load_users(db, count: int = 20) -> List[User]:
    """Tạo người dùng kiểm thử tải trong CSDL và trả về danh sách User."""
    users = []
    pwd_hash = get_password_hash("testPass123@")
    for i in range(count):
        code = f"LOAD_USER_{i:02d}"
        user = db.query(User).filter(User.employee_code == code).first()
        if not user:
            user = User(
                employee_code=code,
                full_name=f"Load Tester {i}",
                password_hash=pwd_hash,
                role="EMPLOYEE",
                department="Kiểm thử tải",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        users.append(user)

    # Thêm user cho kịch bản spam
    spam_code = "SPAM_USER_99"
    spam_user = db.query(User).filter(User.employee_code == spam_code).first()
    if not spam_user:
        spam_user = User(
            employee_code=spam_code,
            full_name="Spam Tester",
            password_hash=pwd_hash,
            role="EMPLOYEE",
            department="Ban Kiểm thử",
            is_active=True
        )
        db.add(spam_user)
        db.commit()
        db.refresh(spam_user)
    users.append(spam_user)
    return users


def cleanup_load_users(db, users: List[User]):
    """Dọn dẹp users kiểm thử tải."""
    user_ids = [u.id for u in users]
    db.query(BlindSignQuota).filter(BlindSignQuota.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


def main():
    print(f"\n{CYAN}{BOLD}================================================================================{RESET}")
    print(f"{CYAN}{BOLD}        ATBM KIỂM THỬ TẢI CAO & CHỊU TẢI ĐỒNG THỜI (HIGH-CONCURRENCY TEST)      {RESET}")
    print(f"{CYAN}{BOLD}                     Học viện Kỹ thuật Mật mã (KMA) - 2026                      {RESET}")
    print(f"{CYAN}{BOLD}================================================================================{RESET}\n")

    db = SessionLocal()
    users = setup_load_users(db, 20)
    load_users = users[:-1]
    spam_user = users[-1]

    client = TestClient(app)
    e, n = key_manager.rsa_public_numbers

    # Tạo JWT token cho NV001
    seeded_nv001 = db.query(User).filter(User.employee_code == "NV001").first()
    nv001_id = seeded_nv001.id if seeded_nv001 else load_users[0].id
    token_emp = create_access_token(subject=str(nv001_id), role="EMPLOYEE")
    auth_headers = {"Authorization": f"Bearer {token_emp}"}

    # Test 1: Đọc bản tin đồng thời (200 requests, 50 workers)
    def worker_read_posts(req_id: int):
        t0 = time.perf_counter_ns()
        resp = client.get("/api/v1/posts/", headers=auth_headers)
        t1 = time.perf_counter_ns()
        return resp.status_code, (t1 - t0) / 1_000_000.0

    print(">>> 1. Đang chạy kiểm thử tải Đọc Bản Tin (/api/v1/posts/) - 200 reqs, 50 threads...")
    res_read = run_load_test("Đọc Bản Tin Nội Bộ", worker_read_posts, 200, 50)

    # Test 2: Xin chữ ký mù đồng thời với 20 nhân viên kiểm thử
    tokens = [
        create_access_token(subject=str(u.id), role="EMPLOYEE")
        for u in load_users
    ]

    def worker_blind_sign(req_id: int):
        user_tok = tokens[req_id % len(tokens)]
        # Client làm mù m* = (H * r^e) mod N
        m_star, _ = simulate_client_blinding(123456789 + req_id, e, n)
        t0 = time.perf_counter_ns()
        resp = client.post(
            "/api/v1/compliance/blind-sign",
            headers={"Authorization": f"Bearer {user_tok}"},
            json={"blinded_hash": str(m_star)}
        )
        t1 = time.perf_counter_ns()
        return resp.status_code, (t1 - t0) / 1_000_000.0

    print(">>> 2. Đang chạy kiểm thử tải Ký Mù RSA (/api/v1/compliance/blind-sign) - 60 reqs, 20 threads...")
    res_sign = run_load_test("Ký Mù RSA-2048", worker_blind_sign, 60, 20)

    # Test 3: Kiểm thử Chống Spam & Quota Limiter (1 nhân viên gửi liên tiếp 7 requests, quota = 5)
    print(">>> 3. Đang kiểm tra cơ chế Chống Spam & Giới Hạn Hạn Ngạch (Quota Limiter)...")
    spam_token = create_access_token(subject=str(spam_user.id), role="EMPLOYEE")
    spam_headers = {"Authorization": f"Bearer {spam_token}"}
    
    quota_results = []
    total_spam_reqs = settings.WEEKLY_BLIND_SIGN_QUOTA + 2  # 7 requests
    for req_idx in range(total_spam_reqs):
        m_star, _ = simulate_client_blinding(999999 + req_idx, e, n)
        resp = client.post(
            "/api/v1/compliance/blind-sign",
            headers=spam_headers,
            json={"blinded_hash": str(m_star)}
        )
        quota_results.append(resp.status_code)

    # Dọn dẹp dữ liệu
    cleanup_load_users(db, users)
    db.close()

    # In bảng tổng kết
    print(f"\n{BOLD}{'Kịch bản kiểm thử tải':<30} | {'Reqs':<6} | {'Threads':<8} | {'Throughput (RPS)':<18} | {'P50':<9} | {'P95':<9} | {'Server Err':<10}{RESET}")
    print("-" * 100)
    for r in [res_read, res_sign]:
        print(f"{r['name']:<30} | {r['total_requests']:<6} | {r['concurrency']:<8} | {r['rps']:<18.1f} | {r['p50']:<6.2f} ms | {r['p95']:<6.2f} ms | {r['server_error']}")
    print("-" * 100)

    # Đánh giá Quota Limiter
    quota_429_count = quota_results.count(429)
    quota_200_count = quota_results.count(200)
    print(f"Kiểm thử Quota Limiter: 5 yêu cầu liên tiếp -> {quota_200_count} thành công (200), {quota_429_count} bị chặn (429 Quota Exceeded).")
    
    if res_read["server_error"] == 0 and res_sign["server_error"] == 0 and quota_429_count >= 2:
        print(f"\n{GREEN}{BOLD}>>> TOÀN BỘ KỊCH BẢN CHỊU TẢI & CHỐNG SPAM ĐẠT CHUẨN XUẤT SẮC (0 SERVER ERRORS, QUOTA ENFORCED) <<<{RESET}\n")
    else:
        print(f"\n{YELLOW}Kiểm thử hoàn tất với một số cảnh báo.{RESET}\n")


if __name__ == "__main__":
    main()
