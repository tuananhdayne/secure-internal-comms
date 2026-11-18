/*
 * Cổng Thanh tra — templates/cases.html
 *
 *   openCaseModal(id)  -> GET /admin/cases/{id}/decrypt (JSON: title, description, decrypted,
 *                         evidences[], messages[]) -> renderEvidence() + renderMessages()
 *   Form trạng thái / phản hồi POST về server rồi redirect ?active_case_id=<id> để mở lại modal.
 *
 * QUY TẮC AN TOÀN: mọi dữ liệu từ server (kể cả do người tố giác ẩn danh gửi) chỉ được đưa vào
 * DOM qua textContent / setAttribute (hàm el()). Không ghép chuỗi HTML từ dữ liệu.
 * Debug: mở DevTools > Network, chọn request "decrypt" để xem JSON; header X-Request-ID của
 * response dùng để tra log phía server.
 */

/* ---------- Tiện ích dựng DOM an toàn (không dùng innerHTML với dữ liệu) ---------- */
const ICONS = {
    file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/>',
    image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
    audio: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>',
    video: '<path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    check: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    x: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
};
function svgIcon(name, cls) {
    // Chỉ chèn markup từ bảng ICONS cố định ở trên — không bao giờ từ dữ liệu server.
    const tpl = document.createElement('template');
    tpl.innerHTML = '<svg class="' + (cls || 'icon-sm') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>';
    return tpl.content.firstChild;
}
function el(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
        if (v === null || v === undefined || v === false) continue;
        if (k === 'class') node.className = v;
        else if (k === 'text') node.textContent = v;
        else node.setAttribute(k, v);
    }
    for (const c of children) if (c) node.append(c);
    return node;
}
function safeEvidenceUrl(url) {
    // Chỉ chấp nhận đường dẫn nội bộ tới thư mục bằng chứng.
    return (typeof url === 'string' && /^\/uploads\/evidences\/[A-Za-z0-9._-]+$/.test(url)) ? url : null;
}
function formatTime(raw) {
    // Server trả "YYYY-MM-DD HH:MM:SS" theo UTC -> hiển thị theo giờ máy người xem.
    const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(raw || ''));
    if (!m) return String(raw || '');
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]));
    return d.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' });
}
function caseCode(token) {
    // Cùng quy tắc với filter Jinja `case_code` và ứng dụng di động: 6 ký tự chữ/số cuối, viết hoa.
    return '#' + String(token || '').replace(/[^A-Za-z0-9]/g, '').slice(-6).toUpperCase();
}
const PLACEHOLDER_EVIDENCE = /(?:^|\/)(?:[0-9a-f]{32}_)?evidence_\d+\.bin$/;
const KIND_LABEL = { image: 'Hình ảnh', audio: 'Ghi âm', video: 'Video', file: 'Tài liệu' };

function setBadge(node, cls, iconName, text) {
    node.className = 'badge ' + cls;
    node.replaceChildren(svgIcon(iconName), document.createTextNode(text));
}

/* ---------- Bộ lọc danh sách ---------- */
(function () {
    const chips = document.querySelectorAll('.chip[data-filter]');
    const search = document.getElementById('caseSearch');
    const rows = document.querySelectorAll('#casesTable tbody tr');
    const noMatch = document.getElementById('noMatch');
    if (!rows.length) return;
    let filter = 'ALL';
    function apply() {
        const q = (search.value || '').trim().toLowerCase();
        let shown = 0;
        rows.forEach(r => {
            const ok = (filter === 'ALL' || r.dataset.status === filter) && (!q || r.dataset.search.includes(q));
            r.hidden = !ok;
            if (ok) shown++;
        });
        noMatch.hidden = shown !== 0;
    }
    chips.forEach(c => c.addEventListener('click', () => {
        filter = c.dataset.filter;
        chips.forEach(x => x.setAttribute('aria-pressed', String(x === c)));
        apply();
    }));
    search.addEventListener('input', apply);
})();

/* ---------- Modal thụ lý ---------- */
let lastFocus = null;

