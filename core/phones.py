"""Chuẩn hoá số điện thoại Việt Nam để so sánh trùng."""
import re

# Các nhóm chữ số có thể là SĐT (cho phép dấu cách, chấm, gạch, ngoặc ở giữa)
_PHONE_CHUNK = re.compile(r'(?:\+?\d[\d\s.\-()]{5,18}\d)')
_NON_DIGIT = re.compile(r'\D')

# Đầu số di động + cố định VN hợp lệ (sau khi bỏ 0 / +84)
_VALID_CORE_HEAD = set('23456789')


def _to_text(value):
    """Đổi giá trị ô Excel thành chuỗi, xử lý cả trường hợp Excel lưu SĐT dạng số."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return ''
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            return ''
        if float(value).is_integer():
            return str(int(value))
        return repr(value)
    return str(value).strip()


def _core(digits):
    """Bỏ mã quốc gia / số 0 đứng đầu, trả về phần lõi."""
    if digits.startswith('0084'):
        digits = digits[4:]
    elif digits.startswith('84') and len(digits) >= 11:
        digits = digits[2:]
    elif digits.startswith('00'):
        digits = digits[2:]
    return digits.lstrip('0')


def _classify(digits):
    """(core, is_vn) - core là khoá so sánh."""
    core = _core(digits)
    if not core:
        return None, False
    if len(core) in (9, 10) and core[0] in _VALID_CORE_HEAD:
        return core, True
    # Không đúng chuẩn VN nhưng vẫn là dãy số dài -> vẫn cho so khớp thô
    if 6 <= len(core) <= 15:
        return core, False
    return None, False


def extract_phones(value, strict=False):
    """Lấy tất cả SĐT trong một ô. Trả về list (key, display).

    key     : khoá so sánh (đã bỏ 0 / +84)
    display : dạng hiển thị, luôn giữ số 0 ở đầu
    """
    text = _to_text(value)
    if not text:
        return []
    out, seen = [], set()
    for chunk in _PHONE_CHUNK.findall(text):
        digits = _NON_DIGIT.sub('', chunk)
        if not digits:
            continue
        core, is_vn = _classify(digits)
        if not core or (strict and not is_vn):
            continue
        if core in seen:
            continue
        seen.add(core)
        out.append((core, '0' + core if is_vn else digits))
    return out


def normalize_phone(value, strict=False):
    """Lấy SĐT đầu tiên của ô -> (key, display) hoặc (None, None)."""
    found = extract_phones(value, strict=strict)
    return found[0] if found else (None, None)


def looks_like_phone(value):
    """Dùng khi tự dò cột SĐT: chỉ nhận số đúng chuẩn VN."""
    return bool(extract_phones(value, strict=True))
