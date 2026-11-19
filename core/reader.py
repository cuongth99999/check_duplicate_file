"""Đọc file Excel: tự dò dòng tiêu đề, cột SĐT, cột tên khách."""
import unicodedata
import openpyxl

from .phones import extract_phones, looks_like_phone

SUPPORTED_EXT = ('.xlsx', '.xlsm', '.xltx', '.xltm')

MAX_HEADER_SCAN = 25        # số dòng đầu tối đa để dò tiêu đề
PROBE_ROWS = 60             # số dòng dữ liệu dùng để dò cột theo nội dung

PHONE_KEYS = (
    'sodienthoai', 'sdt', 'dienthoai', 'sodt', 'dthoai', 'phone', 'mobile',
    'telephone', 'tel', 'zalo', 'sodienthoaikhachhang', 'lienhe', 'sodienthoaizalo',
)
NAME_KEYS = (
    'hovaten', 'hoten', 'khachhang', 'tenkhachhang', 'ten', 'fullname', 'name',
    'customer', 'customername', 'nguoinhan', 'tennguoinhan',
)


def slug(text):
    """'Số điện thoại ' -> 'sodienthoai' (bỏ dấu, bỏ ký tự lạ)."""
    if text is None:
        return ''
    s = unicodedata.normalize('NFD', str(text))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.replace('Đ', 'D').replace('đ', 'd')
    return ''.join(c for c in s.lower() if c.isalnum())


def _match_key(label, keys):
    s = slug(label)
    if not s:
        return 0
    for i, k in enumerate(keys):
        if s == k:
            return 1000 - i
    for i, k in enumerate(keys):
        if k in s or s in k:
            return 500 - i
    return 0


def _grid(ws, max_row, max_col):
    """Đọc trước vài dòng đầu thành ma trận để dò cấu trúc."""
    rows = []
    for r in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col, values_only=True):
        rows.append(list(r))
    return rows


def detect_layout(rows):
    """Dò (header_row, phone_col, name_col) - đánh số từ 1. header_row=0 nghĩa là không có tiêu đề."""
    n_col = max((len(r) for r in rows), default=0)
    if not n_col:
        return 0, 0, 0

    # 1) Dò theo nhãn tiêu đề
    best = None
    for ri, row in enumerate(rows[:MAX_HEADER_SCAN], start=1):
        filled = sum(1 for v in row if v not in (None, ''))
        if filled < 2:
            continue
        for ci, val in enumerate(row, start=1):
            score = _match_key(val, PHONE_KEYS)
            if score and (best is None or score > best[0]):
                best = (score, ri, ci)
    if best:
        _, header_row, phone_col = best
        name_col = _pick_name_col(rows, header_row, phone_col, n_col)
        return header_row, phone_col, name_col

    # 2) Không có nhãn -> dò theo nội dung: cột nào nhiều SĐT nhất
    counts = [0] * (n_col + 1)
    first_hit = [None] * (n_col + 1)
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row, start=1):
            if looks_like_phone(val):
                counts[ci] += 1
                if first_hit[ci] is None:
                    first_hit[ci] = ri
    phone_col = max(range(1, n_col + 1), key=lambda c: counts[c])
    if counts[phone_col] == 0:
        return 0, 0, 0
    header_row = max((first_hit[phone_col] or 1) - 1, 0)
    name_col = _pick_name_col(rows, header_row, phone_col, n_col)
    return header_row, phone_col, name_col


def _pick_name_col(rows, header_row, phone_col, n_col):
    if header_row:
        header = rows[header_row - 1] if header_row <= len(rows) else []
        best = None
        for ci, val in enumerate(header, start=1):
            if ci == phone_col:
                continue
            score = _match_key(val, NAME_KEYS)
            if score and (best is None or score > best[0]):
                best = (score, ci)
        if best:
            return best[1]
    # fallback: cột chữ đầu tiên (không phải cột SĐT)
    start = header_row + 1
    for ci in range(1, n_col + 1):
        if ci == phone_col:
            continue
        texts = 0
        for row in rows[start - 1:start + 20]:
            if ci - 1 < len(row):
                v = row[ci - 1]
                if isinstance(v, str) and v.strip() and not looks_like_phone(v):
                    texts += 1
        if texts >= 3:
            return ci
    return 1 if phone_col != 1 else 0


class SheetInfo:
    __slots__ = ('name', 'index', 'header_row', 'phone_col', 'name_col',
                 'max_row', 'max_col', 'headers', 'data_rows')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def inspect_workbook(path):
    """Trả về list SheetInfo cho mọi sheet, kèm dò cấu trúc."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = []
        for idx, ws in enumerate(wb.worksheets):
            max_row = ws.max_row or 0
            max_col = ws.max_column or 0
            if not max_row or not max_col:
                sheets.append(SheetInfo(name=ws.title, index=idx, header_row=0, phone_col=0,
                                        name_col=0, max_row=0, max_col=0, headers=[], data_rows=0))
                continue
            probe = _grid(ws, min(max_row, MAX_HEADER_SCAN + PROBE_ROWS), max_col)
            header_row, phone_col, name_col = detect_layout(probe)
            headers = []
            if header_row and header_row <= len(probe):
                headers = ['' if v is None else str(v) for v in probe[header_row - 1]]
            if len(headers) < max_col:
                headers += [''] * (max_col - len(headers))
            sheets.append(SheetInfo(
                name=ws.title, index=idx, header_row=header_row, phone_col=phone_col,
                name_col=name_col, max_row=max_row, max_col=max_col, headers=headers,
                data_rows=max(max_row - header_row, 0),
            ))
        return sheets
    finally:
        wb.close()


def iter_phone_rows(path, layouts=None):
    """Duyệt toàn bộ file, sinh (sheet_name, row_idx, phone_key, phone_display, name).

    layouts: dict {sheet_name: (header_row, phone_col, name_col)} để ghi đè phần tự dò.
    """
    infos = {s.name: s for s in inspect_workbook(path)}
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            info = infos.get(ws.title)
            if info is None:
                continue
            header_row, phone_col, name_col = info.header_row, info.phone_col, info.name_col
            if layouts and ws.title in layouts:
                header_row, phone_col, name_col = layouts[ws.title]
            if not phone_col:
                continue
            for r_idx, row in enumerate(
                ws.iter_rows(min_row=header_row + 1, max_col=info.max_col, values_only=True),
                start=header_row + 1,
            ):
                if phone_col - 1 >= len(row):
                    continue
                cell = row[phone_col - 1]
                if cell in (None, ''):
                    continue
                name = ''
                if name_col and name_col - 1 < len(row):
                    nv = row[name_col - 1]
                    name = '' if nv is None else str(nv).strip()
                for key, disp in extract_phones(cell):
                    yield ws.title, r_idx, key, disp, name
    finally:
        wb.close()
