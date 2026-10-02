/* shared.js — EdiPro shared page init: theme, sidebar, command palette, toast system, route guard, auth & store */

// HTML escaping helper
export function escapeHtml(str) {
  if (typeof str !== 'string') return str == null ? '' : String(str);
  return str.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[m];
  });
}
export const esc = escapeHtml;

// Session-only EDI storage
const EDI_STORE_KEY = 'ediSubmissions';

export const ediStore = {
  getSubmissions() {
    try {
      const p = JSON.parse(sessionStorage.getItem(EDI_STORE_KEY) || '[]');
      return Array.isArray(p) ? p : [];
    } catch {
      return [];
    }
  },
  saveSubmission(sub) {
    const list = this.getSubmissions();
    list.unshift(sub);
    sessionStorage.setItem(EDI_STORE_KEY, JSON.stringify(list.slice(0, 100)));
    updateNotificationsBadge();
    return list;
  },
  setSubmissions(items) {
    sessionStorage.setItem(EDI_STORE_KEY, JSON.stringify(Array.isArray(items) ? items : []));
    updateNotificationsBadge();
  },
  clear() {
    sessionStorage.removeItem(EDI_STORE_KEY);
    updateNotificationsBadge();
  }
};

// Derive real notifications strictly from session validation results
export function getSessionNotifications() {
  const submissions = ediStore.getSubmissions();
  const notifications = [];

  submissions.forEach((item, idx) => {
    const errCount = item.errorCount || 0;
    const fn = escapeHtml(item.filename || 'EDI Document');
    const tx = escapeHtml(item.type || 'EDI');

    if (errCount > 0) {
      notifications.push({
        id: `notif-err-${idx}`,
        title: `${tx} Validation Issues (${errCount})`,
        desc: `File "${fn}" completed validation with ${errCount} rule error(s).`,
        time: item.timeLabel || 'Recent',
        severity: 'danger',
        icon: 'error',
        read: false
      });
    } else {
      notifications.push({
        id: `notif-ok-${idx}`,
        title: `${tx} Validated Successfully`,
        desc: `File "${fn}" passed all HIPAA 5010 compliance rules cleanly.`,
        time: item.timeLabel || 'Recent',
        severity: 'success',
        icon: 'check_circle',
        read: false
      });
    }
  });

  return notifications;
}

export function updateNotificationsBadge() {
  const notifs = getSessionNotifications();
  const unreadCount = notifs.filter(n => !n.read).length;
  const badges = document.querySelectorAll('.nav-badge');
  badges.forEach(b => {
    b.textContent = unreadCount;
    b.style.display = unreadCount > 0 ? 'inline-flex' : 'none';
  });
  const notifDots = document.querySelectorAll('.notif-dot');
  notifDots.forEach(d => {
    d.style.display = unreadCount > 0 ? 'block' : 'none';
  });
}

// Toast notification system with ARIA live region
export function showToast(title, message = '', type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-atomic', 'true');
    container.setAttribute('role', 'status');
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;

  const iconMap = {
    success: 'check_circle',
    error: 'error',
    warning: 'warning',
    info: 'info'
  };

  toast.innerHTML = `
    <span class="ms toast-icon">${iconMap[type] || 'info'}</span>
    <div class="toast-content">
      <div class="toast-title">${escapeHtml(title)}</div>
      ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
    </div>
    <button class="toast-close" type="button" aria-label="Close notification">&times;</button>
  `;

  const closeBtn = toast.querySelector('.toast-close');
  closeBtn.addEventListener('click', () => {
    toast.classList.add('toast-hiding');
    setTimeout(() => toast.remove(), 250);
  });

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.add('toast-hiding');
      setTimeout(() => toast.remove(), 250);
    }
  }, duration);
}

// Auth token management
let _inMemoryAccessToken = null;

export function setAccessToken(token) {
  _inMemoryAccessToken = token;
  if (token) {
    sessionStorage.setItem('edipro_access_token', token);
  } else {
    sessionStorage.removeItem('edipro_access_token');
  }
}

