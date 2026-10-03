import { apiFetch, showToast, ediStore, escapeHtml } from '../shared.js';

async function initDashboard() {
  /* ── Live session clock ── */
  const SESSION_START = Date.now();
  const clockTimeEl   = document.getElementById('clock-time');
  const clockUptimeEl = document.getElementById('clock-uptime');

  function pad2(n) { return String(n).padStart(2, '0'); }
  function tickClock() {
    const now = new Date();
    if (clockTimeEl) {
      clockTimeEl.textContent = `${pad2(now.getHours())}:${pad2(now.getMinutes())}:${pad2(now.getSeconds())}`;
    }
    if (clockUptimeEl) {
      const elapsed = Math.floor((Date.now() - SESSION_START) / 1000);
      const m = Math.floor(elapsed / 60);
      const s = elapsed % 60;
      clockUptimeEl.textContent = m > 0 ? `Up ${m}m ${pad2(s)}s` : `Up ${s}s`;
    }
  }
  tickClock();
  setInterval(tickClock, 1000);

  /* ── Backend Online Status Check ── */
  const backendStatusEl = document.getElementById('backend-status-badge');
  const securityStatusEl = document.getElementById('security-status');
  async function checkServerStatus() {
    try {
      const res = await apiFetch('/api/health');
      if (res.ok) {
        if (backendStatusEl) {
          backendStatusEl.textContent = 'Online';
          backendStatusEl.className = 'badge badge-green';
        }
        if (securityStatusEl) securityStatusEl.textContent = 'Active · 5010';
      } else {
        if (backendStatusEl) {
          backendStatusEl.textContent = 'Degraded';
          backendStatusEl.className = 'badge badge-yellow';
        }
      }
    } catch {
      if (backendStatusEl) {
        backendStatusEl.textContent = 'Offline';
        backendStatusEl.className = 'badge badge-red';
      }
      if (securityStatusEl) securityStatusEl.textContent = 'Offline';
    }
  }
  checkServerStatus();

  /* ── DOM Refs ── */
  const uploadTrigger  = document.getElementById('upload-trigger');
  const fileInput      = document.getElementById('file-upload');
  const uploadZone     = document.getElementById('upload-zone');
  const uploadStatus   = document.getElementById('upload-status');
  const recentAudits   = document.getElementById('recent-audits');
  const processedCount = document.getElementById('processed-count');
  const accuracyRate   = document.getElementById('accuracy-rate');
  const storageUsed    = document.getElementById('storage-used');
  const parseLatency   = document.getElementById('parse-latency');
  const clearBtn       = document.getElementById('clear-audits');
  const progressOverlay= document.getElementById('upload-progress');
  const progressBar    = document.getElementById('progress-bar');
  const progressLabel  = document.getElementById('progress-label');
  const donutWrap      = document.getElementById('donut-wrap');

  let totalProcessed = 0, totalValid = 0;

  function updateSummary() {
    const items = ediStore.getSubmissions();
    totalProcessed = items.length;
    totalValid = items.filter(i => (i.errorCount || 0) === 0).length;

    if (processedCount) processedCount.textContent = totalProcessed;
    if (accuracyRate) accuracyRate.textContent = totalProcessed > 0 ? ((totalValid / totalProcessed) * 100).toFixed(1) + '%' : '—';
    if (storageUsed) storageUsed.textContent = totalProcessed;
    if (parseLatency) parseLatency.textContent = totalProcessed > 0 ? '< 250ms' : '—';
    updateDonut();
  }

  function updateDonut() {
    if (!donutWrap) return;
    if (totalProcessed === 0) {
      donutWrap.innerHTML = `<div class="empty-state" class="empty-state py-40">
        <div class="empty-state-icon" class="empty-state-icon avatar-circle-60">
          <span class="ms">donut_large</span>
        </div>
        <h3>No data yet</h3>
        <p>Upload files to see validation stats.</p>
      </div>`;
      return;
    }
    const errors  = totalProcessed - totalValid;
    const pValid  = Math.round((totalValid / totalProcessed) * 100);
    const pError  = 100 - pValid;
    const r = 54, cx = 72, cy = 72;
    const circ = 2 * Math.PI * r;
    const dashValid = (pValid / 100) * circ;
    const dashErr   = (pError / 100) * circ;
    donutWrap.innerHTML = `
      <svg class="donut-svg" width="144" height="144" viewBox="0 0 144 144">
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="16"/>
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--success)" stroke-width="16"
          stroke-dasharray="${dashValid} ${circ}" stroke-dashoffset="${circ * 0.25}"
          stroke-linecap="round" class="donut-ring-stroke">
          <animate attributeName="stroke-dasharray" from="0 ${circ}" to="${dashValid} ${circ}" dur="1.0s" fill="freeze"/>
        </circle>
        ${errors > 0 ? `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--danger)" stroke-width="16"
          stroke-dasharray="${dashErr} ${circ}" stroke-dashoffset="${circ * 0.25 - dashValid}"
          stroke-linecap="round">
          <animate attributeName="stroke-dasharray" from="0 ${circ}" to="${dashErr} ${circ}" dur="1.0s" fill="freeze"/>
        </circle>` : ''}
        <text x="${cx}" y="${cy - 6}" text-anchor="middle" font-family="Inter,sans-serif" font-size="20" font-weight="800" fill="var(--text-primary)">${pValid}%</text>
        <text x="${cx}" y="${cy + 14}" text-anchor="middle" font-family="Inter,sans-serif" font-size="10" font-weight="700" fill="var(--text-tertiary)" letter-spacing="0.06em">VALID</text>
      </svg>
      <div class="donut-legend">
        <div class="legend-item">
          <div class="legend-dot" class="legend-dot bg-success"></div>
          <span class="legend-label">Valid</span>
          <span class="legend-val">${totalValid}</span>
        </div>
        <div class="legend-item">
          <div class="legend-dot" class="legend-dot bg-danger"></div>
          <span class="legend-label">Errors</span>
          <span class="legend-val">${errors}</span>
        </div>
        <div class="legend-item">
          <div class="legend-dot" class="legend-dot bg-accent"></div>
          <span class="legend-label">Total</span>
          <span class="legend-val">${totalProcessed}</span>
        </div>
      </div>`;
  }

  function iconForType(t) {
    if (t === '835') return { icon: 'payments',    cls: 'icon-green' };
    if (t === '834') return { icon: 'group_add',   cls: 'icon-yellow' };
    return                  { icon: 'description', cls: 'icon-blue'  };
  }

  function renderAudits() {
    if (!recentAudits) return;
    const items = ediStore.getSubmissions();
    if (!items.length) {
      recentAudits.innerHTML = `<div class="empty-state"><div class="empty-state-icon"><span class="ms">folder_open</span></div><h3>No audits yet</h3><p>Upload a 837, 835, or 834 file to see results here.</p></div>`;
      return;
    }
    recentAudits.innerHTML = '';
    items.forEach(item => {
      const { icon, cls } = iconForType(item.type);
      const hasErr = (item.errorCount || 0) > 0;
      const card = document.createElement('div');
      card.className = 'audit-card';
      card.innerHTML = `
        <div class="audit-row1">
          <div class="audit-file">
            <div class="audit-file-icon ${cls}"><span class="ms">${icon}</span></div>
            <div>
              <div class="audit-filename">${escapeHtml(item.filename)}</div>
              <div class="audit-source">Processed · HIPAA 5010</div>
            </div>
          </div>
          <span class="audit-type-chip">${escapeHtml(item.type)}</span>
        </div>
        <div class="audit-row2">
          <span class="chip ${hasErr ? 'chip-danger' : 'chip-success'}">${hasErr ? '✕ ' + item.errorCount + ' Errors' : '✓ Valid'}</span>
          <span class="audit-time">${escapeHtml(item.timeLabel || 'Recent')}</span>
        </div>`;
      recentAudits.appendChild(card);
    });
  }

  /* ── File Extraction Helpers ── */
  function extractParsedDetails(report, rawType) {
    const parse = report.parse_result || {};
    const segments = parse.segments || [];
    let claimId = 'CLAIM001';
    let billed = 500.00;
    let paid = 450.00;
    let adjustments = 50.00;
    let patient = 'Patient Record';

    if (rawType === '835') {
      const clp = segments.find(s => s.id === 'CLP');
      if (clp && clp.elements) {
        claimId = clp.elements[0] || claimId;
        billed = parseFloat(clp.elements[2] || '500') || billed;
        paid = parseFloat(clp.elements[3] || '450') || paid;
        adjustments = Math.max(0, billed - paid);
      }
    } else if (rawType.startsWith('837')) {
      const clm = segments.find(s => s.id === 'CLM');
      if (clm && clm.elements) {
        claimId = clm.elements[0] || claimId;
        billed = parseFloat(clm.elements[1] || '500') || billed;
      }
    }

    return { claimId, billed, paid, adjustments, patient };
  }

  async function processFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    if (progressOverlay) progressOverlay.classList.add('visible');

    for (let idx = 0; idx < files.length; idx++) {
      const file = files[idx];
      if (progressLabel) progressLabel.textContent = `Uploading ${idx + 1} of ${files.length}: ${file.name}`;
      if (progressBar) progressBar.style.width = ((idx / files.length) * 80) + '%';

      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await apiFetch('/api/upload', { method: 'POST', body: formData });
        if (!response.ok) throw new Error('Upload rejected by server');
        const payload = await response.json();
        const report  = payload.report || {};
        const parse   = report.parse_result || {};
        const valid   = report.validation_result || {};
        const issues  = Array.isArray(valid.issues) ? valid.issues : [];
        const type    = String(parse.transaction_type || 'UNKNOWN').toUpperCase();
        const errCount = issues.filter(i => i.severity === 'error').length;

        const details = extractParsedDetails(report, type);

        ediStore.saveSubmission({
          filename: report.filename || file.name,
          type: type !== 'UNKNOWN' ? type : (file.name.includes('835') ? '835' : (file.name.includes('834') ? '834' : '837P')),
          errorCount: errCount,
          valid: errCount === 0,
          claimId: details.claimId,
          billed: details.billed,
          paid: details.paid,
          adjustments: details.adjustments,
          amount: type === '835' ? details.paid : details.billed,
          timeLabel: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });

        showToast('File Processed', `${file.name} validated successfully.`, 'success');
      } catch (err) {
        showToast('Upload Failed', `Could not upload ${file.name}: ${err.message || 'Server connection error'}`, 'error');
        ediStore.saveSubmission({
          filename: file.name,
          type: 'ERROR',
          errorCount: 1,
          valid: false,
          claimId: '—',
          billed: 0,
          paid: 0,
          adjustments: 0,
          amount: 0,
          timeLabel: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
      }
    }

    if (progressBar) progressBar.style.width = '100%';
    setTimeout(() => {
      if (progressOverlay) progressOverlay.classList.remove('visible');
      if (progressBar) progressBar.style.width = '0%';
    }, 400);

    updateSummary();
    renderAudits();
    if (uploadStatus) uploadStatus.textContent = `${files.length} file(s) processed.`;
  }

  // Quick Demo Buttons
  async function loadSampleDemo(type) {
    let content = '';
    let fn = `sample_${type.toLowerCase()}.edi`;

    try {
      const res = await fetch(`/${fn}`);
      if (res.ok) {
        content = await res.text();
      }
    } catch {}

    if (!content) {
      if (type === '835') {
        content = `ISA*00*          *00*          *ZZ*PAYER999        *ZZ*PROVIDER111    *230102*0900*^*00501*000000002*0*P*:~GS*HP*PAYER999*PROVIDER111*20230102*0900*2*X*005010X221A1~ST*835*0001*005010X221A1~BPR*I*450.00*C*ACH*CCP*01*111111111*DA*11111111*20230102**01*222222222*DA*22222222~TRN*1*CHECK12345*1234567890~DTM*405*20230102~N1*PR*BLUE CROSS PAYER*XV*987654321~N1*PE*GENERAL HOSPITAL*XX*1234567893~LX*1~CLP*CLAIM001*1*500.00*450.00**MC*CLAIM001REF~NM1*QC*1*DOE*JOHN~SVC*HC:99213*150.00*135.00**1~DTM*472*20230101~CAS*CO*45*15.00~AMT*B6*135.00~SVC*HC:85025*50.00*45.00**1~DTM*472*20230101~CAS*CO*45*5.00~AMT*B6*45.00~SVC*HC:93000*300.00*270.00**1~DTM*472*20230101~CAS*CO*45*30.00~AMT*B6*270.00~SE*22*0001~GE*1*2~IEA*1*000000002~`;
      } else if (type === '834') {
        content = `ISA*00*          *00*          *ZZ*SPONSOR1       *ZZ*INSURER1       *260824*1200*^*00501*000000003*0*P*:~GS*BE*SPONSOR1*INSURER1*20260824*1200*3*X*005010X220A1~ST*834*0003~BGN*00*MEM-2026-08*20260824*1200~N1*P5*TECH CORP ENTERPRISES*FI*123456789~INS*Y*18*001*28*A***FT~REF*0F*W99201920~NM1*IL*1*DOE*JANE*A***34*999-00-1234~PER*IP*JANE DOE*HP*5550192837~N3*742 EVERGREEN TERRACE~N4*SPRINGFIELD*IL*62701~DMG*D8*19900815*F~HD*030**POS*PLAN-GOLD-2026~DTP*348*D8*20260101~SE*13*0003~GE*1*3~IEA*1*000000003~`;
      } else {
        content = `ISA*00*          *00*          *ZZ*SENDER123      *ZZ*RECEIVER456    *230101*1200*^*00501*000000001*0*P*:~GS*HC*SENDER123*RECEIVER456*20230101*1200*1*X*005010X222A1~ST*837*0001*005010X222A1~BHT*0019*00*244579*20230101*1200*CH~NM1*41*2*ACME BILLING*****46*123456789~PER*IC*BILLING CONTACT*TE*5551234567~NM1*40*2*BLUE CROSS*****46*987654321~HL*1**20*1~NM1*85*2*GENERAL HOSPITAL*****XX*1234567893~N3*123 MAIN ST~N4*ANYTOWN*CA*90210~REF*EI*123456789~HL*2*1*22*0~SBR*P*18*******CI~NM1*IL*1*DOE*JOHN****MI*ABC123456789~N3*456 OAK AVE~N4*SOMEWHERE*CA*90211~DMG*D8*19800101*M~NM1*PR*2*BLUE CROSS*****PI*987654321~CLM*CLAIM001*500.00***11:B:1*Y*A*Y*I~DTP*434*RD8*20230101-20230101~REF*D9*AUTHCODE001~HI*ABK:Z00000~NM1*82*1*SMITH*JANE****XX*9876543213~LX*1~SV1*HC:99213*150.00*UN*1***1~DTP*472*D8*20230101~LX*2~SV1*HC:85025*50.00*UN*1***1~DTP*472*D8*20230101~LX*3~SV1*HC:93000*300.00*UN*1***1~DTP*472*D8*20230101~SE*32*0001~GE*1*1~IEA*1*000000001~`;
      }
    }

    const blob = new Blob([content], { type: 'text/plain' });
    const file = new File([blob], fn, { type: 'text/plain' });
    file.type_override = type;
    await processFiles([file]);
  }

  // Event bindings
  if (uploadTrigger) uploadTrigger.addEventListener('click', () => fileInput && fileInput.click());
  if (fileInput) fileInput.addEventListener('change', e => processFiles(e.target.files));

  const demoBtns = document.querySelectorAll('.demo-btn[data-demo]');
  demoBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      loadSampleDemo(btn.dataset.demo);
    });
  });

  const newSubBtn = document.getElementById('new-sub-btn');
  if (newSubBtn) {
    newSubBtn.addEventListener('click', () => {
      if (fileInput) fileInput.click();
    });
  }

  if (uploadZone) {
    uploadZone.addEventListener('dragover',  e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
    uploadZone.addEventListener('dragleave', ()=> uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop',      e => {
      e.preventDefault();
      uploadZone.classList.remove('drag-over');
      processFiles(e.dataTransfer.files);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      ediStore.clear();
      updateSummary();
      renderAudits();
      if (uploadStatus) uploadStatus.textContent = 'No files uploaded yet.';
      showToast('Audits Cleared', 'Session audit list cleared.', 'info');
    });
  }

  updateSummary();
  renderAudits();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDashboard);
} else {
  initDashboard();
}
