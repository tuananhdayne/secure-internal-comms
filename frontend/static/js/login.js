// Trang đăng nhập: hiện/ẩn mật khẩu, điền nhanh tài khoản kiểm thử.
function togglePasswordVisibility() {
    const input = document.getElementById('password');
    const btn = document.getElementById('togglePasswordBtn');
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.setAttribute('aria-pressed', String(show));
    btn.style.color = show ? 'var(--primary)' : '';
}
function fillDemo(code, pw) {
    document.getElementById('employee_code').value = code;
    document.getElementById('password').value = pw;
    document.getElementById('password').focus();
}