export function getAccessToken() {
  if (!_inMemoryAccessToken && typeof sessionStorage !== 'undefined') {
    _inMemoryAccessToken = sessionStorage.getItem('edipro_access_token');
  }
  return _inMemoryAccessToken;
}

// Unified API fetch helper with explicit error UX and request IDs
export async function apiFetch(input, init = {}) {
  init = { ...init };
  const headers = new Headers(init.headers || {});
  const token = getAccessToken();
  const apiKey = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('edipro_api_key') : null;

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  } else if (apiKey && !headers.has('X-API-Key') && !headers.has('Authorization')) {
    headers.set('X-API-Key', apiKey);
  }

  init.headers = headers;

  let res;
  try {
    res = await fetch(input, init);
  } catch (err) {
    showToast('Network Error', err.message || 'Unable to communicate with API server.', 'error');
    throw err;
  }

  const reqId = res.headers.get('X-Request-ID') || 'N/A';

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const clone = res.clone();
      const data = await clone.json();
      if (data && data.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      try {
        const text = await res.clone().text();
        if (text) detail = text.slice(0, 150);
      } catch {}
    }

    const errorMsg = `${detail} (Request ID: ${reqId})`;

    if (res.status === 401) {
      showToast('401 Unauthorized', errorMsg, 'error');
      const path = window.location.pathname;
      const isLogin = path.endsWith('index.html') || path.endsWith('/') || path.includes('login_sleek_redesign');
      if (!isLogin) {
        sessionStorage.removeItem('edipro_access_token');
        sessionStorage.removeItem('edipro_api_key');
        _inMemoryAccessToken = null;
        const target = path.includes('/stitch/')
          ? path.replace(/\/stitch\/.*$/, '/stitch/index.html')
          : '../index.html';
        setTimeout(() => { window.location.href = target; }, 800);
      }
    } else if (res.status === 413) {
      showToast('413 Payload Too Large', errorMsg, 'error');
    } else if (res.status === 415) {
      showToast('415 Unsupported Media Type', errorMsg, 'error');
    } else if (res.status === 429) {
      showToast('429 Rate Limit Exceeded', errorMsg, 'error');
    } else {
      showToast(`Error ${res.status}`, errorMsg, 'error');
    }
  }

  return res;
}

// Route Guard
async function checkAuthRouteGuard() {
  const path = window.location.pathname;
  const isLogin = path.endsWith('index.html') || path.endsWith('/') || path.includes('login_sleek_redesign');
  if (isLogin) return;

  let authEnabled = sessionStorage.getItem('edipro_auth_enabled');
  if (authEnabled === null) {
    try {
      const res = await fetch('/api/auth/config');
      if (res.ok) {
        const conf = await res.json();
        authEnabled = conf.oidc_configured ? 'true' : 'false';
      } else {
        authEnabled = 'false';
      }
    } catch {
      authEnabled = 'false';
    }
    sessionStorage.setItem('edipro_auth_enabled', authEnabled);
  }

  if (authEnabled === 'true') {
    const token = getAccessToken();
    const apiKey = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('edipro_api_key') : null;
    if (!token && !apiKey) {
      const target = path.includes('/stitch/')
        ? path.replace(/\/stitch\/.*$/, '/stitch/index.html')
        : '../index.html';
      window.location.href = target;
    }
  }
}

// User Initials and Identity Hydration
async function hydrateUserIdentity() {
  let user = null;
  const cached = sessionStorage.getItem('edipro_user_me');
  if (cached) {
    try { user = JSON.parse(cached); } catch {}
  }

  if (!user) {
    try {
      const res = await apiFetch('/api/me');
      if (res.ok) {
        user = await res.json();
        sessionStorage.setItem('edipro_user_me', JSON.stringify(user));
      }
    } catch {
      // Optional fallback
    }
  }

  const subject = (user && user.subject) ? user.subject : 'Admin';
  const role = (user && user.role) ? user.role : 'Administrator';
  const initials = subject.slice(0, 2).toUpperCase();

  // Set avatar initials
  document.querySelectorAll('.avatar-initials').forEach(el => {
    el.textContent = initials;
  });

  // Set user profile info if present
  const suName = document.querySelector('.su-name');
  if (suName) suName.textContent = subject;
  const suRole = document.querySelector('.su-role');
  if (suRole) suRole.textContent = role.toUpperCase();
  const suAvatar = document.querySelector('.su-avatar');
  if (suAvatar) suAvatar.textContent = initials;
}

