"""Quản lý thư mục lưu trữ file cũ + cache chỉ mục SĐT."""
import json
import os
import re
import shutil
import time
import unicodedata

from .reader import SUPPORTED_EXT, inspect_workbook, iter_phone_rows

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
FOLDERS_DIR = os.path.join(DATA_DIR, 'folders')
CACHE_DIR = os.path.join(DATA_DIR, 'cache')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')

for d in (FOLDERS_DIR, CACHE_DIR, UPLOAD_DIR, EXPORT_DIR):
    os.makedirs(d, exist_ok=True)

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(name, fallback='khong_ten'):
    """Giữ nguyên tiếng Việt, chỉ bỏ ký tự không hợp lệ cho tên file/thư mục."""
    name = unicodedata.normalize('NFC', str(name or '')).strip()
    name = _BAD.sub('_', name).strip(' .')
    name = re.sub(r'\s+', ' ', name)
    return name[:120] or fallback


def folder_path(folder):
    name = safe_name(folder)
    path = os.path.realpath(os.path.join(FOLDERS_DIR, name))
    if not path.startswith(os.path.realpath(FOLDERS_DIR) + os.sep):
        raise ValueError('Tên thư mục không hợp lệ')
    return path


def create_folder(folder):
    path = folder_path(folder)
    os.makedirs(path, exist_ok=True)
    return os.path.basename(path)


def delete_folder(folder):
    path = folder_path(folder)
    if os.path.isdir(path):
        shutil.rmtree(path)
    cache = _cache_file(os.path.basename(path))
    if os.path.exists(cache):
        os.remove(cache)


def rename_folder(old, new):
    src, dst = folder_path(old), folder_path(new)
    if not os.path.isdir(src):
        raise ValueError('Thư mục không tồn tại')
    if os.path.exists(dst):
        raise ValueError('Tên thư mục mới đã tồn tại')
    os.rename(src, dst)
    old_cache = _cache_file(os.path.basename(src))
    if os.path.exists(old_cache):
        os.rename(old_cache, _cache_file(os.path.basename(dst)))
    return os.path.basename(dst)


def list_files(folder):
    path = folder_path(folder)
    if not os.path.isdir(path):
        return []
    out = []
    for fn in sorted(os.listdir(path)):
        fp = os.path.join(path, fn)
        if not os.path.isfile(fp) or not fn.lower().endswith(SUPPORTED_EXT):
            continue
        st = os.stat(fp)
        out.append({'name': fn, 'size': st.st_size, 'mtime': st.st_mtime})
    return out


def list_folders():
    if not os.path.isdir(FOLDERS_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(FOLDERS_DIR)):
        if not os.path.isdir(os.path.join(FOLDERS_DIR, fn)):
            continue
        files = list_files(fn)
        cache = _load_cache(fn)
        phones = 0
        for meta in cache.get('files', {}).values():
            phones += meta.get('phone_count', 0)
        out.append({
            'name': fn,
            'file_count': len(files),
            'size': sum(f['size'] for f in files),
            'phone_count': phones,
            'indexed': len(cache.get('files', {})),
        })
    return out


def save_uploaded(folder, filename, stream):
    """Lưu file vào thư mục, tự thêm hậu tố nếu trùng tên."""
    path = folder_path(folder)
    os.makedirs(path, exist_ok=True)
    fn = safe_name(os.path.basename(filename), 'file.xlsx')
    base, ext = os.path.splitext(fn)
    if ext.lower() not in SUPPORTED_EXT:
        raise ValueError(f'Chỉ nhận file {", ".join(SUPPORTED_EXT)} - bỏ qua: {fn}')
    target = os.path.join(path, fn)
    i = 1
    while os.path.exists(target):
        target = os.path.join(path, f'{base}__{i}{ext}')
        i += 1
    if hasattr(stream, 'save'):
        stream.save(target)
    elif isinstance(stream, (str, bytes)) and os.path.isfile(stream):
        shutil.copy2(stream, target)
    else:
        with open(target, 'wb') as fh:
            shutil.copyfileobj(stream, fh)
    return os.path.basename(target)


def delete_file(folder, filename):
    path = folder_path(folder)
    fp = os.path.realpath(os.path.join(path, os.path.basename(filename)))
    if not fp.startswith(path + os.sep):
        raise ValueError('Đường dẫn không hợp lệ')
    if os.path.isfile(fp):
        os.remove(fp)


# ---------------------------------------------------------------- cache / index

def _cache_file(folder):
    key = safe_name(folder).replace(' ', '_')
    return os.path.join(CACHE_DIR, f'{key}.json')


def _load_cache(folder):
    fp = _cache_file(folder)
    if not os.path.exists(fp):
        return {'files': {}}
    try:
        with open(fp, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or 'files' not in data:
            return {'files': {}}
        return data
    except Exception:
        return {'files': {}}


def _save_cache(folder, data):
    fp = _cache_file(folder)
    tmp = fp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, fp)


def build_folder_index(folder, progress=None, force=False):
    """Chỉ mục {phone_key: [{file, sheet, row, name, phone}]} cho 1 thư mục.

    Dùng cache theo (mtime, size); file không đổi thì không đọc lại.
    """
    cache = {'files': {}} if force else _load_cache(folder)
    old_files = cache.get('files', {})
    new_files = {}
    warnings = []
    path = folder_path(folder)

    for info in list_files(folder):
        fn = info['name']
        sig = [round(info['mtime'], 3), info['size']]
        cached = old_files.get(fn)
        if cached and cached.get('sig') == sig and 'phones' in cached:
            new_files[fn] = cached
            continue
        if progress:
            progress(f'Đang đọc {folder}/{fn}')
        fp = os.path.join(path, fn)
        phones = {}
        try:
            sheets = inspect_workbook(fp)
            if not any(s.phone_col for s in sheets):
                warnings.append(f'{folder}/{fn}: không tìm thấy cột SĐT - đã bỏ qua')
            for sheet, row, key, disp, name in iter_phone_rows(fp):
                phones.setdefault(key, []).append([sheet, row, name, disp])
        except Exception as exc:                                  # noqa: BLE001
            warnings.append(f'{folder}/{fn}: lỗi đọc file ({exc})')
            continue
        new_files[fn] = {
            'sig': sig,
            'phone_count': sum(len(v) for v in phones.values()),
            'unique_count': len(phones),
            'phones': phones,
            'built_at': time.time(),
        }

    cache['files'] = new_files
    _save_cache(folder, cache)

    index = {}
    for fn, meta in new_files.items():
        for key, hits in meta.get('phones', {}).items():
            bucket = index.setdefault(key, [])
            for sheet, row, name, disp in hits:
                bucket.append({'folder': folder, 'file': fn, 'sheet': sheet,
                               'row': row, 'name': name, 'phone': disp})
    return index, warnings


def build_index(folders, progress=None, force=False):
    """Gộp chỉ mục của nhiều thư mục."""
    index, warnings = {}, []
    for folder in folders:
        part, warn = build_folder_index(folder, progress=progress, force=force)
        warnings.extend(warn)
        for key, hits in part.items():
            index.setdefault(key, []).extend(hits)
    return index, warnings
