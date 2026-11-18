"""Chạy backend qua HTTPS/TLS (uvicorn + chứng chỉ trong backend/certs/).

    python scripts/gen_dev_certs.py   # một lần, sinh chứng chỉ
    python run_https.py               # https://0.0.0.0:8443

Biến môi trường tùy chọn: HTTPS_HOST (mặc định 0.0.0.0), HTTPS_PORT (mặc định 8443).
"""
import os
import ssl
import sys
from pathlib import Path

import uvicorn

BASE_DIR = Path(__file__).resolve().parent
CERT = BASE_DIR / "certs" / "server.crt"
KEY = BASE_DIR / "certs" / "server.key"

if __name__ == "__main__":
    if not CERT.exists() or not KEY.exists():
        sys.exit("Chưa có chứng chỉ. Chạy trước: python scripts/gen_dev_certs.py")
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HTTPS_HOST", "0.0.0.0"),
        port=int(os.getenv("HTTPS_PORT", "8443")),
        ssl_certfile=str(CERT),
        ssl_keyfile=str(KEY),
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        ssl_ciphers="ECDHE+AESGCM:ECDHE+CHACHA20",
        proxy_headers=False,
        access_log=False,  # access log mặc định ghi IP; app tự ghi log an toàn (app/core/logging.py)
    )