// Command Palette (Accessible, no inline onclick)
function initCommandPalette() {
  if (document.getElementById('cmd-palette-backdrop')) return;

  const backdrop = document.createElement('div');
  backdrop.id = 'cmd-palette-backdrop';
  backdrop.className = 'cmd-palette-backdrop';
  backdrop.setAttribute('role', 'dialog');
  backdrop.setAttribute('aria-modal', 'true');
  backdrop.setAttribute('aria-label', 'Command Palette');

  const modal = document.createElement('div');
  modal.className = 'cmd-palette-modal';

  modal.innerHTML = `
    <div class="cmd-palette-header">
      <span class="ms">search</span>
      <input type="text" id="cmd-palette-input" placeholder="Type a command or search pages (e.g., 837, Claims, Settings)..." autocomplete="off" aria-label="Command search input" />
      <span class="kbd">ESC</span>
    </div>
    <div class="cmd-palette-results" id="cmd-palette-results" role="listbox">
      <div class="cmd-group-label">Quick Navigation</div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../dashboard_sleek/code.html"><span class="ms">dashboard</span><span>Dashboard Overview</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../master_parser_sleek/code.html"><span class="ms">analytics</span><span>Master EDI Parser</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../837_claims_view/code.html"><span class="ms">description</span><span>837 Professional Claims</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../835_remittance_sleek/code.html"><span class="ms">payments</span><span>835 Payment Remittance</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../834_enrollment_sleek/code.html"><span class="ms">group_add</span><span>834 Member Enrollment</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../notifications/code.html"><span class="ms">notifications</span><span>Notification Center</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../settings/code.html"><span class="ms">settings</span><span>System Settings & Rules</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../user_profile/code.html"><span class="ms">person</span><span>User Profile & Access</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../documentation/code.html"><span class="ms">menu_book</span><span>API & Schema Documentation</span><span class="kbd">Go</span></div>
      <div class="cmd-item" role="option" tabindex="0" data-url="../help_center/code.html"><span class="ms">help</span><span>Support & Help Center</span><span class="kbd">Go</span></div>
    </div>
  `;

  modal.addEventListener('click', (e) => e.stopPropagation());
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  const input = modal.querySelector('#cmd-palette-input');
  const results = modal.querySelector('#cmd-palette-results');

  backdrop.addEventListener('click', closeCommandPalette);

  input.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const items = results.querySelectorAll('.cmd-item');
    items.forEach(item => {
      const text = item.textContent.toLowerCase();
      item.style.display = text.includes(q) ? 'flex' : 'none';
    });
  });

  results.addEventListener('click', (e) => {
    const item = e.target.closest('.cmd-item');
    if (item && item.dataset.url) {
      closeCommandPalette();
      window.location.href = item.dataset.url;
    }
  });

  input.addEventListener('keydown', (e) => {
    const items = Array.from(results.querySelectorAll('.cmd-item')).filter(i => i.style.display !== 'none');
    if (!items.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      items[0].focus();
    } else if (e.key === 'Enter' && items.length > 0) {
      e.preventDefault();
      closeCommandPalette();
      window.location.href = items[0].dataset.url;
    }
  });

  results.addEventListener('keydown', (e) => {
    const current = document.activeElement;
    const items = Array.from(results.querySelectorAll('.cmd-item')).filter(i => i.style.display !== 'none');
    const idx = items.indexOf(current);
    if (e.key === 'ArrowDown' && idx < items.length - 1) {
      e.preventDefault();
      items[idx + 1].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (idx > 0) items[idx - 1].focus();
      else input.focus();
    } else if (e.key === 'Enter' && current && current.dataset.url) {
      e.preventDefault();
      closeCommandPalette();
      window.location.href = current.dataset.url;
    }
  });
}