function renderEvidence(list) {
    list = list.filter(ev => !PLACEHOLDER_EVIDENCE.test(String(ev.file_url || '')));
    const box = document.getElementById('modalEvidenceList');
    document.getElementById('modalEvidenceCount').textContent = String(list.length);
    document.getElementById('modalEvidenceBadge').hidden = list.length === 0;
    box.replaceChildren();
    if (!list.length) {
        box.append(el('div', { class: 'empty', style: 'padding:1.25rem;', text: 'Hồ sơ này không đính kèm tệp bằng chứng.' }));
        return;
    }
    list.forEach(ev => {
        const url = safeEvidenceUrl(ev.file_url);
        const mime = String(ev.mime_type || '').toLowerCase();
        const fileName = url ? url.substring(url.lastIndexOf('/') + 1) : '(tệp không khả dụng)';
        const displayName = fileName.replace(/^[0-9a-f]{32}_/, '');
        const kind = mime.startsWith('image/') ? 'image' : mime.startsWith('audio/') ? 'audio' : mime.startsWith('video/') ? 'video' : 'file';

        const row = el('div', { class: 'ev-row' },
            el('span', { class: 'ev-ico' }, svgIcon(kind, 'icon')),
            el('div', { style: 'min-width:0;flex:1;' },
                el('div', { class: 'ev-name', title: displayName, text: displayName }),
                el('div', { class: 'ev-sub' }, el('span', { text: KIND_LABEL[kind] }))
            ),
            url ? el('a', { class: 'btn btn-secondary btn-sm', href: url, download: displayName, 'aria-label': 'Tải ' + displayName }, svgIcon('download'), el('span', { text: 'Tải' })) : null
        );
        const item = el('div', { class: 'ev' }, row);
        if (url && kind !== 'file') {
            const media = kind === 'image'
                ? el('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, el('img', { src: url, alt: 'Bằng chứng hình ảnh', loading: 'lazy' }))
                : el(kind, { src: url, controls: 'controls', preload: 'metadata' });
            item.append(el('div', { class: 'ev-media' }, media));
        }
        box.append(item);
    });
}

function renderMessages(list) {
    const box = document.getElementById('modalMessagesList');
    box.replaceChildren();
    if (!list.length) {
        box.append(el('div', { class: 'empty', style: 'padding:1.5rem .5rem;' },
            el('div', { class: 'empty-ico' }, svgIcon('message', 'icon')),
            el('div', { text: 'Chưa có tin nhắn. Gửi phản hồi bên dưới để bắt đầu trao đổi với người gửi.' })));
        return;
    }
    list.forEach(m => {
        const mine = m.sender_type === 'COMPLIANCE_OFFICER';
        box.append(el('div', { class: 'msg ' + (mine ? 'me' : 'them') },
            el('div', { class: 'msg-who' }, svgIcon(mine ? 'user' : 'shield'), el('span', { text: mine ? 'Bạn (Ban Thanh tra)' : 'Người gửi (ẩn danh)' })),
            el('div', { text: String(m.content ?? '') }),
            el('div', { class: 'msg-time', text: formatTime(m.created_at) })
        ));
    });
    box.scrollTop = box.scrollHeight;
}

async function openCaseModal(caseId) {
    caseId = parseInt(caseId, 10);
    if (!Number.isFinite(caseId)) return;
    const modal = document.getElementById('caseModal');
    lastFocus = document.activeElement;
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';

    const $ = (id) => document.getElementById(id);
    const badge = $('modalDecryptedBadge');
    $('modalCaseToken').textContent = 'Đang mở hồ sơ…';
    $('modalCategory').textContent = '';
    $('modalDecryptedTitle').replaceChildren(el('div', { class: 'loading-line', style: 'width:60%;' }));
    $('modalDecryptedDesc').replaceChildren(el('div', { class: 'loading-line' }), el('div', { class: 'loading-line', style: 'width:80%;margin-top:.5rem;' }));
    badge.className = 'badge badge-info'; badge.textContent = 'Đang tải';
    $('modalEvidenceList').replaceChildren();
    $('modalMessagesList').replaceChildren();
    $('statusForm').action = '/admin/cases/' + caseId + '/status';
    $('replyForm').action = '/admin/cases/' + caseId + '/reply';
    modal.querySelector('.icon-btn').focus();

    try {
        const res = await fetch('/admin/cases/' + caseId + '/decrypt', { credentials: 'same-origin' });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const rid = res.headers.get('X-Request-ID');
            const reason = res.status === 403 ? 'Bạn không có quyền xem hồ sơ này.'
                : res.status === 404 ? 'Hồ sơ không tồn tại hoặc đã bị xóa.'
                : 'Không thể mở hồ sơ lúc này. Vui lòng thử lại sau.';
            throw new Error(reason + (rid ? ' Mã hỗ trợ: ' + rid.substring(0, 8) : ''));
        }

        $('modalCaseToken').textContent = 'Hồ sơ ' + caseCode(data.case_token);
        $('modalCaseToken').title = String(data.case_token ?? '');
        $('modalCategory').textContent = String(data.category ?? '');
        $('modalDecryptedTitle').textContent = String(data.title ?? '');
        $('modalDecryptedDesc').textContent = String(data.description ?? '');
        const sel = $('modalStatusSelect');
        const st = data.status === 'UNDER_INVESTIGATION' ? 'INVESTIGATING' : data.status;
        if ([...sel.options].some(o => o.value === st)) sel.value = st;

        const failed = data.decrypted === false;
        if (failed) setBadge(badge, 'badge-warning', 'alert', 'Không đọc được nội dung');
        else setBadge(badge, 'badge-success', 'check', 'Nội dung nguyên vẹn');

        renderEvidence(Array.isArray(data.evidences) ? data.evidences : []);
        renderMessages(Array.isArray(data.messages) ? data.messages : []);
    } catch (err) {
        $('modalDecryptedTitle').textContent = 'Không thể mở hồ sơ';
        $('modalDecryptedDesc').textContent = (err instanceof TypeError) ? 'Mất kết nối tới máy chủ. Vui lòng kiểm tra mạng và thử lại.' : err.message;
        setBadge(badge, 'badge-danger', 'x', 'Lỗi');
    }
}

function closeCaseModal() {
    document.getElementById('caseModal').classList.remove('open');
    document.body.style.overflow = '';
    const url = new URL(window.location);
    url.searchParams.delete('active_case_id');
    window.history.replaceState({}, '', url);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('caseModal').classList.contains('open')) closeCaseModal();
});

window.addEventListener('DOMContentLoaded', () => {
    const activeId = new URLSearchParams(window.location.search).get('active_case_id');
    if (activeId) openCaseModal(activeId);
});
