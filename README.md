# Tool check trùng số điện thoại (Excel)

Lưu các file cũ theo **thư mục tự đặt tên** → mỗi ngày upload file mới → tool đối chiếu
**theo số điện thoại** với **một hoặc nhiều thư mục cùng lúc** → báo số dòng trùng, tên
khách trùng, trùng ở file nào, dòng nào → **xuất file Excel mới giữ nguyên 100% format**.

- Tech: **Python 3.12 + Flask + openpyxl** (chạy local, dữ liệu nằm trên máy bạn).

---

## 1. Cài đặt & chạy

Yêu cầu: **Python 3.9+**. Lần chạy đầu `run.sh` sẽ tự tạo môi trường ảo và cài thư viện.

```bash
git clone https://github.com/cuongth99999/check_duplicate_file.git
cd check_duplicate_file
./run.sh
```

Mở trình duyệt: **http://127.0.0.1:8686**
Đổi cổng: `PORT=9000 ./run.sh` · Dừng: `Ctrl + C`

Nếu máy chưa có `python3-venv`:

```bash
sudo apt install python3-venv python3-pip     # Ubuntu/Debian
# hoặc không có quyền sudo:
python3 -m pip install --user virtualenv
```

Cài tay (nếu không dùng `run.sh`):

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

> **Dữ liệu của bạn nằm ở máy bạn.** Thư mục `data/`, `uploads/`, `exports/` đã được
> `.gitignore` loại khỏi git — file Excel khách hàng **không bao giờ** bị đẩy lên repo.

---

## 2. Dùng trên web

**Tab “Thư mục lưu trữ”** — kho file cũ
1. Nhập tên thư mục (tuỳ ý, có dấu tiếng Việt) → **Tạo thư mục**.
2. Bấm **+ Thêm file cũ** để tải lên nhiều file `.xlsx` một lúc.
3. Mỗi thư mục có: *Xem file* (xem/xoá từng file), *Lập lại chỉ mục*, *Đổi tên*, *Xoá*.

**Tab “Kiểm tra trùng”** — việc hằng ngày
1. Tích chọn **một hoặc nhiều thư mục** cần đối chiếu.
2. Kéo thả **file mới** (chọn được nhiều file cùng lúc).
3. Bấm **Kiểm tra trùng** → xem báo cáo:
   - Dòng có SĐT · Trùng với thư mục · Trùng trong chính file · Tổng dòng trùng ·
     SĐT trùng (duy nhất) · Còn lại sau loại trùng.
   - Bảng chi tiết: sheet, dòng, **SĐT**, **tên khách**, loại trùng, và **trùng tại
     thư mục / file / sheet / dòng nào, tên khách bên file cũ là ai**. Có ô tìm kiếm.
4. **Xuất file Excel** (gõ tên file hoặc để trống cho tool tự đặt):
   - `File đã loại trùng` — file gốc đã bỏ các dòng trùng.
   - `File chỉ dòng trùng` — chỉ các dòng trùng + sheet `BAO_CAO_TRUNG`.
   - `Báo cáo trùng` — chỉ bảng báo cáo.
5. **Lưu file này vào thư mục** *(tuỳ chọn — chỉ lưu khi bạn bấm nút, không tự động lưu)*:
   chọn **lưu file nào** (file gốc vừa upload / file đã loại trùng / file chỉ dòng trùng)
   → chọn **thư mục** (hoặc `➕ Tạo thư mục mới…`) → bấm **Lưu vào thư mục**.

6. Kiểm tra xong, muốn làm đợt khác → bấm **↺ Kiểm tra đợt mới** (xoá hết file đã chọn và
   kết quả cũ, giữ nguyên các thư mục đang tích). Hoặc bấm **Xoá hết file đã chọn** nếu chỉ
   muốn bỏ danh sách file.

> - Nút **xuất file đã loại trùng** nằm ở khung kết quả, chỉ hiện ra **sau khi bấm Kiểm tra trùng**.
> - Nút **↻ Tải lại danh sách** chỉ để đọc lại danh sách thư mục + số SĐT đã lập chỉ mục
>   (dùng khi vừa thêm/xoá file ở tab *Thư mục lưu trữ*). Nó **không** chạy kiểm tra trùng.

---

## 3. Cam kết về file xuất ra

| Yêu cầu | Cách tool xử lý |
|---|---|
| Giữ đúng format cột của file gốc | Mở chính file gốc rồi dồn dòng, **không tạo file mới copy qua** → font, màu, viền, merge, freeze, auto-filter giữ nguyên |
| Độ rộng cột không bị co dúm | Giữ nguyên `column_dimensions` + khổ sheet mặc định của file gốc |
| Không lệch dòng, đúng khách nào thông tin khách đó | Copy nguyên vẹn **cả dòng** theo chỉ số dòng gốc, không ghép/ sắp xếp lại |
| SĐT giữ số 0 ở đầu | Ô SĐT luôn ghi dạng **chuỗi + định dạng Text (`@`)**; số lưu kiểu number bị mất số 0 sẽ được khôi phục (`975805564` → `0975805564`) |
| Nhiều sheet | Xử lý **từng sheet**, giữ nguyên toàn bộ sheet trong file |

