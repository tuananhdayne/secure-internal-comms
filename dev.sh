#!/usr/bin/env bash
# ATBM — lệnh phát triển thường dùng. Chạy `./dev.sh` (hoặc `bash dev.sh help`) để xem danh sách.
# Yêu cầu: Python 3.11+. Mọi lệnh Python chạy trong backend/.venv.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"
PY="$VENV/bin/python"
PORT="${PORT:-8000}"

need_venv() { [ -x "$PY" ] || { echo "Chưa có môi trường ảo -> chạy: ./dev.sh setup"; exit 1; }; }

cmd="${1:-help}"; shift || true
case "$cmd" in
  setup)          # Tạo venv + cài thư viện + nạp dữ liệu mẫu
    [ -d "$VENV" ] || python3 -m venv "$VENV"
    "$PY" -m pip install -q -r "$BACKEND/requirements.txt"
    cd "$BACKEND" && "$PY" -m app.db.seed ;;
  run)            # Chạy backend HTTP (http://127.0.0.1:8000, tự reload khi sửa code)
    need_venv; cd "$BACKEND" && exec "$PY" -m uvicorn app.main:app --reload --port "$PORT" --no-access-log ;;
  run-debug)      # Như `run` nhưng LOG_LEVEL=DEBUG
    need_venv; cd "$BACKEND" && LOG_LEVEL=DEBUG exec "$PY" -m uvicorn app.main:app --reload --port "$PORT" --no-access-log ;;
  preflight)      # Kiểm tra cấu hình trước khi chạy thật (khóa JWT, demo, CORS, mật khẩu mẫu...)
    need_venv; cd "$BACKEND" && "$PY" scripts/preflight.py "$@" ;;
  certs)          # Sinh CA nội bộ + chứng chỉ TLS (thêm IP LAN: ./dev.sh certs 192.168.1.15)
    need_venv; cd "$BACKEND" && "$PY" scripts/gen_dev_certs.py "$@" ;;
  run-https)      # Chạy backend HTTPS (https://0.0.0.0:8443; emulator: https://10.0.2.2:8443)
    need_venv
    [ -f "$BACKEND/certs/server.crt" ] || { echo "Chưa có chứng chỉ -> chạy: ./dev.sh certs"; exit 1; }
    cd "$BACKEND" && exec "$PY" run_https.py ;;
  lan)            # Thử trong mạng Wi-Fi chung: chứng chỉ có IP máy này + build APK debug trỏ về đây + chạy HTTPS
    need_venv
    # Các IPv4 trong mạng LAN của máy (bỏ docker/bridge); APK trỏ về IP Wi-Fi nếu có
    mapfile -t IPS < <(ip -4 -o addr show scope global | awk '$2 !~ /^(docker|br-|veth|virbr)/ {split($4,a,"/"); print a[1]}')
    [ "${#IPS[@]}" -gt 0 ] || { echo "Không tìm thấy IP mạng LAN — máy đã kết nối Wi-Fi chưa?"; exit 1; }
    LAN_IP="${1:-$(ip -4 -o addr show scope global | awk '$2 ~ /^wl/ {split($4,a,"/"); print a[1]; exit}')}"
    LAN_IP="${LAN_IP:-${IPS[0]}}"
    MISSING=0
    for ip in "${IPS[@]}" "$LAN_IP"; do
      "$PY" - "$BACKEND/certs/server.crt" "$ip" <<'PYEOF' || MISSING=1
import ipaddress, sys
from cryptography import x509
try:
    cert = x509.load_pem_x509_certificate(open(sys.argv[1], "rb").read())
    ips = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
except Exception:
    sys.exit(1)
sys.exit(0 if ipaddress.ip_address(sys.argv[2]) in ips else 1)
PYEOF
    done
    if [ "$MISSING" = 1 ]; then
      echo "==> Sinh lại chứng chỉ cho: ${IPS[*]}"
      (cd "$BACKEND" && "$PY" scripts/gen_dev_certs.py "${IPS[@]}")
    fi
    echo "==> Build APK debug trỏ về https://$LAN_IP:8443/"
    (cd "$ROOT/android" && ./gradlew -q assembleDebug "-Patbm.serverUrl=https://$LAN_IP:8443/")
    mkdir -p "$ROOT/dist" && cp "$ROOT/android/app/build/outputs/apk/debug/app-debug.apk" "$ROOT/dist/cong-noi-bo-lan.apk"
    echo "==> APK: dist/cong-noi-bo-lan.apk  (cài: adb install -r dist/cong-noi-bo-lan.apk, hoặc gửi file sang điện thoại)"
    echo "    Điện thoại phải cùng Wi-Fi. Nếu không kết nối được: sudo ufw allow 8443/tcp"
    echo "    Web quản trị: https://$LAN_IP:8443/admin  (trình duyệt sẽ cảnh báo CA nội bộ — bình thường)"
    cd "$BACKEND" && exec "$PY" run_https.py ;;
  seed)           # Nạp dữ liệu mẫu (chỉ thêm tài khoản/bài viết còn thiếu)
    need_venv; cd "$BACKEND" && "$PY" -m app.db.seed ;;
  test)           # Toàn bộ pytest (CSDL tạm, không đụng app.db). Thêm tham số pytest tùy ý.
    need_venv; cd "$BACKEND" && "$PY" -m pytest -q "$@" ;;
  test-fast)      # pytest dừng ở lỗi đầu tiên, in chi tiết
    need_venv; cd "$BACKEND" && "$PY" -m pytest -x -vv --tb=short "$@" ;;
  test-security)  # 5 kịch bản bảo mật cốt lõi (không cần server; dùng CSDL tạm, không đụng app.db)
    need_venv; cd "$BACKEND" && "$PY" run_security_tests.py ;;
  reset-db)       # XÓA app.db + tệp bằng chứng rồi nạp lại dữ liệu mẫu (hỏi xác nhận)
    need_venv
    read -r -p "Xóa toàn bộ dữ liệu trong backend/app.db và backend/uploads/evidences? [y/N] " ans
    if [ "$ans" = "y" ]; then
      rm -f "$BACKEND"/app.db "$BACKEND"/app.db-wal "$BACKEND"/app.db-shm
      find "$BACKEND/uploads/evidences" -type f -delete 2>/dev/null || true
      cd "$BACKEND" && "$PY" -m app.db.seed
    else echo "Đã hủy."; fi ;;
  flatten-kotlin) # Rút gọn thư mục Kotlin (bỏ com/atbm/app khỏi đường dẫn, giữ package)
    bash "$ROOT/scripts/flatten_kotlin_layout.sh" ;;
  clean)          # Xóa cache Python / pytest
    find "$BACKEND" -name __pycache__ -type d -prune -exec rm -rf {} +
    rm -rf "$BACKEND/.pytest_cache" "$ROOT/.pytest_cache" ;;
  help|-h|--help)
    echo "Cách dùng: ./dev.sh <lệnh> [tham số]"; echo
    awk '/^  [a-z|-]+\)[ \t]+#/ { name=$1; sub(/\)$/, "", name); sub(/^[^#]*# /, ""); printf "  \033[36m%-16s\033[0m %s\n", name, $0 }' "$0" ;;
  *)
    echo "Lệnh không hợp lệ: $cmd"; "$0" help; exit 1 ;;
esac