export function openCommandPalette() {
  initCommandPalette();
  const backdrop = document.getElementById('cmd-palette-backdrop');
  if (backdrop) {
    backdrop.classList.add('visible');
    const input = backdrop.querySelector('#cmd-palette-input');
    if (input) {
      input.value = '';
      input.focus();
      const items = backdrop.querySelectorAll('.cmd-item');
      items.forEach(i => i.style.display = 'flex');
    }
  }
}

export function closeCommandPalette() {
  const backdrop = document.getElementById('cmd-palette-backdrop');
  if (backdrop) {
    backdrop.classList.remove('visible');
  }
}

function highlightActiveNav() {
  const currentPath = window.location.pathname;
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    const href = item.getAttribute('href');
    if (!href) return;
    const cleanHref = href.replace(/^\.\.\//, '').replace(/^\.\//, '');
    if (currentPath.endsWith(cleanHref) || currentPath.includes(cleanHref.split('/')[0])) {
      item.classList.add('active');
    }
  });
}

export function initPage() {
  checkAuthRouteGuard();

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

  /* ---- Topnav Navigation Buttons ---- */
  const notifBtns = document.querySelectorAll('.topnav-right button[onclick*="notifications"]');
  notifBtns.forEach(btn => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', () => {
      const p = window.location.pathname;
      window.location.href = p.includes('dashboard_sleek') || p.includes('835') || p.includes('837') || p.includes('834') || p.includes('settings') || p.includes('master')
        ? '../notifications/code.html'
        : 'notifications/code.html';
    });
  });

  const avatarDivs = document.querySelectorAll('.topnav-right .avatar');
  avatarDivs.forEach(div => {
    div.removeAttribute('onclick');
    div.addEventListener('click', () => {
      const p = window.location.pathname;
      window.location.href = p.includes('dashboard_sleek') || p.includes('835') || p.includes('837') || p.includes('834') || p.includes('settings') || p.includes('master')
        ? '../user_profile/code.html'
        : 'user_profile/code.html';
    });
  });

  /* ---- Keyboard Shortcuts ---- */
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openCommandPalette();
    }
    if (e.key === 'Escape') {
      closeCommandPalette();
    }
  });

  /* ---- Search Trigger ---- */
  const searchBtns = document.querySelectorAll('.nav-icon-btn, .search-trigger');
  searchBtns.forEach(btn => {
    if (btn.querySelector('.ms') && btn.querySelector('.ms').textContent.trim() === 'search') {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        openCommandPalette();
      });
    }
  });

  highlightActiveNav();
  updateNotificationsBadge();
  hydrateUserIdentity();
}

// Idle timeout (default 15 minutes of no input)
let _idleTimeoutHandle = null;
const IDLE_TIMEOUT_MS = 15 * 60 * 1000;

export function resetIdleTimeout() {
  if (_idleTimeoutHandle) {
    clearTimeout(_idleTimeoutHandle);
  }
  _idleTimeoutHandle = setTimeout(() => {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.clear();
    }
    _inMemoryAccessToken = null;
    const path = window.location.pathname;
    const isLogin = path.endsWith('index.html') || path.endsWith('/');
    if (!isLogin) {
      const target = path.includes('/stitch/')
        ? path.replace(/\/stitch\/.*$/, '/stitch/index.html')
        : '/stitch/index.html';
      window.location.href = target;
    }
  }, IDLE_TIMEOUT_MS);
}

if (typeof window !== 'undefined') {
  const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
  events.forEach(evt => {
    window.addEventListener(evt, resetIdleTimeout, { passive: true });
  });
  resetIdleTimeout();
}

// Auto init on DOM load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPage);
} else {
  initPage();
}

// Expose globals for backward compatibility and classic scripts
if (typeof window !== 'undefined') {
  window.esc = escapeHtml;
  window.escapeHtml = escapeHtml;
  window.ediStore = ediStore;
  window.apiFetch = apiFetch;
  window.showToast = showToast;
  window.openCommandPalette = openCommandPalette;
  window.closeCommandPalette = closeCommandPalette;
  window.setAccessToken = setAccessToken;
  window.getAccessToken = getAccessToken;
  window.getSessionNotifications = getSessionNotifications;
  window.updateNotificationsBadge = updateNotificationsBadge;
}
