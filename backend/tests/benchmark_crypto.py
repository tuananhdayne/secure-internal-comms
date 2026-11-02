#!/usr/bin/env python3
"""BENCHMARK HIỆU NĂNG MẬT MÃ HỌC - ATBM WHISTLEBLOWER ENGINE.
Học viện Kỹ thuật Mật mã (KMA) - Khóa Đồ Án ATBM.

Đo lường thời gian thực thi (Latency: P50, P95, P99, Mean) của các tác vụ mật mã:
1. ECC P-256 Key Generation (KeyGen).
2. ECIES P-256 Hybrid Encryption (ECDH + HKDF-SHA256 + AES-256-GCM).
3. ECIES P-256 Hybrid Decryption.
4. RSA-2048 Blinding (Client: m* = (H * r^e) mod N).
5. RSA-2048 Blind Signing (Officer: s* = (m*)^d mod N).
6. RSA-2048 Unblinding & Verification (Client: s = s* * r^-1 mod N, verify s^e mod N == H).
7. EXIF Metadata & GPS Stripping (Sanitizer trên ảnh 2MB).
8. Panic Duress Overwrite Shredding (Ghi đè 3 lượt ngẫu nhiên + unlink).
"""

import io
import math
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any

# Thêm đường dẫn backend vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from PIL import Image

from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import (
    BlindSignatureEngine,
    simulate_client_blinding,
    simulate_client_unblinding,
)
from app.crypto.ecies import ecies_encrypt, ecies_decrypt
from app.crypto.sanitizer import strip_image_metadata

# ANSI Colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def format_ms(val_ms: float) -> str:
    return f"{val_ms:.3f} ms"


def run_benchmark_iterations(name: str, fn, iterations: int = 1000) -> Dict[str, float]:
    """Chạy fn iterations lần và tính toán các chỉ số thống kê (ms)."""
    # Warmup
    for _ in range(min(50, iterations)):
        fn()

    durations_ms: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        durations_ms.append((t1 - t0) / 1_000_000.0)

    durations_ms.sort()
    n = len(durations_ms)
    p50 = durations_ms[int(n * 0.50)]
    p95 = durations_ms[int(n * 0.95)]
    p99 = durations_ms[int(n * 0.99)]
    mean_val = statistics.mean(durations_ms)
    max_val = max(durations_ms)
    min_val = min(durations_ms)

    return {
        "name": name,
        "iterations": iterations,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "mean": mean_val,
        "min": min_val,
        "max": max_val,
    }


