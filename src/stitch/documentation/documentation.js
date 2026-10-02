// documentation.js — Documentation Interactions

function initDocs() {
  const newSubBtns = document.querySelectorAll('.new-sub-btn');
  newSubBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      window.location.href = '../dashboard_sleek/code.html';
    });
  });

  // Table of contents link highlighting
  const tocLinks = document.querySelectorAll('.toc-item');
  const sections = Array.from(document.querySelectorAll('.doc-section'));

  window.addEventListener('scroll', () => {
    const scrollPos = window.scrollY + 100;
    for (let i = sections.length - 1; i >= 0; i--) {
      const sec = sections[i];
      if (sec.offsetTop <= scrollPos) {
        tocLinks.forEach(l => l.classList.remove('active'));
        const activeLink = document.querySelector(`.toc-item[href="#${sec.id}"]`);
        if (activeLink) activeLink.classList.add('active');
        break;
      }
    }
  }, { passive: true });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDocs);
} else {
  initDocs();
}
