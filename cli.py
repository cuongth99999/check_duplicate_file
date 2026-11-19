#!/usr/bin/env python3
"""CLI check trùng SĐT theo thư mục.

Ví dụ:
  python cli.py folders
  python cli.py add "Don hang thang 11" "/duong/dan/*.xlsx"
  python cli.py check file_moi.xlsx -f "Don hang thang 11" -f "Data Lao Cai" --clean --dup
"""
import argparse
import os
import sys

from core import storage
from core.checker import check_file
from core.exporter import export


def cmd_folders(args):
    rows = storage.list_folders()
    if not rows:
        print('Chưa có thư mục nào. Tạo bằng: python cli.py add "<tên thư mục>" file.xlsx')
        return
    print(f'{"THƯ MỤC":<34}{"FILE":>6}{"SĐT ĐÃ INDEX":>14}{"DUNG LƯỢNG":>14}')
    for r in rows:
        print(f'{r["name"]:<34}{r["file_count"]:>6}{r["phone_count"]:>14,}'
              f'{r["size"]/1048576:>13.1f}M')


def cmd_add(args):
    folder = storage.create_folder(args.folder)
    added = []
    for path in args.files:
        if not os.path.isfile(path):
            print(f'! Bỏ qua (không thấy file): {path}')
            continue
        try:
            name = storage.save_uploaded(folder, os.path.basename(path), path)
            added.append(name)
            print(f'+ {folder}/{name}')
        except ValueError as exc:
            print(f'! {exc}')
    if added:
        print('Đang lập chỉ mục SĐT...')
        _, warn = storage.build_folder_index(folder, progress=lambda m: print('  ' + m))
        for w in warn:
            print('  ! ' + w)


def cmd_reindex(args):
    folders = args.folders or [f['name'] for f in storage.list_folders()]
    for f in folders:
        print(f'== {f}')
        idx, warn = storage.build_folder_index(f, progress=lambda m: print('  ' + m), force=args.force)
        print(f'   {len(idx):,} SĐT duy nhất')
        for w in warn:
            print('   ! ' + w)


def cmd_check(args):
    if not os.path.isfile(args.file):
        sys.exit(f'Không thấy file: {args.file}')
    folders = args.folder or []
    for f in folders:
        if not os.path.isdir(storage.folder_path(f)):
            sys.exit(f'Không thấy thư mục: {f}')
    print(f'Đối chiếu với: {", ".join(folders) or "(không có)"}')
    index, warn = storage.build_index(folders, progress=lambda m: print('  ' + m))
    for w in warn:
        print('  ! ' + w)
    print(f'  Chỉ mục: {len(index):,} SĐT duy nhất')

    result = check_file(args.file, index, include_self=not args.no_self)
    s = result['summary']
    print('\n================ KẾT QUẢ ================')
    print(f'File            : {os.path.basename(args.file)}')
    print(f'Tổng dòng có SĐT: {s["total_rows"]:,}')
    print(f'Trùng thư mục   : {s["dup_folder_rows"]:,} dòng ({s["dup_unique_phones"]:,} SĐT)')
    print(f'Trùng nội bộ    : {s["dup_self_rows"]:,} dòng')
    print(f'Tổng trùng      : {s["dup_total_rows"]:,} dòng')
    print(f'Còn lại         : {s["clean_rows"]:,} dòng')
    for sh in result['sheets']:
        print(f'  - sheet "{sh["name"]}": tiêu đề dòng {sh["header_row"]}, '
              f'cột SĐT {sh["phone_col"]}, trùng {sh["dup_folder"]}+{sh["dup_self"]}')
    if result['rows']:
        print('\n--- Chi tiết (20 dòng đầu) ---')
        for item in result['rows'][:20]:
            where = '; '.join(f'{m["folder"]}/{m["file"]}:{m["sheet"]}!{m["row"]}'
                              f'{" (" + m["name"] + ")" if m["name"] else ""}'
                              for m in item['matches'])
            print(f'  {item["sheet"]}!{item["row"]:<6} {item["phone"]:<13} '
                  f'{(item["name"] or "")[:26]:<28} {item["kind"]:<12} {where}')
        if len(result['rows']) > 20:
            print(f'  ... còn {len(result["rows"]) - 20} dòng nữa')

    for mode, flag in (('clean', args.clean), ('dup', args.dup), ('report', args.report)):
        if not flag:
            continue
        path, name = export(args.file, result, mode, folders, filename=args.name,
                            renumber_stt=not args.no_renumber,
                            normalize_phones=args.normalize_phones)
        print(f'>> Đã xuất [{mode}]: {path}')

    if args.save_to:
        name = storage.save_uploaded(args.save_to, os.path.basename(args.file), args.file)
        storage.build_folder_index(args.save_to)
        print(f'>> Đã lưu file vào thư mục: {args.save_to}/{name}')


def main():
    ap = argparse.ArgumentParser(description='Check trùng số điện thoại theo thư mục')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('folders', help='Liệt kê thư mục')
    p.set_defaults(func=cmd_folders)

    p = sub.add_parser('add', help='Thêm file cũ vào thư mục')
    p.add_argument('folder')
    p.add_argument('files', nargs='+')
    p.set_defaults(func=cmd_add)

    p = sub.add_parser('reindex', help='Lập lại chỉ mục SĐT')
    p.add_argument('folders', nargs='*')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_reindex)

    p = sub.add_parser('check', help='Check trùng cho 1 file mới')
    p.add_argument('file')
    p.add_argument('-f', '--folder', action='append', help='Thư mục đối chiếu (lặp nhiều lần)')
    p.add_argument('--clean', action='store_true', help='Xuất file đã loại trùng')
    p.add_argument('--dup', action='store_true', help='Xuất file chỉ chứa dòng trùng')
    p.add_argument('--report', action='store_true', help='Xuất riêng file báo cáo')
    p.add_argument('--name', help='Tên file xuất (không đặt thì tự gen)')
    p.add_argument('--no-self', action='store_true', help='Bỏ qua trùng nội bộ trong file mới')
    p.add_argument('--no-renumber', action='store_true', help='Không đánh lại STT')
    p.add_argument('--normalize-phones', action='store_true',
                   help='Chuẩn hoá SĐT về dạng 0xxxxxxxxx khi xuất')
    p.add_argument('--save-to', help='Lưu file này vào thư mục sau khi check')
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
