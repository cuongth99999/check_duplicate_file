#!/usr/bin/env python3
"""Web tool check trùng số điện thoại theo thư mục."""
import os
import shutil
import time
import uuid

from flask import (Flask, abort, jsonify, render_template, request,
                   send_file, send_from_directory)

from core import storage
from core.checker import check_file
from core.exporter import auto_filename, export
from core.reader import SUPPORTED_EXT

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024        # 512MB / lượt upload
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0                 # không cache css/js cũ
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.json.ensure_ascii = False

CHECKS = {}                 # token -> phiên kiểm tra
MAX_ROWS_JSON = 3000        # số dòng trùng trả về cho giao diện
SESSION_TTL = 12 * 3600


# ------------------------------------------------------------------ tiện ích

def _dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(root, fn))
            except OSError:
                pass
    return total


def _cleanup(drop_all=False):
    """Dọn file tạm trong uploads/ và exports/.

    drop_all=True (lúc khởi động hoặc bấm nút dọn): xoá hết, không cần chờ hết hạn.
    Phiên kiểm tra nằm trong RAM nên sau khi restart, file tạm cũ là vô dụng.
    """
    now = time.time()
    freed = 0

    for token in list(CHECKS):
        if drop_all or now - CHECKS[token]['created'] > SESSION_TTL:
            CHECKS.pop(token, None)

    for base in (storage.UPLOAD_DIR, storage.EXPORT_DIR):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if not os.path.isdir(path) or name in CHECKS:
                continue
            try:
                expired = now - os.path.getmtime(path) > SESSION_TTL
            except OSError:
                expired = True
            if drop_all or expired:
                freed += _dir_size(path)
                shutil.rmtree(path, ignore_errors=True)
    return freed


