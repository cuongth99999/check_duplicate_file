"""Xuất file Excel mới - giữ nguyên 100% format cột, độ rộng, kiểu ô của file gốc.

Cách làm: mở chính file gốc rồi "dồn" các dòng cần giữ lên trên, sau đó xoá phần
dư ở cuối. Nhờ vậy toàn bộ style, độ rộng cột, merge, freeze... giữ nguyên bản
(không bị mất như khi tạo workbook mới rồi copy style qua).
"""
import os
import re
from copy import copy
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import range_boundaries

from .phones import normalize_phone
from .reader import slug
from .storage import EXPORT_DIR, safe_name

STT_KEYS = ('stt', 'tt', 'sothutu', 'so', 'no', 'num', 'index')
_CELL_REF = re.compile(r'^(\$?[A-Z]+)(\$?)(\d+)$')
_TOTAL_LABEL = re.compile(r'^(.*?)([\d.,]+)(\s*dòng.*)$', re.IGNORECASE)


# ------------------------------------------------------------------ dồn dòng

def _move_cell(ws, src_row, dst_row, col):
    src = ws.cell(row=src_row, column=col)
    dst = ws.cell(row=dst_row, column=col)
    dst.value = src.value
    dst._style = copy(src._style)
    dst.hyperlink = copy(src.hyperlink) if src.hyperlink is not None else None
    if src.comment is not None:
        try:
            dst.comment = copy(src.comment)
        except Exception:                                          # noqa: BLE001
            pass
    elif dst.comment is not None:
        dst.comment = None


def _force_text_phone(cell, normalize=False):
    """Giữ số 0 ở đầu SĐT: ghi dạng chuỗi + định dạng Text.

    normalize=True: đưa về dạng 0xxxxxxxxx (bỏ khoảng trắng, dấu chấm, +84).
    """
    if cell.value is None or cell.value == '':
        return
    if isinstance(cell.value, str) and not normalize:
        cell.value = cell.value.strip()
    else:
        _, disp = normalize_phone(cell.value)
        cell.value = disp or str(cell.value).strip()
    cell.number_format = '@'


def _remap_ref(ref, row_map, last_row):
    """Đổi địa chỉ vùng theo số dòng mới (dùng cho auto_filter)."""
    if not ref:
        return None

    def fix(token, fallback=None):
        m = _CELL_REF.match(token)
        if not m:
            return None
        col, dollar, row = m.group(1), m.group(2), int(m.group(3))
        new_row = row_map.get(row, fallback)
        if new_row is None:
            return None
        return f'{col}{dollar}{new_row}'

    if ':' in ref:
        a, b = ref.split(':', 1)
        fa, fb = fix(a), fix(b, fallback=last_row)
        return f'{fa}:{fb}' if fa and fb else None
    return fix(ref)


def _update_total_label(ws, header_row, data_count, max_col):
    """Cập nhật nhãn kiểu 'Tổng số: 1,127 dòng' ở phần tiêu đề cho khớp số dòng mới."""
    for row in range(1, header_row + 1):
        for col in range(1, min(max_col, 4) + 1):
            cell = ws.cell(row=row, column=col)
            if not isinstance(cell.value, str):
                continue
            m = _TOTAL_LABEL.match(cell.value.strip())
            if m and m.group(1).strip():
                cell.value = f'{m.group(1)}{data_count:,}{m.group(3)}'
                return


