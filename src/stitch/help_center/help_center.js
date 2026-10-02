import { apiFetch, escapeHtml } from '../shared.js';

function initHelpCenter() {
  // Bind FAQ accordions
  const faqHeaders = document.querySelectorAll('.faq-q');
  faqHeaders.forEach(header => {
    header.addEventListener('click', () => {
      const parent = header.parentElement;
      if (parent) parent.classList.toggle('open');
    });
  });

  // Topnav New Submission buttons
  const newSubBtns = document.querySelectorAll('.new-sub-btn');
  newSubBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      window.location.href = '../dashboard_sleek/code.html';
    });
  });

  // AI question button
  const chatSendBtn = document.getElementById('ai-chat-send');
  const chatInput = document.getElementById('ai-chat-input');
  const chatResponse = document.getElementById('ai-chat-response');

  async function handleAskAi() {
    if (!chatInput || !chatInput.value.trim() || !chatResponse) return;
    const question = chatInput.value.trim();
    chatResponse.style.display = 'block';
    chatResponse.innerHTML = '<span class="text-secondary">Checking validation rules and specifications…</span>';
    if (chatSendBtn) chatSendBtn.disabled = true;

    try {
      const res = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question })
      });

      if (res.ok) {
        const data = await res.json();
        chatResponse.innerHTML = `<div class="text-primary">${escapeHtml(data.response || data.reply || 'No response returned.')}</div>`;
      } else {
        chatResponse.innerHTML = `<span style="color:var(--text-secondary);">Rule guidance: X12 5010 transactions require strict loop hierarchy, envelope sequence numbers (SE01 matching segment count), and valid 10-digit NPIs verified via the Luhn algorithm.</span>`;
      }
    } catch {
      chatResponse.innerHTML = `<span style="color:var(--text-secondary);">Rule guidance: X12 5010 transactions require strict loop hierarchy, envelope sequence numbers (SE01 matching segment count), and valid 10-digit NPIs verified via the Luhn algorithm.</span>`;
    } finally {
      if (chatSendBtn) chatSendBtn.disabled = false;
    }
  }

  if (chatSendBtn) {
    chatSendBtn.addEventListener('click', handleAskAi);
  }
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAskAi();
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initHelpCenter);
} else {
  initHelpCenter();
}
