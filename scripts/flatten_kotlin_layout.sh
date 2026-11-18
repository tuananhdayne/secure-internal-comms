#!/usr/bin/env bash
# Rút gọn cấu trúc thư mục Kotlin theo khuyến nghị của Kotlin:
# "bỏ phần package gốc chung (com.atbm.app) khỏi đường dẫn thư mục".
#
#   android/app/src/main/kotlin/com/atbm/app/ui/screens/LoginScreen.kt
#   -> android/app/src/main/kotlin/ui/screens/LoginScreen.kt
#
# Câu lệnh `package com.atbm.app...` trong từng file GIỮ NGUYÊN, nên import, build,
# applicationId và namespace không thay đổi. Dùng `git mv` để giữ lịch sử file.
#
# Chạy từ bất kỳ đâu:  bash ~/KMA/atbm/scripts/flatten_kotlin_layout.sh
set -euo pipefail
cd "$(dirname "$0")/.."

in_git=false
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && in_git=true

flatten() {
    local from="$1" to="$2"
    if [ ! -d "$from" ]; then
        echo "[bỏ qua] $from không tồn tại (có thể đã rút gọn rồi)"
        return 0
    fi
    shopt -s nullglob dotglob
    for item in "$from"/*; do
        local name; name="$(basename "$item")"
        if [ -e "$to/$name" ]; then
            echo "[LỖI] $to/$name đã tồn tại — dừng lại để tránh ghi đè." >&2
            exit 1
        fi
        if $in_git && [ -n "$(git ls-files -- "$item" | head -n1)" ]; then
            git mv "$item" "$to/$name"
        else
            mv "$item" "$to/$name"
        fi
        echo "  $item -> $to/$name"
    done
    shopt -u nullglob dotglob
    # Xóa các thư mục com/atbm/app đã rỗng (dừng khi gặp thư mục còn file)
    rmdir -p "$from" 2>/dev/null || true
}

echo "== Mã nguồn chính =="
flatten android/app/src/main/kotlin/com/atbm/app android/app/src/main/kotlin
echo "== Unit test =="
flatten android/app/src/test/java/com/atbm/app android/app/src/test/java
if [ -d android/app/src/androidTest/java/com/atbm/app ]; then
    echo "== Instrumented test =="
    flatten android/app/src/androidTest/java/com/atbm/app android/app/src/androidTest/java
fi

echo
echo "Hoàn tất. Cấu trúc mới:"
find android/app/src/main/kotlin android/app/src/test/java -name '*.kt' | sort
echo
echo "Tiếp theo: mở Android Studio -> File > Sync Project with Gradle Files, rồi Build > Make Project."
