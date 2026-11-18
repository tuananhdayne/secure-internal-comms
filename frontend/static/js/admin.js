// Hành vi chung của Web Admin: mở/đóng menu ngăn kéo trên màn hình hẹp.
function toggleNav(force) {
    const open = typeof force === 'boolean' ? force : !document.body.classList.contains('nav-open');
    document.body.classList.toggle('nav-open', open);
}
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') toggleNav(false); });

// Nút có data-toggle="#id": mở/đóng khối tương ứng (vd. form "Thêm nhân viên").
// Mở sẵn khi URL có #id (liên kết "Thao tác nhanh" từ trang Tổng quan).
document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-toggle]');
    if (!btn) return;
    const target = document.querySelector(btn.getAttribute('data-toggle'));
    if (!target) return;
    e.preventDefault();
    target.hidden = !target.hidden;
    if (!target.hidden) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        const first = target.querySelector('input, select, textarea');
        if (first) first.focus();
    }
});
window.addEventListener('DOMContentLoaded', () => {
    if (location.hash.length > 1) {
        const el = document.getElementById(location.hash.slice(1));
        if (el && el.hidden) el.hidden = false;
    }
});
