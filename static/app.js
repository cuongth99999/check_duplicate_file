/* Check trùng SĐT - giao diện */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const fmt = n => (n == null ? '' : Number(n).toLocaleString('vi-VN'));
const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const mb = b => b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';

let FOLDERS = [];
let PICKED = new Set();
let NEW_FILES = [];
let LAST = null;            // { token, folders, files: [...] }

/* datalist gợi ý tên thư mục cho ô "lưu vào thư mục" */
const FOLDER_DL = document.createElement('datalist');
FOLDER_DL.id = 'folder-list';
document.addEventListener('DOMContentLoaded', () => document.body.appendChild(FOLDER_DL));

/* ------------------------------------------------------------------ helpers */
function toast(msg, bad) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast show' + (bad ? ' bad' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = 'toast'), 4200);
}

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  let data = {};
  try { data = await res.json(); } catch (e) { /* ignore */ }
  if (!res.ok || data.ok === false) throw new Error(data.error || `Lỗi ${res.status}`);
  return data;
}


/* ------------------------------------------------------------------ popup */
const MODAL = {
  mask: null, resolve: null,
  init() {
    this.mask = $('#modal-mask');
    $('#modal-cancel').addEventListener('click', () => this.close(null));
    $('#modal-ok').addEventListener('click', () => this.submit());
    this.mask.addEventListener('mousedown', e => { if (e.target === this.mask) this.close(null); });
    document.addEventListener('keydown', e => {
      if (!this.mask.classList.contains('show')) return;
      if (e.key === 'Escape') this.close(null);
      if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); this.submit(); }
    });
  },
  submit() {
    const input = $('#modal-field input, #modal-field select');
    if (input) {
      const v = input.value.trim();
      if (!v) { input.focus(); input.style.borderColor = 'var(--bad)'; return; }
      this.close(v);
    } else this.close(true);
  },
  close(val) {
    this.mask.classList.remove('show');
    const r = this.resolve; this.resolve = null;
    if (r) r(val);
  },
  open({ title, text = '', icon = '?', danger = false, field = null, ok = 'Đồng ý', cancel = 'Huỷ' }) {
    $('#modal-title').textContent = title;
    $('#modal-text').innerHTML = text;
    $('#modal-text').style.display = text ? '' : 'none';
    const ic = $('#modal-icon');
    ic.textContent = icon;
    ic.className = 'modal-icon' + (danger ? ' danger' : '');
    $('#modal-field').innerHTML = field || '';
    $('#modal-ok').textContent = ok;
    $('#modal-ok').className = 'btn ' + (danger ? 'danger' : 'primary');
    $('#modal-cancel').textContent = cancel;
    this.mask.classList.add('show');
    setTimeout(() => {
      const el = $('#modal-field input, #modal-field select');
      if (el) { el.focus(); if (el.select) el.select(); }
    }, 60);
    return new Promise(res => (this.resolve = res));
  },
};

const askText = (title, value = '', text = '', placeholder = '') => MODAL.open({
  title, text, icon: '✎',
  field: `<input type="text" value="${esc(value)}" placeholder="${esc(placeholder)}">`,
  ok: 'Xác nhận',
});
const askConfirm = (title, text = '', danger = true, ok = 'Xoá') =>
  MODAL.open({ title, text, icon: danger ? '⚠' : '?', danger, ok });

