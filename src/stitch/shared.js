/* shared.js — EdiPro shared page init: theme, sidebar, localStorage */
function initPage() {
  /* ---- Theme ---- */
  const html = document.documentElement;
  const themeBtn = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  const themeLabel = document.getElementById('theme-label');

  function applyTheme(t) {
    html.classList.toggle('dark', t === 'dark');
    if (themeIcon) themeIcon.textContent = t === 'dark' ? 'dark_mode' : 'light_mode';
    if (themeLabel) themeLabel.textContent = t === 'dark' ? 'Dark' : 'Light';
    localStorage.setItem('theme', t);
  }
  applyTheme(localStorage.getItem('theme') || 'light');
  if (themeBtn) themeBtn.addEventListener('click', () => applyTheme(html.classList.contains('dark') ? 'light' : 'dark'));

  /* ---- Sidebar ---- */
  const sidebar = document.getElementById('sidebar');
  const mainEl = document.getElementById('main');
  const overlay = document.getElementById('overlay');
  const sidebarToggle = document.getElementById('sidebar-toggle');

  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('collapsed', !open);
    if (mainEl) mainEl.classList.toggle('expanded', !open);
    if (overlay) overlay.classList.toggle('visible', open && window.innerWidth < 900);
  }

  setSidebar(window.innerWidth >= 900);
  if (sidebarToggle) sidebarToggle.addEventListener('click', () => setSidebar(sidebar.classList.contains('collapsed')));
  if (overlay) overlay.addEventListener('click', () => setSidebar(false));
  window.addEventListener('resize', () => { if (window.innerWidth >= 900) setSidebar(true); });
}

/* ---- Shared storage helpers ---- */
function readSubmissions() {
  try { const p = JSON.parse(localStorage.getItem('ediSubmissions') || '[]'); return Array.isArray(p) ? p : []; }
  catch { return []; }
}
