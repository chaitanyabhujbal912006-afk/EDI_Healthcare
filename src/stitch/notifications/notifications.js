import { getSessionNotifications, updateNotificationsBadge, ediStore, showToast, escapeHtml } from '../shared.js';

let dismissedIds = new Set(JSON.parse(sessionStorage.getItem('edipro_dismissed_notifs') || '[]'));
let readIds = new Set(JSON.parse(sessionStorage.getItem('edipro_read_notifs') || '[]'));

function saveState() {
  sessionStorage.setItem('edipro_dismissed_notifs', JSON.stringify(Array.from(dismissedIds)));
  sessionStorage.setItem('edipro_read_notifs', JSON.stringify(Array.from(readIds)));
}

function renderNotifications() {
  const all = getSessionNotifications().filter(n => !dismissedIds.has(n.id));
  const container = document.getElementById('notif-list');
  const countSummary = document.getElementById('notif-count-summary');
  const unreadEl = document.getElementById('unread-count');
  const errorEl = document.getElementById('error-count');
  const warnEl = document.getElementById('warn-count');
  const badgeCount = document.getElementById('badge-count');

  const unreadCount = all.filter(n => !readIds.has(n.id)).length;
  const errorCount = all.filter(n => n.severity === 'danger').length;

  if (unreadEl) unreadEl.textContent = unreadCount;
  if (errorEl) errorEl.textContent = `${errorCount} Error${errorCount === 1 ? '' : 's'}`;
  if (warnEl) warnEl.textContent = `0 Warnings`;
  if (badgeCount) {
    badgeCount.textContent = `${unreadCount} unread`;
    badgeCount.className = `badge ${unreadCount > 0 ? 'badge-red' : 'badge-green'}`;
  }
  if (countSummary) {
    countSummary.textContent = `Showing ${all.length} notification${all.length === 1 ? '' : 's'}`;
  }

  if (!container) return;

  if (all.length === 0) {
    container.innerHTML = `
      <div class="empty-state" class="empty-state py-40">
        <div class="empty-state-icon"><span class="ms">notifications_off</span></div>
        <h3>No notifications in this session</h3>
        <p>Validation results and transaction alerts will appear here when files are processed on the Dashboard.</p>
        <a class="btn btn-primary" href="../dashboard_sleek/code.html" class="btn btn-primary mt-12">
          <span class="ms">upload_file</span> Go to Dashboard
        </a>
      </div>
    `;
    return;
  }

  let html = `<div class="notif-group-label">Current Session</div>`;

  all.forEach(item => {
    const isRead = readIds.has(item.id);
    const iconCls = item.severity === 'danger' ? 'icon-red' : 'icon-green';
    html += `
      <div class="notif-item ${isRead ? 'read' : 'unread'}" data-id="${item.id}">
        <div class="notif-icon ${iconCls}"><span class="ms">${escapeHtml(item.icon)}</span></div>
        <div class="notif-content">
          <div class="notif-title">${escapeHtml(item.title)}</div>
          <div class="notif-desc">${escapeHtml(item.desc)}</div>
          <div class="notif-time">${escapeHtml(item.time)}</div>
        </div>
        <button class="notif-dismiss" type="button" aria-label="Dismiss notification" data-dismiss="${item.id}">
          <span class="ms">close</span>
        </button>
      </div>
    `;
  });

  container.innerHTML = html;

  // Bind clicks
  container.querySelectorAll('.notif-item').forEach(itemEl => {
    itemEl.addEventListener('click', (e) => {
      if (e.target.closest('.notif-dismiss')) return;
      const id = itemEl.dataset.id;
      if (readIds.has(id)) {
        readIds.delete(id);
      } else {
        readIds.add(id);
      }
      saveState();
      renderNotifications();
      updateNotificationsBadge();
    });
  });

  container.querySelectorAll('.notif-dismiss').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = btn.dataset.dismiss;
      dismissedIds.add(id);
      saveState();
      renderNotifications();
      updateNotificationsBadge();
    });
  });
}

function initNotifications() {
  renderNotifications();

  const markAllBtn = document.getElementById('mark-all-read');
  if (markAllBtn) {
    markAllBtn.addEventListener('click', () => {
      const all = getSessionNotifications();
      all.forEach(n => readIds.add(n.id));
      saveState();
      renderNotifications();
      updateNotificationsBadge();
      showToast('Notifications Updated', 'All notifications marked as read.', 'success');
    });
  }

  const clearAllBtn = document.getElementById('clear-all');
  if (clearAllBtn) {
    clearAllBtn.addEventListener('click', () => {
      if (confirm('Clear all session notifications and audit records?')) {
        ediStore.clear();
        dismissedIds.clear();
        readIds.clear();
        saveState();
        renderNotifications();
        updateNotificationsBadge();
        showToast('Notifications Cleared', 'All session notifications removed.', 'info');
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNotifications);
} else {
  initNotifications();
}
