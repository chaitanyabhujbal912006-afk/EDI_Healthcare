/* shared.js — EdiPro shared page init: theme, sidebar, command palette, toast system */

function showToast(title, message = '', type = 'info', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
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
      <div class="toast-title">${title}</div>
      ${message ? `<div class="toast-message">${message}</div>` : ''}
    </div>
    <button class="toast-close" aria-label="Close">&times;</button>
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

function initCommandPalette() {
  if (document.getElementById('cmd-palette-backdrop')) return;

  const backdrop = document.createElement('div');
  backdrop.id = 'cmd-palette-backdrop';
  backdrop.className = 'cmd-palette-backdrop';
  
  backdrop.innerHTML = `
    <div class="cmd-palette-modal" onclick="event.stopPropagation()">
      <div class="cmd-palette-header">
        <span class="ms">search</span>
        <input type="text" id="cmd-palette-input" placeholder="Type a command or search pages (e.g., 837, Claims, Settings)..." autocomplete="off" />
        <span class="kbd">ESC</span>
      </div>
      <div class="cmd-palette-results" id="cmd-palette-results">
        <div class="cmd-group-label">Quick Navigation</div>
        <div class="cmd-item" data-url="../dashboard_sleek/code.html"><span class="ms">dashboard</span><span>Dashboard Overview</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../master_parser_sleek/code.html"><span class="ms">analytics</span><span>Master EDI Parser</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../837_claims_view/code.html"><span class="ms">description</span><span>837 Professional Claims</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../835_remittance_sleek/code.html"><span class="ms">payments</span><span>835 Payment Remittance</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../834_enrollment_sleek/code.html"><span class="ms">group_add</span><span>834 Member Enrollment</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../notifications/code.html"><span class="ms">notifications</span><span>Notification Center</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../settings/code.html"><span class="ms">settings</span><span>System Settings & Rules</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../user_profile/code.html"><span class="ms">person</span><span>User Profile & API Keys</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../documentation/code.html"><span class="ms">menu_book</span><span>API & Schema Documentation</span><span class="kbd">Go</span></div>
        <div class="cmd-item" data-url="../help_center/code.html"><span class="ms">help</span><span>Support & Help Center</span><span class="kbd">Go</span></div>
      </div>
    </div>
  `;

  document.body.appendChild(backdrop);

  const input = backdrop.querySelector('#cmd-palette-input');
  const results = backdrop.querySelector('#cmd-palette-results');

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
}

function openCommandPalette() {
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

function closeCommandPalette() {
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

function getSampleEdiContent(type = '837P') {
  if (type === '837P') {
    return `ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*^*00501*000000001*0*P*:~
GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*3920392*20260824*1030*CH~
NM1*41*2*AETHER HEALTH SERVICES*****46*993029101~
PER*IC*EDI DEPT*TE*8005550199~
NM1*40*2*BLUE CROSS BLUE SHIELD*****46*BCBS10293~
HL*1**20*1~
NM1*85*2*METRO HEALTHCARE CLINIC*****XX*1928374650~
N3*100 MEDICAL CENTER BLVD*SUITE 400~
N4*AUSTIN*TX*78701~
REF*EI*948302910~
HL*2*1*22*0~
SBR*P*18*******CI~
NM1*IL*1*SMITH*JOHN*M***MI*W99201920~
N3*452 OAK PARK AVE~
N4*AUSTIN*TX*78704~
DMG*D8*19850412*M~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BCBS10293~
CLM*CLM-99401*1250.00***11:B:1*Y*A*Y*Y~
HI*BK:F329*BF:E119~
LX*1~
SV1*HC:99214*250.00*UN*1***1~
DTP*472*D8*20260820~
LX*2~
SV1*HC:80053*1000.00*UN*1***1~
DTP*472*D8*20260820~
SE*25*0001~
GE*1*1~
IEA*1*000000001~`;
  } else if (type === '835') {
    return `ISA*00*          *00*          *ZZ*PAYER1         *ZZ*PROVIDER1      *260824*1145*^*00501*000000002*0*P*:~
GS*HP*PAYER1*PROVIDER1*20260824*1145*2*X*005010X221A1~
ST*835*0002~
BPR*I*1450.00*C*ACH*CTX*01*011000015*DA*998019283*1992019203**20260824~
TRN*1*9920192849*1992019203~
REF*EV*4920192~
DTM*405*20260824~
N1*PR*BLUE SHIELD HEALTHCARE~
N1*PE*METRO HEALTHCARE CLINIC*XX*1928374650~
LX*1~
CLP*CLM-99401*1*1250.00*1100.00*150.00*MC*99401827361*11~
NM1*QC*1*SMITH*JOHN*M***MI*W99201920~
SVC*HC:99214*250.00*220.00~
CAS*CO*45*30.00~
DTM*472*20260820~
SVC*HC:80053*1000.00*880.00~
CAS*CO*45*120.00~
DTM*472*20260820~
SE*18*0002~
GE*1*2~
IEA*1*000000002~`;
  } else if (type === '834') {
    return `ISA*00*          *00*          *ZZ*SPONSOR1       *ZZ*INSURER1       *260824*1200*^*00501*000000003*0*P*:~
GS*BE*SPONSOR1*INSURER1*20260824*1200*3*X*005010X220A1~
ST*834*0003~
BGN*00*MEM-2026-08*20260824*1200~
N1*P5*TECH CORP ENTERPRISES*FI*123456789~
INS*Y*18*001*28*A***FT~
REF*0F*W99201920~
NM1*IL*1*DOE*JANE*A***34*999-00-1234~
PER*IP*JANE DOE*HP*5550192837~
N3*742 EVERGREEN TERRACE~
N4*SPRINGFIELD*IL*62701~
DMG*D8*19900815*F~
HD*030**POS*PLAN-GOLD-2026~
DTP*348*D8*20260101~
SE*13*0003~
GE*1*3~
IEA*1*000000003~`;
  }
  return '';
}

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

  /* ---- Highlight Navigation ---- */
  highlightActiveNav();

  /* ---- Attach Command Palette Triggers ---- */
  const searchInputs = document.querySelectorAll('.search-trigger, .nav-search');
  searchInputs.forEach(input => {
    input.addEventListener('click', (e) => {
      e.preventDefault();
      openCommandPalette();
    });
  });
}

function readSubmissions() {
  try { const p = JSON.parse(localStorage.getItem('ediSubmissions') || '[]'); return Array.isArray(p) ? p : []; }
  catch { return []; }
}

function saveSubmission(sub) {
  const current = readSubmissions();
  current.unshift(sub);
  localStorage.setItem('ediSubmissions', JSON.stringify(current.slice(0, 50)));
}

// Auto init on DOM load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPage);
} else {
  initPage();
}

// Export functions to global scope
window.EdiPro = {
  showToast,
  openCommandPalette,
  closeCommandPalette,
  getSampleEdiContent,
  readSubmissions,
  saveSubmission
};
window.showToast = showToast;
window.openCommandPalette = openCommandPalette;
window.getSampleEdiContent = getSampleEdiContent;

