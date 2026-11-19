#!/usr/bin/env bash
# Khởi động tool check trùng SĐT (tự tạo môi trường ở lần chạy đầu)
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8686}"
export PORT

if [ ! -x "./venv/bin/python" ]; then
  echo ">> Chưa có môi trường ảo, đang tạo lần đầu..."
  if python3 -m venv venv 2>/dev/null; then
    :
  elif python3 -m virtualenv venv 2>/dev/null; then
    :
  else
    echo "!! Máy chưa có python3-venv. Chạy một trong hai cách sau rồi thử lại:"
    echo "   sudo apt install python3-venv python3-pip"
    echo "   hoặc: python3 -m pip install --user virtualenv"
    exit 1
  fi
  ./venv/bin/python -m pip install -q --upgrade pip
  ./venv/bin/pip install -q -r requirements.txt
  echo ">> Đã cài xong thư viện."
fi

echo "============================================================"
echo "  TOOL CHECK TRÙNG SỐ ĐIỆN THOẠI"
echo "  Mở trình duyệt: http://127.0.0.1:${PORT}"
echo "  Dừng: Ctrl + C"
echo "============================================================"
exec ./venv/bin/python app.py
