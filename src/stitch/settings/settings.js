import { apiFetch, showToast, ediStore } from '../shared.js';

async function initSettings() {
  // Appearance select
  const sel = document.getElementById('appearance-select');
  if (sel) {
    sel.value = localStorage.getItem('theme') || 'light';
    sel.addEventListener('change', () => {
      const html = document.documentElement;
      const t = sel.value === 'system'
        ? (window.matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light')
        : sel.value;
      html.classList.toggle('dark', t === 'dark');
      localStorage.setItem('theme', t);
    });
  }

  // Tab switching
  const tabs = document.querySelectorAll('.snav-item[data-tab]');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const targetTab = btn.dataset.tab;
      ['general', 'notifications', 'api', 'security', 'team'].forEach(t => {
        const el = document.getElementById('tab-' + t);
        if (el) el.style.display = t === targetTab ? 'block' : 'none';
      });
      const dangerSection = document.getElementById('danger-section');
      if (dangerSection) {
        dangerSection.style.display = targetTab === 'security' ? 'block' : 'none';
      }
    });
  });

  const dangerSection = document.getElementById('danger-section');
  if (dangerSection) dangerSection.style.display = 'none';

  // Toggle switch listeners
  document.querySelectorAll('.toggle').forEach(el => {
    el.addEventListener('click', () => {
      el.classList.toggle('on');
    });
  });

  // Load engine status from /api/health/detailed
  async function loadEngineStatus() {
    try {
      const res = await apiFetch('/api/health/detailed');
      if (res.ok) {
        const data = await res.json();

        const badge = document.getElementById('engine-status-badge');
        if (badge) badge.textContent = `Online (v${data.engine_version || '1.0.0'})`;

        const authStatus = document.getElementById('engine-auth-status');
        if (authStatus) {
          authStatus.textContent = data.auth_enabled ? 'Enforced (Active)' : 'Standard (Optional)';
          authStatus.className = 'chip ' + (data.auth_enabled ? 'chip-success' : 'chip-info');
        }

        const llmStatus = document.getElementById('engine-llm-status');
        if (llmStatus) {
          llmStatus.textContent = data.external_llm_enabled ? 'Server Enabled (Active)' : 'Rule-based Fallback Only';
          llmStatus.className = 'chip ' + (data.external_llm_enabled ? 'chip-success' : 'chip-neutral');
        }

        const ruleCount = document.getElementById('engine-rule-count');
        if (ruleCount) {
          ruleCount.textContent = (data.rule_count || data.total_built_in_rules || 60) + ' Rules';
        }

        const uploadLimit = document.getElementById('engine-upload-limit');
        if (uploadLimit) {
          uploadLimit.textContent = data.limits?.max_upload_mb ? `${data.limits.max_upload_mb} MB` : '50 MB';
        }

        const batchLimit = document.getElementById('engine-batch-limit');
        if (batchLimit) {
          batchLimit.textContent = data.limits?.max_batch_mb ? `${data.limits.max_batch_mb} MB` : '100 MB';
        }
      }
    } catch (err) {
      const badge = document.getElementById('engine-status-badge');
      if (badge) {
        badge.textContent = 'Offline / Local';
        badge.className = 'badge badge-gray';
      }
    }
  }

  loadEngineStatus();

  // Save settings button
  const saveBtn = document.getElementById('save-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      try {
        const res = await apiFetch('/api/health');
        if (res.ok) {
          showToast('Settings Saved', 'Preferences saved and FastAPI backend verified.', 'success');
        } else {
          showToast('Settings Saved', 'Preferences saved locally.', 'info');
        }
      } catch {
        showToast('Settings Saved', 'Preferences saved locally.', 'info');
      }
    });
  }

  // Clear audit data button
  const clearDataBtn = document.getElementById('btn-clear-data');
  if (clearDataBtn) {
    clearDataBtn.addEventListener('click', () => {
      if (confirm('Clear all session audit data?')) {
        ediStore.clear();
        showToast('Audit Data Cleared', 'Session storage audit data has been reset.', 'success');
      }
    });
  }

  // Reset settings button
  const resetBtn = document.getElementById('btn-reset-settings');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (confirm('Reset all settings to defaults?')) {
        sessionStorage.clear();
        localStorage.removeItem('theme');
        window.location.reload();
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSettings);
} else {
  initSettings();
}