Tuỳ chọn thêm (ở tab Kiểm tra trùng):
- *Đánh lại cột STT khi xuất file* — đánh số lại 1,2,3… sau khi bỏ dòng trùng.
- *Cập nhật nhãn “Tổng số: … dòng”* — sửa lại con số ở dòng tiêu đề cho khớp.
- *Chuẩn hoá SĐT về dạng 0xxxxxxxxx* — mặc định **tắt** để không làm sai lệch dữ liệu gốc.

---

## 4. Cách nhận diện & so khớp SĐT

- Tự dò **dòng tiêu đề** và **cột SĐT** cho từng sheet (nhận: `Số điện thoại`, `SDT`,
  `Điện thoại`, `Phone`, `Mobile`, `Zalo`…). Không có tiêu đề thì dò theo nội dung cột.
- Tự dò cột **tên khách** (`Khách hàng`, `Họ và tên`, `Tên`, `Name`…) để báo cáo.
- So khớp sau khi chuẩn hoá, nên các dạng sau **được coi là cùng một số**:
  `0975805564` · `975805564` (lưu kiểu số, mất số 0) · `0975 805 564` · `0975.805.564` ·
  `+84975805564` · `84975805564`.
- Số CCCD 12 chữ số lọt vào cột SĐT **không** bị khớp nhầm với SĐT 10 số.
- “Trùng trong file” chỉ tính **trong cùng một sheet**, nên file chia nhiều sheet
  (TỔNG HỢP + từng tỉnh) không bị báo trùng oan.

---

## 5. Dùng bằng dòng lệnh (tuỳ chọn)

```bash
# Liệt kê thư mục
./venv/bin/python cli.py folders

# Thêm file cũ vào thư mục
./venv/bin/python cli.py add "Đơn hàng tháng 11" /duong/dan/*.xlsx

# Check trùng + xuất file
./venv/bin/python cli.py check file_moi.xlsx \
    -f "Đơn hàng tháng 11" -f "Data nguồn" \
    --clean --dup --name "don_hang_19_11_sach"

# Các cờ khác: --report, --no-self, --no-renumber, --normalize-phones,
#              --save-to "Đơn hàng tháng 11"
```

---

## 6. Cấu trúc thư mục

```
check_duplicate_file/
├── app.py              # web server (Flask)
├── cli.py              # bản dòng lệnh
├── run.sh              # script khởi động
├── core/
│   ├── phones.py       # chuẩn hoá SĐT Việt Nam
│   ├── reader.py       # đọc Excel, tự dò tiêu đề / cột SĐT / cột tên
│   ├── storage.py      # quản lý thư mục + cache chỉ mục SĐT
│   ├── checker.py      # logic so trùng
│   └── exporter.py     # xuất Excel giữ nguyên format
├── templates/, static/ # giao diện web
├── data/folders/       # KHO FILE CŨ (mỗi thư mục = 1 thư mục thật ở đây)
├── data/cache/         # chỉ mục SĐT (tự tạo lại được, xoá cũng không sao)
├── uploads/            # FILE TẠM: file mới vừa upload để kiểm tra
└── exports/            # FILE TẠM: file vừa xuất ra
```

**File tạm (`uploads/`, `exports/`)**: giữ lại trong lúc làm việc để còn xuất file / lưu vào
thư mục sau khi kiểm tra. Chúng **tự xoá sạch mỗi lần khởi động lại tool**, và tự dọn sau 12 giờ
không dùng. Muốn dọn ngay: tab *Thư mục lưu trữ* → mục **File tạm** → **🧹 Dọn ngay**.
Xoá tay cũng được, không ảnh hưởng gì.

Muốn sao lưu toàn bộ kho dữ liệu: copy thư mục `data/folders/`.
Chỉ mục được cache theo ngày sửa + dung lượng file, nên lần check sau rất nhanh;
nếu sửa file trực tiếp trong `data/folders/` thì bấm **Lập lại chỉ mục**.

---

## 7. Giới hạn

- Hỗ trợ `.xlsx`, `.xlsm`. File `.xls` (Excel 97-2003) cần mở bằng Excel và **Save As .xlsx**.
- Mỗi lượt upload tối đa 512 MB.
- Bảng chi tiết trên web hiển thị tối đa 3.000 dòng trùng; file Excel xuất ra thì đầy đủ.
