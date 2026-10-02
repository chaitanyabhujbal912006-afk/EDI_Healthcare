import { apiFetch, ediStore, escapeHtml } from '../shared.js';

let currentFilter = 'all';
let searchQuery = '';

async function loadClaimsData() {
  const items = ediStore.getSubmissions();
  let claims = items.filter(i => i.type === '837' || (i.type && i.type.startsWith('837')));


  const errCount = claims.filter(i => (i.errorCount || 0) > 0 || i.valid === false).length;
  const validCount = claims.length - errCount;
  const totalValue = claims.reduce((sum, item) => sum + (parseFloat(item.billed != null ? item.billed : (item.amount || 500.00))), 0);

  const clTotal = document.getElementById('cl-total');
  const clValid = document.getElementById('cl-valid');
  const clErrors = document.getElementById('cl-errors');
  const clValue = document.getElementById('cl-value');

  if (clTotal) clTotal.textContent = String(claims.length);
  if (clValid) clValid.textContent = String(validCount);
  if (clErrors) clErrors.textContent = String(errCount);
  if (clValue) clValue.textContent = totalValue > 0 ? '$' + totalValue.toFixed(2) : '$0.00';

  renderClaimsTable(claims);
}

function renderClaimsTable(claimItems) {
  const container = document.getElementById('claims-content');
  if (!container) return;

  let filtered = claimItems;
  if (currentFilter === 'valid') {
    filtered = filtered.filter(i => (i.errorCount || 0) === 0 && i.valid !== false);
  } else if (currentFilter === 'errors') {
    filtered = filtered.filter(i => (i.errorCount || 0) > 0 || i.valid === false);
  } else if (currentFilter === '837p') {
    filtered = filtered.filter(i => i.type === '837P');
  } else if (currentFilter === '837i') {
    filtered = filtered.filter(i => i.type === '837I');
  }

  if (searchQuery) {
    filtered = filtered.filter(i =>
      (i.claimId && i.claimId.toLowerCase().includes(searchQuery)) ||
      (i.filename && i.filename.toLowerCase().includes(searchQuery))
    );
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><span class="ms">description</span></div>
        <h3>No 837 claims data yet</h3>
        <p>Upload 837P or 837I files from the <a href="../dashboard_sleek/code.html" class="text-accent">Dashboard</a> to view claims here.</p>
        <a class="btn btn-primary" href="../dashboard_sleek/code.html"><span class="ms">upload_file</span> Go to Dashboard</a>
      </div>`;
    return;
  }

  const rows = filtered.map(c => {
    const claimId = escapeHtml(c.claimId || 'CLAIM001');
    const billed = parseFloat(c.billed != null ? c.billed : 500.00).toFixed(2);
    const errCount = c.errorCount || 0;
    const ok = errCount === 0 && c.valid !== false;
    const type = escapeHtml(c.type || '837P');
    const date = escapeHtml(c.timeLabel || 'Session');

    return `
      <tr>
        <td><span class="badge badge-purple">${type}</span> <strong>${claimId}</strong></td>
        <td>$${billed}</td>
        <td><span class="badge ${ok ? 'badge-green' : 'badge-red'}">${ok ? 'Valid' : errCount + ' Errors'}</span></td>
        <td>${date}</td>
      </tr>
    `;
  }).join('');

  container.innerHTML = `
    <table class="table" class="table w-full">
      <thead>
        <tr>
          <th>Claim ID</th>
          <th>Billed Amount</th>
          <th>Validation Status</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function initClaims() {
  loadClaimsData();

  // Filter segment control
  const segBtns = document.querySelectorAll('.seg-btn');
  segBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      segBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = (btn.textContent || '').toLowerCase().trim();
      loadClaimsData();
    });
  });

  // Search input
  const searchInput = document.querySelector('.search-bar input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      loadClaimsData();
    });
  }

  // Topnav New Submission button
  const newSubBtns = document.querySelectorAll('.new-sub-btn');
  newSubBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      window.location.href = '../dashboard_sleek/code.html';
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initClaims);
} else {
  initClaims();
}