def _compact_sheet(ws, keep_rows, phone_col=0, header_row=0, stt_col=0,
                   normalize_phones=False):
    """Giữ lại đúng keep_rows (theo thứ tự gốc), dồn lên đầu sheet."""
    max_row = ws.max_row or 0
    max_col = ws.max_column or 1
    keep_rows = sorted(keep_rows)
    row_map = {src: new for new, src in enumerate(keep_rows, start=1)}

    # Lưu lại chiều cao / ẩn dòng trước khi dồn
    old_dims = {}
    for idx in keep_rows:
        dim = ws.row_dimensions.get(idx)
        if dim is not None:
            old_dims[row_map[idx]] = (dim.height, dim.hidden,
                                      copy(dim._style) if dim.has_style else None)

    merges = [str(m) for m in ws.merged_cells.ranges]
    for m in merges:
        ws.unmerge_cells(m)

    for src_row in keep_rows:                 # new_row <= src_row nên dồn xuôi là an toàn
        new_row = row_map[src_row]
        if new_row != src_row:
            for col in range(1, max_col + 1):
                _move_cell(ws, src_row, new_row, col)

    tail = max_row - len(keep_rows)
    if tail > 0:
        ws.delete_rows(len(keep_rows) + 1, tail)

    for new_row, (height, hidden, style) in old_dims.items():
        dim = ws.row_dimensions[new_row]
        dim.height = height
        dim.hidden = hidden
        if style is not None:
            dim._style = style

    for m in merges:
        min_col, min_row, max_c, max_r = range_boundaries(m)
        rows = list(range(min_row, max_r + 1))
        if not all(r in row_map for r in rows):
            continue
        new_rows = [row_map[r] for r in rows]
        if new_rows != list(range(new_rows[0], new_rows[0] + len(new_rows))):
            continue
        ws.merge_cells(start_row=new_rows[0], start_column=min_col,
                       end_row=new_rows[-1], end_column=max_c)

    # SĐT luôn là text + đánh lại STT
    stt = 0
    for src_row in keep_rows:
        new_row = row_map[src_row]
        if src_row <= header_row:
            continue
        if phone_col:
            _force_text_phone(ws.cell(row=new_row, column=phone_col), normalize_phones)
        if stt_col:
            stt += 1
            cell = ws.cell(row=new_row, column=stt_col)
            if cell.value is not None and str(cell.value).strip() != '':
                cell.value = stt

    # Dòng tiêu đề luôn giữ nguyên vị trí -> neo freeze/filter ngay dưới tiêu đề
    anchor = {r: r for r in range(1, header_row + 1)}
    anchor[header_row + 1] = min(header_row + 1, len(keep_rows))
    fallback_map = dict(anchor)
    fallback_map.update(row_map)

    if ws.auto_filter and ws.auto_filter.ref:
        new_ref = _remap_ref(str(ws.auto_filter.ref), fallback_map, len(keep_rows))
        ws.auto_filter.ref = new_ref if new_ref else None
    if ws.freeze_panes:
        new_ref = _remap_ref(str(ws.freeze_panes), fallback_map, len(keep_rows))
        ws.freeze_panes = new_ref if new_ref else None
    return row_map


# ------------------------------------------------------------------ sheet báo cáo

_HDR_FILL = PatternFill('solid', fgColor='FFE2EFDA')
_HDR_FONT = Font(bold=True)
_KIND_LABEL = {'folder': 'Trùng thư mục', 'self': 'Trùng trong file mới',
               'folder+self': 'Trùng thư mục + trong file mới'}


def _unique_sheet_title(wb, base):
    title, i = base, 1
    while title in wb.sheetnames:
        i += 1
        title = f'{base}_{i}'
    return title[:31]


def _add_report_sheet(wb, result, folders, base='BAO_CAO_TRUNG'):
    ws = wb.create_sheet(_unique_sheet_title(wb, base))
    s = result['summary']
    meta = [
        ('File kiểm tra', os.path.basename(result['file'])),
        ('Thời điểm kiểm tra', datetime.now().strftime('%d/%m/%Y %H:%M:%S')),
        ('Thư mục đối chiếu', ', '.join(folders) if folders else '(không chọn)'),
        ('Tổng dòng có SĐT', s['total_rows']),
        ('Dòng trùng với thư mục', s['dup_folder_rows']),
        ('Dòng trùng nội bộ trong file', s['dup_self_rows']),
        ('Tổng dòng trùng', s['dup_total_rows']),
        ('Số SĐT trùng (duy nhất)', s['dup_unique_phones']),
        ('Dòng còn lại sau khi loại trùng', s['clean_rows']),
    ]
    for i, (k, v) in enumerate(meta, start=1):
        ws.cell(row=i, column=1, value=k).font = _HDR_FONT
        ws.cell(row=i, column=2, value=v)

    start = len(meta) + 2
    headers = ['Sheet', 'Dòng', 'Số điện thoại', 'Tên khách (file mới)', 'Loại trùng',
               'Số nơi trùng', 'Trùng tại thư mục', 'Trùng tại file', 'Sheet cũ',
               'Dòng cũ', 'Tên khách (file cũ)']
    for ci, h in enumerate(headers, start=1):
        c = ws.cell(row=start, column=ci, value=h)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    r = start + 1
    for item in result['rows']:
        matches = list(item['matches'])
        if not matches:
            matches = [{'folder': '(trong chính file mới)', 'file': os.path.basename(result['file']),
                        'sheet': item['sheet'], 'row': item.get('self_first_row') or '',
                        'name': item['name']}]
        for m in matches:
            ws.cell(row=r, column=1, value=item['sheet'])
            ws.cell(row=r, column=2, value=item['row'])
            pc = ws.cell(row=r, column=3, value=item['phone'])
            pc.number_format = '@'
            ws.cell(row=r, column=4, value=item['name'])
            ws.cell(row=r, column=5, value=_KIND_LABEL.get(item['kind'], item['kind']))
            ws.cell(row=r, column=6, value=item['match_count'])
            ws.cell(row=r, column=7, value=m.get('folder', ''))
            ws.cell(row=r, column=8, value=m.get('file', ''))
            ws.cell(row=r, column=9, value=m.get('sheet', ''))
            ws.cell(row=r, column=10, value=m.get('row', '') or '')
            ws.cell(row=r, column=11, value=m.get('name', ''))
            r += 1

    for letter, width in zip('ABCDEFGHIJK', (22, 8, 18, 30, 28, 12, 26, 40, 18, 10, 30)):
        ws.column_dimensions[letter].width = width
    ws.freeze_panes = f'A{start + 1}'
    return ws


