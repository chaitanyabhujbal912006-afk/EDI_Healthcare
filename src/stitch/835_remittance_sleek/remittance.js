import { apiFetch, ediStore, escapeHtml } from '../shared.js';

let currentFilter = 'all';
let searchQuery = '';

async function loadRemittanceData() {
  const items = ediStore.getSubmissions();
  let rm = items.filter(i => i.type === '835');


  // Calculate totals
  const totalPaid = rm.reduce((sum, item) => sum + (parseFloat(item.paid != null ? item.paid : (item.amount || 0))), 0);
  const totalBilled = rm.reduce((sum, item) => sum + (parseFloat(item.billed != null ? item.billed : (item.amount || 0))), 0);
  const totalAdj = rm.reduce((sum, item) => sum + (parseFloat(item.adjustments != null ? item.adjustments : Math.max(0, (item.billed || 0) - (item.paid || item.amount || 0)))), 0);
  const grandTotal = Math.max(totalBilled, totalPaid + totalAdj, 1);

  const countEl = document.getElementById('rm-count');
  const totalEl = document.getElementById('rm-total');
  const billedEl = document.getElementById('rm-billed');
  const adjEl = document.getElementById('rm-adj');

  if (countEl) countEl.textContent = rm.length ? String(rm.length) : '0';
  if (totalEl) totalEl.textContent = totalPaid > 0 ? '$' + totalPaid.toFixed(2) : '$0.00';
  if (billedEl) billedEl.textContent = totalBilled > 0 ? '$' + totalBilled.toFixed(2) : '$0.00';
  if (adjEl) adjEl.textContent = totalAdj > 0 ? '$' + totalAdj.toFixed(2) : '$0.00';

  // Breakdown mini chart
  const amtPaidEl = document.getElementById('amt-paid');
  const amtAdjEl  = document.getElementById('amt-adj');
  const amtPrEl   = document.getElementById('amt-pr');
  const barPaidEl = document.getElementById('bar-paid');
  const barAdjEl  = document.getElementById('bar-adj');
  const barPrEl   = document.getElementById('bar-pr');

  if (amtPaidEl) amtPaidEl.textContent = '$' + totalPaid.toFixed(2);
  if (amtAdjEl)  amtAdjEl.textContent  = '$' + totalAdj.toFixed(2);
  if (amtPrEl)   amtPrEl.textContent   = '$0.00';
  if (barPaidEl) barPaidEl.style.width = Math.min(100, Math.round((totalPaid / grandTotal) * 100)) + '%';
  if (barAdjEl)  barAdjEl.style.width  = Math.min(100, Math.round((totalAdj / grandTotal) * 100)) + '%';
  if (barPrEl)   barPrEl.style.width   = '0%';

  renderTable(rm);
}

function renderTable(rmItems) {
  const container = document.getElementById('rm-content');
  if (!container) return;

  let filtered = rmItems;
  if (currentFilter === 'paid') {
    filtered = filtered.filter(i => (i.paid || i.amount) > 0);
  } else if (currentFilter === 'adjusted') {
    filtered = filtered.filter(i => (i.adjustments || 0) > 0);
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
        <div class="empty-state-icon"><span class="ms">receipt_long</span></div>
        <h3>No 835 remittance data yet</h3>
        <p>Upload 835 files from the <a href="../dashboard_sleek/code.html" class="text-accent">Dashboard</a> to see payment data here.</p>
        <a class="btn btn-primary" href="../dashboard_sleek/code.html"><span class="ms">upload_file</span> Go to Dashboard</a>
      </div>`;
    return;
  }

  let rowsHtml = filtered.map(item => {
    const claimId = escapeHtml(item.claimId || 'CLAIM001');
    const billed = parseFloat(item.billed != null ? item.billed : 500.00).toFixed(2);
    const paid = parseFloat(item.paid != null ? item.paid : (item.amount || 450.00)).toFixed(2);
    const adj = parseFloat(item.adjustments != null ? item.adjustments : 50.00).toFixed(2);
    const date = escapeHtml(item.timeLabel || 'Session');
    const status = escapeHtml(item.status || 'Paid');

    return `
      <tr class="rm-table-row">
        <td><span class="badge badge-green">835</span> <strong>${claimId}</strong></td>
        <td>$${billed}</td>
        <td><strong class="text-success">$${paid}</strong></td>
        <td class="text-warning">$${adj}</td>
        <td><span class="badge badge-blue">${status}</span></td>
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
          <th>Paid Amount</th>
          <th>Adjustments</th>
          <th>Status</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>`;
}

function initRemittance() {
  loadRemittanceData();

  // Filter buttons
  const segBtns = document.querySelectorAll('.seg-btn');
  segBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      segBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter || 'all';
      loadRemittanceData();
    });
  });

  // Search input
  const searchInput = document.getElementById('rm-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      loadRemittanceData();
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
  document.addEventListener('DOMContentLoaded', initRemittance);
} else {
  initRemittance();
}
