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
  certs)          # Sinh CA nội bộ + chứng chỉ TLS (thêm IP LAN: ./dev.sh certs 192.168.1.15)
    need_venv; cd "$BACKEND" && "$PY" scripts/gen_dev_certs.py "$@" ;;
  run-https)      # Chạy backend HTTPS (https://0.0.0.0:8443; emulator: https://10.0.2.2:8443)
    need_venv
    [ -f "$BACKEND/certs/server.crt" ] || { echo "Chưa có chứng chỉ -> chạy: ./dev.sh certs"; exit 1; }
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