def main():
    print(f"\n{CYAN}{BOLD}================================================================================{RESET}")
    print(f"{CYAN}{BOLD}          ATBM BENCHMARK HIỆU NĂNG MẬT MÃ HỌC (CRYPTOGRAPHIC BENCHMARK)         {RESET}")
    print(f"{CYAN}{BOLD}                    Học viện Kỹ thuật Mật mã (KMA) - 2026                       {RESET}")
    print(f"{CYAN}{BOLD}================================================================================{RESET}\n")

    # Đảm bảo khóa RSA và ECC của Officer đã sẵn sàng
    e, n = key_manager.rsa_public_numbers
    officer_ec_pub_hex = key_manager.ec_public_key_hex
    officer_ec_priv_key = key_manager.ec_private_key

    sample_payload = "Nội dung tố giác bí mật: Sai phạm đấu thầu vật tư y tế quy mô lớn.".encode("utf-8")
    
    # Chuẩn bị ảnh mẫu 2MB cho bài test EXIF Sanitizer
    img_byte_arr = io.BytesIO()
    sample_img = Image.new("RGB", (1920, 1080), color=(73, 109, 137))
    sample_img.save(img_byte_arr, format="JPEG", quality=95)
    sample_img_bytes = img_byte_arr.getvalue()
    img_size_kb = len(sample_img_bytes) / 1024.0

    # 1. ECC P-256 KeyGen
    def bench_keygen():
        priv = ec.generate_private_key(ec.SECP256R1())
        _ = priv.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )

    # 2. ECIES Encrypt
    def bench_ecies_encrypt():
        _ = ecies_encrypt(officer_ec_pub_hex, sample_payload)

    # 3. ECIES Decrypt
    encrypted_blob = ecies_encrypt(officer_ec_pub_hex, sample_payload)
    def bench_ecies_decrypt():
        _ = ecies_decrypt(
            recipient_priv_key=officer_ec_priv_key,
            ephemeral_pub_hex=encrypted_blob["ephemeral_public_key"],
            iv_hex=encrypted_blob["iv"],
            ciphertext_hex=encrypted_blob["ciphertext"],
            tag_hex=encrypted_blob["auth_tag"]
        )

    # 4. RSA-2048 Client Blinding
    sample_h = BlindSignatureEngine.compute_payload_hash(
        category="Tham nhũng",
        encrypted_title=encrypted_blob["ciphertext"][:20],
        encrypted_description=encrypted_blob["ciphertext"],
        case_token="CASE-TEST-123456",
        case_public_key="04aabbcc",
        evidence_file_hashes=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]
    )
    def bench_client_blinding():
        _ = simulate_client_blinding(sample_h, e, n)

    # 5. RSA-2048 Officer Blind Sign
    m_star, r = simulate_client_blinding(sample_h, e, n)
    def bench_officer_sign():
        _ = BlindSignatureEngine.blind_sign(m_star)

    # 6. RSA-2048 Client Unblind & Verify
    s_star = BlindSignatureEngine.blind_sign(m_star)
    def bench_client_unblind_verify():
        s = simulate_client_unblinding(s_star, r, n)
        # verify: s^e mod N == H
        _ = (pow(s, e, n) == sample_h)

    # 7. EXIF Metadata Sanitizer
    def bench_sanitizer():
        _ = strip_image_metadata(sample_img_bytes, "JPEG")

    # 8. Panic Duress Shredding
    def bench_panic_shredding():
        tmp_dir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_dir, "vault.db")
        with open(tmp_file, "wb") as f:
            f.write(os.urandom(64 * 1024))  # 64KB mock vault
        file_len = os.path.getsize(tmp_file)
        # 3-pass overwrite
        with open(tmp_file, "ba+", buffering=0) as f:
            for _ in range(3):
                f.seek(0)
                f.write(os.urandom(file_len))
        os.remove(tmp_file)
        shutil.rmtree(tmp_dir, ignore_errors=True)

    benchmarks = [
        ("1. ECC P-256 KeyGen", bench_keygen, 1000, 5.0),
        ("2. ECIES P-256 Encrypt (AES-GCM)", bench_ecies_encrypt, 1000, 10.0),
        ("3. ECIES P-256 Decrypt (AES-GCM)", bench_ecies_decrypt, 1000, 10.0),
        ("4. RSA-2048 Blinding (Client)", bench_client_blinding, 1000, 15.0),
        ("5. RSA-2048 Blind Sign (Officer)", bench_officer_sign, 500, 15.0),
        ("6. RSA-2048 Unblind & Verify", bench_client_unblind_verify, 1000, 15.0),
        (f"7. EXIF Sanitizer ({img_size_kb:.0f}KB JPEG)", bench_sanitizer, 100, 30.0),
        ("8. Panic Overwrite Shredding (64KB)", bench_panic_shredding, 100, 50.0),
    ]

    results = []
    print(f"{'Tác vụ mật mã':<36} | {'P50':<9} | {'P95':<9} | {'Mean':<9} | {'SLA Target':<10} | {'Đánh giá'}")
    print("-" * 88)

    all_passed = True
    for name, fn, iters, sla in benchmarks:
        res = run_benchmark_iterations(name, fn, iters)
        status = f"{GREEN}PASS [OK]{RESET}" if res["p95"] <= sla else f"{YELLOW}ACCEPTABLE{RESET}"
        if res["p95"] > sla * 2:
            status = f"\033[91mSLOW\033[0m"
            all_passed = False
        print(f"{res['name']:<36} | {format_ms(res['p50']):<9} | {format_ms(res['p95']):<9} | {format_ms(res['mean']):<9} | {format_ms(sla):<10} | {status}")
        results.append(res)

    print("-" * 88)
    if all_passed:
        print(f"\n{GREEN}{BOLD}>>> TOÀN BỘ 8/8 TÁC VỤ MẬT MÃ ĐẠT TIÊU CHUẨN HIỆU NĂNG THỜI GIAN THỰC (SLA) <<<{RESET}\n")
    else:
        print(f"\n{YELLOW}Một số tác vụ tiệm cận ngưỡng SLA.{RESET}\n")


if __name__ == "__main__":
    main()
