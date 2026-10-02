import { apiFetch, ediStore, escapeHtml } from '../shared.js';

async function initProfile() {
  // Load identity from /api/me
  try {
    const res = await apiFetch('/api/me');
    if (res.ok) {
      const data = await res.json();
      const subject = data.subject || 'Admin';
      const role = (data.role || 'viewer').toUpperCase();
      const authType = data.auth_type === 'jwt' ? 'OIDC Bearer JWT' : 'API Key (Service)';

      const nameEl = document.getElementById('profile-name');
      const subEl = document.getElementById('profile-subject');
      const roleEl = document.getElementById('profile-role');
      const authEl = document.getElementById('profile-auth-type');
      const roleBadge = document.getElementById('badge-role');

      if (nameEl) nameEl.textContent = subject;
      if (subEl) subEl.textContent = subject;
      if (roleEl) roleEl.textContent = role;
      if (authEl) authEl.textContent = authType;
      if (roleBadge) roleBadge.textContent = role;

      const initials = subject.slice(0, 2).toUpperCase();
      document.querySelectorAll('.avatar-initials').forEach(el => {
        el.textContent = initials;
      });
    }
  } catch (err) {
    console.warn('Could not fetch /api/me:', err);
  }

  // Load activity from session store
  const actContainer = document.getElementById('profile-activity');
  if (actContainer) {
    const submissions = ediStore.getSubmissions();
    if (submissions.length === 0) {
      actContainer.innerHTML = `
        <div class="empty-state" class="empty-state py-40">
          <div class="empty-state-icon"><span class="ms">history</span></div>
          <h3>No session activity yet</h3>
          <p>Files processed in this session will be recorded here.</p>
        </div>
      `;
    } else {
      actContainer.innerHTML = submissions.slice(0, 10).map(sub => {
        const hasErr = (sub.errorCount || 0) > 0;
        const dotColor = hasErr ? 'var(--danger)' : 'var(--success)';
        const badgeCls = hasErr ? 'badge-red' : 'badge-green';
        const badgeTxt = hasErr ? `${sub.errorCount} Errors` : 'Valid';
        return `
          <div class="activity-item">
            <div class="activity-dot" class="activity-dot ${hasErr ? 'bg-danger' : 'bg-success'}"></div>
            <div class="flex-1">
              <span class="font-14 font-bold text-primary">
                Processed ${escapeHtml(sub.type || 'EDI')} — ${escapeHtml(sub.filename)}
              </span>
              <div class="font-12 text-tertiary mt-4">
                ${escapeHtml(sub.timeLabel || 'Recent')}
              </div>
            </div>
            <span class="badge ${badgeCls}">${badgeTxt}</span>
          </div>
        `;
      }).join('');
    }
  }

  // New Submission buttons
  document.querySelectorAll('.new-sub-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      window.location.href = '../dashboard_sleek/code.html';
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProfile);
} else {
  initProfile();
}