def _fail(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code


def _public(result):
    """Gọt kết quả để trả về JSON."""
    rows = result['rows']
    return {
        'sheets': result['sheets'],
        'summary': result['summary'],
        'rows': rows[:MAX_ROWS_JSON],
        'rows_total': len(rows),
        'rows_truncated': len(rows) > MAX_ROWS_JSON,
    }


def _session(token):
    sess = CHECKS.get(token)
    if not sess:
        abort(404, 'Phiên kiểm tra đã hết hạn, vui lòng kiểm tra lại')
    return sess


def _entry(sess, file_id):
    for item in sess['files']:
        if item['id'] == file_id:
            return item
    abort(404, 'Không tìm thấy file trong phiên')


# ------------------------------------------------------------------ giao diện

@app.get('/')
def index():
    return render_template('index.html')


@app.get('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)


# ------------------------------------------------------------------ API thư mục

@app.get('/api/folders')
def api_folders():
    return jsonify({'ok': True, 'folders': storage.list_folders()})


@app.get('/api/folders/<folder>/files')
def api_folder_files(folder):
    return jsonify({'ok': True, 'files': storage.list_files(folder)})


@app.post('/api/folders')
def api_create_folder():
    name = (request.json or {}).get('name', '').strip()
    if not name:
        return _fail('Vui lòng nhập tên thư mục')
    created = storage.create_folder(name)
    return jsonify({'ok': True, 'name': created})


@app.post('/api/folders/<folder>/rename')
def api_rename_folder(folder):
    new = (request.json or {}).get('name', '').strip()
    if not new:
        return _fail('Vui lòng nhập tên mới')
    try:
        return jsonify({'ok': True, 'name': storage.rename_folder(folder, new)})
    except ValueError as exc:
        return _fail(str(exc))


@app.delete('/api/folders/<folder>')
def api_delete_folder(folder):
    storage.delete_folder(folder)
    return jsonify({'ok': True})


@app.post('/api/folders/<folder>/files')
def api_upload_to_folder(folder):
    files = request.files.getlist('files')
    if not files:
        return _fail('Chưa chọn file nào')
    storage.create_folder(folder)
    added, errors = [], []
    for fs in files:
        if not fs or not fs.filename:
            continue
        try:
            added.append(storage.save_uploaded(folder, fs.filename, fs))
        except ValueError as exc:
            errors.append(str(exc))
    _, warn = storage.build_folder_index(folder)
    return jsonify({'ok': True, 'added': added, 'errors': errors + warn,
                    'folders': storage.list_folders()})


@app.delete('/api/folders/<folder>/files/<path:filename>')
def api_delete_file(folder, filename):
    try:
        storage.delete_file(folder, filename)
    except ValueError as exc:
        return _fail(str(exc))
    storage.build_folder_index(folder)
    return jsonify({'ok': True, 'folders': storage.list_folders()})


@app.post('/api/folders/<folder>/reindex')
def api_reindex(folder):
    index, warn = storage.build_folder_index(folder, force=True)
    return jsonify({'ok': True, 'unique_phones': len(index), 'warnings': warn,
                    'folders': storage.list_folders()})


# ------------------------------------------------------------------ API check

@app.get('/api/temp-usage')
def api_temp_usage():
    size = _dir_size(storage.UPLOAD_DIR) + _dir_size(storage.EXPORT_DIR)
    sessions = sum(1 for base in (storage.UPLOAD_DIR, storage.EXPORT_DIR)
                   if os.path.isdir(base)
                   for name in os.listdir(base)
                   if os.path.isdir(os.path.join(base, name)))
    return jsonify({'ok': True, 'size': size, 'items': sessions, 'active': len(CHECKS)})


@app.post('/api/cleanup')
def api_cleanup():
    freed = _cleanup(drop_all=True)
    return jsonify({'ok': True, 'freed': freed})


@app.post('/api/check')
def api_check():
    _cleanup()
    files = [f for f in request.files.getlist('files') if f and f.filename]
    if not files:
        return _fail('Chưa chọn file cần kiểm tra')
    folders = [f for f in request.form.getlist('folders') if f]
    include_self = request.form.get('include_self', '1') == '1'

    for folder in folders:
        if not os.path.isdir(storage.folder_path(folder)):
            return _fail(f'Không tìm thấy thư mục: {folder}')

    try:
        index, warnings = storage.build_index(folders)
    except Exception as exc:                                       # noqa: BLE001
        return _fail(f'Lỗi khi lập chỉ mục: {exc}')

    token = uuid.uuid4().hex[:16]
    workdir = os.path.join(storage.UPLOAD_DIR, token)
    os.makedirs(workdir, exist_ok=True)
    sess = {'token': token, 'created': time.time(), 'folders': folders, 'files': []}

    payload = []
    for i, fs in enumerate(files):
        name = storage.safe_name(os.path.basename(fs.filename), f'file_{i}.xlsx')
        if not name.lower().endswith(SUPPORTED_EXT):
            payload.append({'id': f'f{i}', 'name': name, 'ok': False,
                            'error': f'Chỉ hỗ trợ {", ".join(SUPPORTED_EXT)}'})
            continue
        path = os.path.join(workdir, f'{i}__{name}')
        fs.save(path)
        try:
            result = check_file(path, index, include_self=include_self)
        except Exception as exc:                                   # noqa: BLE001
            payload.append({'id': f'f{i}', 'name': name, 'ok': False,
                            'error': f'Lỗi đọc file: {exc}'})
            continue
        if not any(s['phone_col'] for s in result['sheets']):
            payload.append({'id': f'f{i}', 'name': name, 'ok': False,
                            'error': 'Không tìm thấy cột số điện thoại trong file'})
            continue
        result['file'] = name                        # tên gốc (bỏ tiền tố chống trùng)
        entry = {'id': f'f{i}', 'name': name, 'path': path, 'result': result}
        sess['files'].append(entry)
        payload.append(dict({'id': entry['id'], 'name': name, 'ok': True}, **_public(result)))

    CHECKS[token] = sess
    return jsonify({'ok': True, 'token': token, 'folders': folders,
                    'index_size': len(index), 'warnings': warnings, 'files': payload})


@app.post('/api/export')
def api_export():
    data = request.json or {}
    sess = _session(data.get('token'))
    entry = _entry(sess, data.get('file_id'))
    mode = data.get('mode')
    if mode not in ('clean', 'dup', 'report'):
        return _fail('Loại file xuất không hợp lệ')
    try:
        out_path, out_name = export(
            entry['path'], entry['result'], mode, sess['folders'],
            filename=(data.get('filename') or '').strip() or auto_filename(entry['name'], mode),
            renumber_stt=bool(data.get('renumber_stt', True)),
            with_report=bool(data.get('with_report', True)),
            update_total_label=bool(data.get('update_total_label', True)),
            normalize_phones=bool(data.get('normalize_phones', False)),
            out_dir=os.path.join(storage.EXPORT_DIR, sess['token']),
        )
    except Exception as exc:                                       # noqa: BLE001
        return _fail(f'Lỗi khi xuất file: {exc}', 500)
    return jsonify({'ok': True, 'name': out_name, 'size': os.path.getsize(out_path),
                    'url': f'/download/{sess["token"]}/{out_name}'})


@app.get('/api/export-name')
def api_export_name():
    src = request.args.get('name', 'file.xlsx')
    mode = request.args.get('mode', 'clean')
    if mode not in ('clean', 'dup', 'report'):
        mode = 'clean'
    return jsonify({'ok': True, 'name': auto_filename(src, mode)})


@app.get('/download/<token>/<path:name>')
def download(token, name):
    folder = os.path.realpath(os.path.join(storage.EXPORT_DIR, token))
    path = os.path.realpath(os.path.join(folder, os.path.basename(name)))
    if not path.startswith(folder + os.sep) or not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.post('/api/save-to-folder')
def api_save_to_folder():
    data = request.json or {}
    sess = _session(data.get('token'))
    entry = _entry(sess, data.get('file_id'))
    folder = (data.get('folder') or '').strip()
    if not folder:
        return _fail('Chưa chọn thư mục để lưu')
    source = data.get('source') or 'original'
    if source not in ('original', 'clean', 'dup'):
        return _fail('Loại file cần lưu không hợp lệ')

    if source == 'original':
        src_path, src_name = entry['path'], entry['name']
    else:
        try:
            src_path, src_name = export(
                entry['path'], entry['result'], source, sess['folders'],
                filename=(data.get('filename') or '').strip()
                         or auto_filename(entry['name'], source),
                renumber_stt=bool(data.get('renumber_stt', True)),
                update_total_label=bool(data.get('update_total_label', True)),
                normalize_phones=bool(data.get('normalize_phones', False)),
                out_dir=os.path.join(storage.EXPORT_DIR, sess['token']),
            )
        except Exception as exc:                                   # noqa: BLE001
            return _fail(f'Lỗi khi tạo file để lưu: {exc}', 500)

    storage.create_folder(folder)
    saved = storage.save_uploaded(folder, src_name, src_path)
    _, warn = storage.build_folder_index(folder)
    return jsonify({'ok': True, 'saved': saved, 'folder': folder, 'source': source,
                    'warnings': warn, 'folders': storage.list_folders()})


@app.errorhandler(404)
def handle_404(exc):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': getattr(exc, 'description', 'Không tìm thấy')}), 404
    return exc, 404


@app.errorhandler(413)
def handle_413(exc):
    return _fail('File quá lớn (giới hạn 512MB mỗi lượt upload)', 413)


if __name__ == '__main__':
    _freed = _cleanup(drop_all=True)
    if _freed:
        print(f'>> Đã dọn {_freed / 1048576:.1f} MB file tạm của phiên trước')
    port = int(os.environ.get('PORT', 8686))
    print(f'>> Mở trình duyệt: http://127.0.0.1:{port}')
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=port, threaded=True, debug=False)