/* ------------------------------------------------------------------ tabs */
$$('.tab').forEach(btn => btn.addEventListener('click', () => {
  $$('.tab').forEach(b => b.classList.toggle('active', b === btn));
  $$('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + btn.dataset.tab));
}));

/* ------------------------------------------------------------------ folders */
async function loadFolders() {
  const data = await api('/api/folders');
  FOLDERS = data.folders;
  PICKED = new Set([...PICKED].filter(n => FOLDERS.some(f => f.name === n)));
  renderPicker();
  renderManager();
}

function renderPicker() {
  FOLDER_DL.innerHTML = FOLDERS.map(f => `<option value="${esc(f.name)}">`).join('');
  const box = $('#folder-picker');
  if (!FOLDERS.length) {
    box.innerHTML = '<p class="muted">Chưa có thư mục nào. Sang tab <b>Thư mục lưu trữ</b> để tạo thư mục và tải file cũ lên.</p>';
    return;
  }
  box.innerHTML = FOLDERS.map(f => `
    <label class="fp-item ${PICKED.has(f.name) ? 'on' : ''}">
      <input type="checkbox" value="${esc(f.name)}" ${PICKED.has(f.name) ? 'checked' : ''}>
      <span>
        <span class="fp-name">${esc(f.name)}</span>
        <span class="fp-meta">${fmt(f.file_count)} file · ${fmt(f.phone_count)} SĐT · ${mb(f.size)}</span>
      </span>
    </label>`).join('');
  $$('#folder-picker input').forEach(cb => cb.addEventListener('change', () => {
    cb.checked ? PICKED.add(cb.value) : PICKED.delete(cb.value);
    cb.closest('.fp-item').classList.toggle('on', cb.checked);
  }));
}

function renderManager() {
  const box = $('#folder-manager');
  if (!FOLDERS.length) { box.innerHTML = '<p class="muted">Chưa có thư mục nào.</p>'; return; }
  box.innerHTML = FOLDERS.map(f => `
    <div class="fm-item" data-folder="${esc(f.name)}">
      <div class="fm-top">
        <div>
          <div class="fm-name">${esc(f.name)}</div>
          <div class="fm-meta">${fmt(f.file_count)} file · ${fmt(f.phone_count)} SĐT đã lập chỉ mục · ${mb(f.size)}</div>
        </div>
        <div class="fm-actions">
          <label class="btn sm primary" style="position:relative;overflow:hidden">
            + Thêm file cũ
            <input type="file" multiple accept=".xlsx,.xlsm" class="fm-upload"
                   style="position:absolute;inset:0;opacity:0;cursor:pointer">
          </label>
          <button class="btn sm ghost act-files">Xem file</button>
          <button class="btn sm ghost act-reindex">Lập lại chỉ mục</button>
          <button class="btn sm ghost act-rename">Đổi tên</button>
          <button class="btn sm danger act-delete">Xoá</button>
        </div>
      </div>
      <div class="fm-files"></div>
    </div>`).join('');

  $$('#folder-manager .fm-item').forEach(item => {
    const folder = item.dataset.folder;
    $('.fm-upload', item).addEventListener('change', async ev => {
      const files = ev.target.files;
      if (!files.length) return;
      const fd = new FormData();
      for (const f of files) fd.append('files', f);
      toast('Đang tải lên & lập chỉ mục…');
      try {
        const r = await api(`/api/folders/${encodeURIComponent(folder)}/files`,
                            { method: 'POST', body: fd });
        toast(`Đã thêm ${r.added.length} file vào "${folder}"`);
        (r.errors || []).forEach(e => toast(e, true));
        await loadFolders();
      } catch (e) { toast(e.message, true); }
      ev.target.value = '';
    });
    $('.act-files', item).addEventListener('click', async () => {
      const box = $('.fm-files', item);
      if (box.classList.contains('open')) { box.classList.remove('open'); return; }
      box.classList.add('open');
      box.innerHTML = '<p class="muted"><span class="spin"></span>Đang tải…</p>';
      const r = await api(`/api/folders/${encodeURIComponent(folder)}/files`);
      box.innerHTML = r.files.length ? `<div class="table-wrap"><table>
        <thead><tr><th>Tên file</th><th class="num">Dung lượng</th><th class="num">Ngày tải lên</th><th style="width:60px"></th></tr></thead>
        <tbody>${r.files.map(f => `<tr>
          <td>${esc(f.name)}</td><td class="num">${mb(f.size)}</td>
          <td class="num">${new Date(f.mtime * 1000).toLocaleString('vi-VN')}</td>
          <td><button class="btn-link rm-file" data-name="${esc(f.name)}" style="color:var(--bad)">Xoá</button></td>
        </tr>`).join('')}</tbody></table></div>`
        : '<p class="muted">Thư mục trống.</p>';
      $$('.rm-file', box).forEach(b => b.addEventListener('click', async () => {
        if (!await askConfirm('Xoá file khỏi thư mục?',
            `<b>${esc(b.dataset.name)}</b><br>trong thư mục <b>${esc(folder)}</b>`)) return;
        await api(`/api/folders/${encodeURIComponent(folder)}/files/${encodeURIComponent(b.dataset.name)}`,
                  { method: 'DELETE' });
        toast('Đã xoá file');
        await loadFolders();
      }));
    });
    $('.act-reindex', item).addEventListener('click', async () => {
      toast('Đang đọc lại toàn bộ file…');
      const r = await api(`/api/folders/${encodeURIComponent(folder)}/reindex`, { method: 'POST' });
      toast(`Đã lập chỉ mục: ${fmt(r.unique_phones)} SĐT duy nhất`);
      (r.warnings || []).forEach(w => toast(w, true));
      await loadFolders();
    });
    $('.act-rename', item).addEventListener('click', async () => {
      const name = await askText('Đổi tên thư mục', folder, `Tên hiện tại: <b>${esc(folder)}</b>`);
      if (!name || name === folder) return;
      try {
        await api(`/api/folders/${encodeURIComponent(folder)}/rename`,
                  { method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name }) });
        toast('Đã đổi tên thư mục');
        await loadFolders();
      } catch (e) { toast(e.message, true); }
    });
    $('.act-delete', item).addEventListener('click', async () => {
      if (!await askConfirm('Xoá cả thư mục?',
            `Thư mục <b>${esc(folder)}</b> và toàn bộ file bên trong sẽ bị xoá vĩnh viễn.`)) return;
      await api(`/api/folders/${encodeURIComponent(folder)}`, { method: 'DELETE' });
      toast('Đã xoá thư mục');
      await loadFolders();
    });
  });
}

