import { apiFetch, ediStore, escapeHtml } from '../shared.js';

async function loadEnrollmentData() {
  const all = ediStore.getSubmissions();
  let items = all.filter(i => i.type && i.type.toUpperCase().includes('834'));


  const enrollCount = document.getElementById('enroll-count');
  if (enrollCount) enrollCount.textContent = String(items.length);

  const container = document.getElementById('enrollment-content');
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="ms">group_add</span>
        <h3>No 834 enrollment data yet</h3>
        <p>Upload 834 files from the <a href="../dashboard_sleek/code.html" class="text-accent">Dashboard</a> to view enrollment data here.</p>
        <a class="btn btn-primary" href="../dashboard_sleek/code.html" class="btn btn-primary mt-12">
          <span class="ms">upload_file</span> Go to Dashboard
        </a>
      </div>`;
  } else {
    const rows = items.map(item => {
      const ok = (item.errorCount || 0) === 0;
      return `
        <tr>
          <td class="font-bold">${escapeHtml(item.filename)}</td>
          <td><span class="badge badge-blue">${escapeHtml(item.type)}</span></td>
          <td class="td-mono">${item.errorCount || 0}</td>
          <td><span class="badge ${ok ? 'badge-green' : 'badge-red'}">${ok ? 'Valid' : item.errorCount + ' Errors'}</span></td>
          <td class="td-mono">${escapeHtml(item.timeLabel || 'Session')}</td>
        </tr>
      `;
    }).join('');

    container.innerHTML = `
      <div class="table-wrap">
        <table class="table" class="table w-full">
          <thead>
            <tr>
              <th>File Name</th><th>Type</th><th>Errors</th><th>Status</th><th>Processed</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }
}

function initEnrollment() {
  loadEnrollmentData();

  const newSubBtns = document.querySelectorAll('.new-sub-btn');
  newSubBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      window.location.href = '../dashboard_sleek/code.html';
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initEnrollment);
} else {
  initEnrollment();
}
