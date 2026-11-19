"""So trùng SĐT giữa file mới và chỉ mục các thư mục đã lưu."""
from .reader import inspect_workbook, iter_phone_rows

MAX_MATCH_DETAIL = 5        # số nơi trùng hiển thị tối đa cho mỗi dòng


def check_file(path, index, layouts=None, include_self=True):
    """Kết quả so trùng cho 1 file mới.

    index    : {phone_key: [hit, ...]} từ storage.build_index
    layouts  : {sheet_name: (header_row, phone_col, name_col)} ghi đè tự dò
    """
    sheets = inspect_workbook(path)
    sheet_map = {s.name: s for s in sheets}

    rows = []           # mọi dòng có SĐT
    seen_in_sheet = {}  # (sheet, key) -> dòng đầu tiên gặp
    for sheet, row, key, disp, name in iter_phone_rows(path, layouts=layouts):
        rows.append({'sheet': sheet, 'row': row, 'key': key, 'phone': disp, 'name': name})

    results = []
    dup_folder_rows = {}    # sheet -> set(row) trùng với thư mục
    dup_self_rows = {}      # sheet -> set(row) trùng nội bộ trong cùng sheet
    phones_hit = set()
    row_keys_seen = set()

    for item in rows:
        sheet, row, key = item['sheet'], item['row'], item['key']
        hits = index.get(key) or []
        self_first = seen_in_sheet.get((sheet, key))
        if self_first is None:
            seen_in_sheet[(sheet, key)] = row

        kinds = []
        if hits:
            kinds.append('folder')
            dup_folder_rows.setdefault(sheet, set()).add(row)
            phones_hit.add(key)
        if include_self and self_first is not None and self_first != row:
            kinds.append('self')
            dup_self_rows.setdefault(sheet, set()).add(row)

        if kinds:
            results.append({
                'sheet': sheet,
                'row': row,
                'phone': item['phone'],
                'name': item['name'],
                'kind': '+'.join(kinds),
                'match_count': len(hits),
                'self_first_row': self_first if 'self' in kinds else None,
                'matches': hits[:MAX_MATCH_DETAIL],
            })
        row_keys_seen.add((sheet, row))

    total_rows = len(row_keys_seen)
    dup_folder_count = sum(len(v) for v in dup_folder_rows.values())
    dup_self_count = sum(len(v) for v in dup_self_rows.values())
    all_dup = {s: set(dup_folder_rows.get(s, set())) | set(dup_self_rows.get(s, set()))
               for s in set(dup_folder_rows) | set(dup_self_rows)}

    return {
        'file': path,
        'sheets': [{
            'name': s.name,
            'header_row': (layouts or {}).get(s.name, (s.header_row, s.phone_col, s.name_col))[0],
            'phone_col': (layouts or {}).get(s.name, (s.header_row, s.phone_col, s.name_col))[1],
            'name_col': (layouts or {}).get(s.name, (s.header_row, s.phone_col, s.name_col))[2],
            'headers': s.headers,
            'max_row': s.max_row,
            'max_col': s.max_col,
            'dup_folder': len(dup_folder_rows.get(s.name, ())),
            'dup_self': len(dup_self_rows.get(s.name, ())),
        } for s in sheets],
        'rows': results,
        'dup_folder_rows': {k: sorted(v) for k, v in dup_folder_rows.items()},
        'dup_self_rows': {k: sorted(v) for k, v in dup_self_rows.items()},
        'dup_rows': {k: sorted(v) for k, v in all_dup.items()},
        'summary': {
            'total_rows': total_rows,
            'dup_folder_rows': dup_folder_count,
            'dup_self_rows': dup_self_count,
            'dup_total_rows': sum(len(v) for v in all_dup.values()),
            'dup_unique_phones': len(phones_hit),
            'clean_rows': total_rows - sum(len(v) for v in all_dup.values()),
        },
        '_sheet_map': sheet_map,
    }