$('#btn-create-folder').addEventListener('click', async () => {
  const input = $('#new-folder-name');
  const name = input.value.trim();
  if (!name) return toast('Nhập tên thư mục đã nhé', true);
  try {
    const r = await api('/api/folders', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
    input.value = '';
    toast(`Đã tạo thư mục "${r.name}"`);
    await loadFolders();
  } catch (e) { toast(e.message, true); }
});
$('#new-folder-name').addEventListener('keydown', e => {
  if (e.key === 'Enter') $('#btn-create-folder').click();
});
$('#pick-all').addEventListener('click', () => { PICKED = new Set(FOLDERS.map(f => f.name)); renderPicker(); });
$('#pick-none').addEventListener('click', () => { PICKED = new Set(); renderPicker(); });
/* Tải lại danh sách thư mục - có trạng thái + thông báo để biết đã chạy */
async function reloadFolders(btn) {
  const label = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Đang tải…'; }
  try {
    await loadFolders();
    const phones = FOLDERS.reduce((t, f) => t + f.phone_count, 0);
    const pending = FOLDERS.filter(f => f.file_count > f.indexed);
    toast(`Đã tải lại: ${fmt(FOLDERS.length)} thư mục · ${fmt(phones)} SĐT`);
    if (pending.length) {
      toast(`Có file chưa lập chỉ mục ở: ${pending.map(f => f.name).join(', ')} — bấm "Lập lại chỉ mục"`, true);
    }
  } catch (e) { toast(e.message, true); }
  if (btn) { btn.disabled = false; btn.textContent = label; }
}
$('#reload-folders').addEventListener('click', e => reloadFolders(e.currentTarget));
$('#reload-folders-2').addEventListener('click', e => reloadFolders(e.currentTarget));

/* ------------------------------------------------------------------ chọn file mới */
const dz = $('#dropzone');
$('#new-files').addEventListener('change', e => addFiles(e.target.files));
['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => {
  e.preventDefault(); dz.classList.add('hot');
}));
['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => {
  e.preventDefault(); dz.classList.remove('hot');
}));
dz.addEventListener('drop', e => addFiles(e.dataTransfer.files));