# ----------------------------------------------------------------------- xuất file

MODE_TAG = {'clean': 'da_loai_trung', 'dup': 'chi_dong_trung', 'report': 'bao_cao_trung'}


def _layout_for(result, sheet_name):
    for s in result['sheets']:
        if s['name'] == sheet_name:
            return s
    return None


def _detect_stt_col(sheet_meta):
    if not sheet_meta or not sheet_meta.get('header_row'):
        return 0
    for ci, h in enumerate(sheet_meta.get('headers') or [], start=1):
        if slug(h) in STT_KEYS:
            return ci
    return 0


def auto_filename(src_path, mode, custom=None):
    base = os.path.splitext(os.path.basename(src_path))[0]
    if custom and str(custom).strip():
        name = safe_name(str(custom).strip())
        if not name.lower().endswith(('.xlsx', '.xlsm')):
            name += '.xlsx'
        return name
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return safe_name(f'{base}__{MODE_TAG[mode]}__{stamp}.xlsx')


def export(src_path, result, mode, folders, filename=None, renumber_stt=True,
           with_report=True, update_total_label=True, normalize_phones=False,
           out_dir=EXPORT_DIR):
    """mode: 'clean' = bỏ dòng trùng | 'dup' = chỉ dòng trùng | 'report' = chỉ báo cáo."""
    os.makedirs(out_dir, exist_ok=True)
    out_name = auto_filename(src_path, mode, filename)
    out_path = os.path.join(out_dir, out_name)

    if mode == 'report':
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        _add_report_sheet(wb, result, folders)
        wb.save(out_path)
        return out_path, out_name

    dup_rows = {k: set(v) for k, v in result['dup_rows'].items()}
    wb = openpyxl.load_workbook(src_path)
    drop_sheets, stats = [], {}

    for ws in wb.worksheets:
        meta = _layout_for(result, ws.title)
        header_row = (meta or {}).get('header_row') or 0
        phone_col = (meta or {}).get('phone_col') or 0
        max_row = ws.max_row or 0
        dups = dup_rows.get(ws.title, set())

        if not phone_col or not max_row:
            # Sheet không có cột SĐT: file sạch giữ nguyên, file trùng thì bỏ
            if mode == 'dup':
                drop_sheets.append(ws.title)
            continue

        data = range(header_row + 1, max_row + 1)
        body = [r for r in data if (r not in dups if mode == 'clean' else r in dups)]
        if mode == 'dup' and not body:
            drop_sheets.append(ws.title)
            continue
        keep = list(range(1, header_row + 1)) + body
        stt_col = _detect_stt_col(meta) if renumber_stt else 0
        _compact_sheet(ws, keep, phone_col=phone_col, header_row=header_row, stt_col=stt_col,
                       normalize_phones=normalize_phones)
        if update_total_label and header_row:
            _update_total_label(ws, header_row, len(body), ws.max_column or 1)
        stats[ws.title] = len(body)

    for title in drop_sheets:
        wb.remove(wb[title])
    if not wb.worksheets:
        ws = wb.create_sheet('KHONG_CO_DONG_TRUNG')
        ws['A1'] = 'Không có dòng nào phù hợp để xuất.'
        ws.column_dimensions['A'].width = 60
    if with_report and mode == 'dup':
        _add_report_sheet(wb, result, folders)

    wb.save(out_path)
    wb.close()
    return out_path, out_name