function addFiles(list) {
  for (const f of list) {
    if (!/\.(xlsx|xlsm)$/i.test(f.name)) { toast(`Bỏ qua "${f.name}" (chỉ nhận .xlsx/.xlsm)`, true); continue; }
    if (!NEW_FILES.some(x => x.name === f.name && x.size === f.size)) NEW_FILES.push(f);
  }
  $('#new-files').value = '';
  renderNewFiles();
}

function renderNewFiles() {
  $('#new-file-list').innerHTML = NEW_FILES.map((f, i) =>
    `<li>${esc(f.name)} <span class="muted">${mb(f.size)}</span> <span class="x" data-i="${i}">✕</span></li>`).join('');
  $$('#new-file-list .x').forEach(x => x.addEventListener('click', () => {
    NEW_FILES.splice(+x.dataset.i, 1); renderNewFiles();
  }));
  const bar = $('#new-file-bar');
  bar.style.display = NEW_FILES.length ? 'flex' : 'none';
  $('#new-file-count').textContent =
    `Đã chọn ${fmt(NEW_FILES.length)} file · ${mb(NEW_FILES.reduce((t, f) => t + f.size, 0))}`;
}

/* Dọn sạch để bắt đầu một đợt kiểm tra mới (giữ nguyên thư mục đang chọn) */
function resetRound() {
  NEW_FILES = [];
  LAST = null;
  renderNewFiles();
  $('#results').innerHTML = '';
  $('#check-status').textContent = '';
  $('#btn-reset').style.display = 'none';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
$('#clear-files').addEventListener('click', () => { NEW_FILES = []; renderNewFiles(); });
$('#btn-reset').addEventListener('click', () => {
  resetRound();
  toast('Đã làm mới — chọn file mới để kiểm tra đợt tiếp theo');
});

/* ------------------------------------------------------------------ chạy check */
$('#btn-check').addEventListener('click', async () => {
  if (!NEW_FILES.length) return toast('Chưa chọn file mới cần kiểm tra', true);
  if (!PICKED.size && !await askConfirm('Chưa chọn thư mục đối chiếu',
        'Tool sẽ chỉ kiểm tra SĐT trùng lặp <b>trong chính file mới</b>. Tiếp tục?', false, 'Tiếp tục')) return;

  const btn = $('#btn-check');
  btn.disabled = true;
  $('#check-status').innerHTML = '<span class="spin"></span>Đang đọc dữ liệu & đối chiếu…';
  const fd = new FormData();
  NEW_FILES.forEach(f => fd.append('files', f));
  [...PICKED].forEach(f => fd.append('folders', f));
  fd.append('include_self', $('#opt-self').checked ? '1' : '0');

  try {
    const t0 = performance.now();
    const data = await api('/api/check', { method: 'POST', body: fd });
    LAST = data;
    refreshTempUsage();
    $('#btn-reset').style.display = '';
    $('#check-status').textContent =
      `Xong trong ${((performance.now() - t0) / 1000).toFixed(1)}s · chỉ mục ${fmt(data.index_size)} SĐT`;
    renderResults(data);
  } catch (e) {
    $('#check-status').textContent = '';
    toast(e.message, true);
  } finally { btn.disabled = false; }
});

function kindPill(kind) {
  if (kind === 'folder') return '<span class="pill folder">Trùng thư mục</span>';
  if (kind === 'self') return '<span class="pill self">Trùng trong file</span>';
  return '<span class="pill both">Thư mục + trong file</span>';
}

function renderResults(data) {
  const wrap = $('#results');
  const warn = (data.warnings || []).length
    ? `<div class="warn-box"><b>Lưu ý khi đọc thư mục:</b><br>${data.warnings.map(esc).join('<br>')}</div>` : '';
  wrap.innerHTML = warn + data.files.map(f => f.ok ? fileCard(f, data) : `
    <div class="card"><div class="res-head"><h3>${esc(f.name)}</h3></div>
    <div class="err-box">${esc(f.error)}</div></div>`).join('');

  data.files.filter(f => f.ok).forEach(f => bindCard(f, data));
}

function fileCard(f, data) {
  const s = f.summary;
  const rows = f.rows.map(r => `
    <tr data-q="${esc((r.phone + ' ' + (r.name || '') + ' ' + r.sheet).toLowerCase())}">
      <td>${esc(r.sheet)}</td>
      <td class="num">${r.row}</td>
      <td class="phone">${esc(r.phone)}</td>
      <td>${esc(r.name)}</td>
      <td>${kindPill(r.kind)}</td>
      <td class="where">${(r.matches || []).map(m =>
        `<div><b>${esc(m.folder)}</b> / ${esc(m.file)} — <i>${esc(m.sheet)}</i> dòng ${m.row}${
          m.name ? ' · ' + esc(m.name) : ''}</div>`).join('')
        || (r.self_first_row ? `<div>Trùng với dòng ${r.self_first_row} trong chính file này</div>` : '')}
      </td>
    </tr>`).join('');

  return `
  <div class="card" data-file="${esc(f.id)}">
    <div class="res-head">
      <h3>📄 ${esc(f.name)}</h3>
      <span class="muted">Đối chiếu: ${data.folders.length ? data.folders.map(esc).join(', ') : '(không chọn thư mục)'}</span>
    </div>
    <div class="stats">
      <div class="stat"><b>${fmt(s.total_rows)}</b><span>Dòng có SĐT</span></div>
      <div class="stat bad"><b>${fmt(s.dup_folder_rows)}</b><span>Trùng với thư mục</span></div>
      <div class="stat warn"><b>${fmt(s.dup_self_rows)}</b><span>Trùng trong file</span></div>
      <div class="stat bad"><b>${fmt(s.dup_total_rows)}</b><span>Tổng dòng trùng</span></div>
      <div class="stat"><b>${fmt(s.dup_unique_phones)}</b><span>SĐT trùng (duy nhất)</span></div>
      <div class="stat ok"><b>${fmt(s.clean_rows)}</b><span>Còn lại sau loại trùng</span></div>
    </div>
    <div class="sheet-line">${sheetSummary(f.sheets)}</div>

    ${f.rows_total ? `
    <div class="search-row">
      <input type="search" class="filter" placeholder="Tìm trong danh sách trùng: SĐT, tên khách…">
      <span class="muted count">${fmt(f.rows_total)} dòng trùng${f.rows_truncated ? ` (hiển thị ${fmt(f.rows.length)} dòng đầu)` : ''}</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Sheet</th><th>Dòng</th><th>Số điện thoại</th><th>Tên khách</th><th>Loại</th><th>Trùng tại</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>` : '<div class="ok-box">✓ Không có SĐT nào bị trùng</div>'}

    <div class="export-box">
      <b>Xuất file Excel</b> <span class="muted">(giữ nguyên format, độ rộng cột và số 0 đầu SĐT)</span>
      <div class="export-row">
        <input type="text" class="exp-name" placeholder="Tên file xuất (bỏ trống = tự đặt tên)">
        <button class="btn primary sm exp" data-mode="clean">⬇ File đã loại trùng (${fmt(s.clean_rows)} dòng)</button>
        <button class="btn sm exp" data-mode="dup">⬇ File chỉ dòng trùng (${fmt(s.dup_total_rows)} dòng)</button>
        <button class="btn sm exp" data-mode="report">⬇ Báo cáo trùng</button>
      </div>
      <ul class="dl-list"></ul>
    </div>

    <div class="export-box">
      <b>Lưu file này vào thư mục</b>
      <span class="muted">(tuỳ chọn — chỉ lưu khi bạn bấm nút, để mai đối chiếu tiếp)</span>
      <div class="export-row">
        <select class="save-what">
          <option value="original">File gốc vừa upload (${fmt(s.total_rows)} dòng)</option>
          <option value="clean">File đã loại trùng (${fmt(s.clean_rows)} dòng)</option>
          <option value="dup">File chỉ dòng trùng (${fmt(s.dup_total_rows)} dòng)</option>
        </select>
        <select class="save-folder">
          <option value="">— Chọn thư mục để lưu —</option>
          ${FOLDERS.map(x => `<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('')}
          <option value="__new__">➕ Tạo thư mục mới…</option>
        </select>
        <button class="btn sm ghost save-btn">💾 Lưu vào thư mục</button>
        <span class="muted save-note"></span>
      </div>
    </div>
  </div>`;
}


/* Mô tả cấu trúc đã nhận diện - gom nhóm cho gọn khi file nhiều sheet */
function sheetSummary(sheets) {
  const withPhone = sheets.filter(s => s.phone_col);
  const without = sheets.filter(s => !s.phone_col).map(s => s.name);
  const parts = [];

  if (!withPhone.length) {
    parts.push('<b>Không nhận diện được cột số điện thoại</b>');
  } else {
    const groups = {};
    withPhone.forEach(s => {
      const key = `${s.header_row}|${s.phone_col}|${s.headers[s.phone_col - 1] || ''}`;
      (groups[key] = groups[key] || []).push(s);
    });
    Object.values(groups).forEach(g => {
      const s = g[0];
      const label = esc(String(s.headers[s.phone_col - 1] || '').trim());
      const who = g.length === 1 ? `Sheet <b>${esc(s.name)}</b>`
                                 : `${g.length} sheet (${g.slice(0, 3).map(x => esc(x.name)).join(', ')}${g.length > 3 ? '…' : ''})`;
      parts.push(`${who}: tiêu đề dòng ${s.header_row || '–'}, cột SĐT <b>${colLetter(s.phone_col)}</b>${label ? ` (${label})` : ''}`);
    });
    const hit = withPhone.filter(s => s.dup_folder + s.dup_self > 0);
    if (hit.length) {
      parts.push('Sheet có trùng: ' + hit.map(s =>
        `<b>${esc(s.name)}</b> (${fmt(s.dup_folder + s.dup_self)})`).join(', '));
    }
  }
  if (without.length) {
    parts.push(`Bỏ qua ${without.length} sheet không có cột SĐT (${without.slice(0, 3).map(esc).join(', ')}${without.length > 3 ? '…' : ''})`);
  }
  return parts.join(' · ');
}

function colLetter(n) {
  let s = '';
  while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = (n - m - 1) / 26; }
  return s;
}

function bindCard(f, data) {
  const card = $(`.card[data-file="${f.id}"]`);
  const filter = $('.filter', card);
  if (filter) filter.addEventListener('input', () => {
    const q = filter.value.trim().toLowerCase();
    let shown = 0;
    $$('tbody tr', card).forEach(tr => {
      const hit = !q || tr.dataset.q.includes(q);
      tr.style.display = hit ? '' : 'none';
      if (hit) shown++;
    });
    $('.count', card).textContent = q ? `${fmt(shown)} dòng khớp` :
      `${fmt(f.rows_total)} dòng trùng${f.rows_truncated ? ` (hiển thị ${fmt(f.rows.length)} dòng đầu)` : ''}`;
  });

  $$('.exp', card).forEach(btn => btn.addEventListener('click', async () => {
    const mode = btn.dataset.mode;
    btn.disabled = true;
    const old = btn.textContent;
    btn.textContent = 'Đang xuất…';
    try {
      const r = await api('/api/export', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: data.token, file_id: f.id, mode,
          filename: $('.exp-name', card).value.trim(),
          renumber_stt: $('#opt-stt').checked,
          update_total_label: $('#opt-total').checked,
          normalize_phones: $('#opt-normalize').checked,
          with_report: true,
        }),
      });
      const li = document.createElement('li');
      li.innerHTML = `<a href="${r.url}" download>⬇ ${esc(r.name)}</a> <span class="muted">${mb(r.size)}</span>`;
      $('.dl-list', card).prepend(li);
      const a = document.createElement('a');
      a.href = r.url; a.download = r.name; document.body.appendChild(a); a.click(); a.remove();
      toast('Đã xuất: ' + r.name);
    } catch (e) { toast(e.message, true); }
    btn.disabled = false; btn.textContent = old;
  }));

  const sel = $('.save-folder', card);
  sel.addEventListener('change', async () => {
    if (sel.value !== '__new__') return;
    const name = await askText('Tạo thư mục mới', '', 'File sẽ được lưu vào thư mục này.',
                               'VD: Đơn hàng tháng 11');
    sel.value = '';
    if (!name) return;
    try {
      const r = await api('/api/folders', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
      await loadFolders();
      sel.insertBefore(new Option(r.name, r.name), sel.lastElementChild);
      sel.value = r.name;
      toast(`Đã tạo thư mục "${r.name}"`);
    } catch (e) { toast(e.message, true); }
  });

  $('.save-btn', card).addEventListener('click', async () => {
    const folder = sel.value === '__new__' ? '' : sel.value.trim();
    if (!folder) return toast('Chọn thư mục cần lưu vào đã nhé', true);
    const what = $('.save-what', card).value;
    const whatLabel = { original: 'file gốc vừa upload', clean: 'file đã loại trùng',
                        dup: 'file chỉ dòng trùng' }[what];
    if (!await askConfirm('Lưu file vào thư mục?',
          `Lưu <b>${whatLabel}</b> của <b>${esc(f.name)}</b><br>vào thư mục <b>${esc(folder)}</b>.`,
          false, 'Lưu')) return;
    try {
      const r = await api('/api/save-to-folder', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: data.token, file_id: f.id, folder, source: what,
          renumber_stt: $('#opt-stt').checked,
          update_total_label: $('#opt-total').checked,
          normalize_phones: $('#opt-normalize').checked,
        }),
      });
      toast(`Đã lưu "${r.saved}" vào thư mục "${r.folder}"`);
      $('.save-note', card).textContent = `✓ Đã lưu vào "${r.folder}"`;
      (r.warnings || []).forEach(w => toast(w, true));
      await loadFolders();
    } catch (e) { toast(e.message, true); }
  });
}

/* ------------------------------------------------------------------ file tạm */
async function refreshTempUsage() {
  try {
    const r = await api('/api/temp-usage');
    $('#temp-usage').innerHTML = r.items
      ? `Đang chiếm <b>${mb(r.size)}</b> · ${fmt(r.items)} thư mục tạm · ${fmt(r.active)} phiên còn dùng được`
      : 'Không có file tạm nào.';
  } catch (e) { $('#temp-usage').textContent = ''; }
}
$('#btn-cleanup').addEventListener('click', async () => {
  if (!await askConfirm('Dọn hết file tạm?',
        'Xoá file đã upload và file đã xuất đang giữ tạm.<br>'
        + '<b>Không ảnh hưởng</b> dữ liệu trong các thư mục lưu trữ.<br>'
        + 'Lưu ý: các link tải file đã xuất ở màn hình kết quả sẽ không còn dùng được.',
        false, 'Dọn')) return;
  try {
    const r = await api('/api/cleanup', { method: 'POST' });
    toast(`Đã dọn ${mb(r.freed)} file tạm`);
    refreshTempUsage();
  } catch (e) { toast(e.message, true); }
});

MODAL.init();
refreshTempUsage();
loadFolders().catch(e => toast(e.message, true));
