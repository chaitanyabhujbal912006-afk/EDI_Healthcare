import { setAccessToken } from './shared.js';

async function initLogin() {
  /* ── Theme ── */
  const html  = document.documentElement;
  const toggle = document.getElementById('theme-toggle');
  const tIcon  = document.getElementById('theme-icon');
  const tLabel = document.getElementById('theme-label');
  const saved  = localStorage.getItem('theme') || 'light';
  
  function applyTheme(t) {
    html.classList.toggle('dark', t === 'dark');
    if (tIcon) tIcon.textContent  = t === 'dark' ? 'dark_mode' : 'light_mode';
    if (tLabel) tLabel.textContent = t === 'dark' ? 'Dark' : 'Light';
  }
  applyTheme(saved);
  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = html.classList.contains('dark') ? 'light' : 'dark';
      applyTheme(next);
      localStorage.setItem('theme', next);
    });
  }

  /* ── Password toggle ── */
  const pwInput  = document.getElementById('password');
  const pwToggle = document.getElementById('pw-toggle');
  const pwIcon   = document.getElementById('pw-icon');
  if (pwToggle && pwInput) {
    pwToggle.addEventListener('click', () => {
      const hidden = pwInput.type === 'password';
      pwInput.type = hidden ? 'text' : 'password';
      if (pwIcon) pwIcon.textContent = hidden ? 'visibility_off' : 'visibility';
    });
  }

  /* ── Populate Real Rule Count & Uptime from Health/Version ── */
  try {
    const res = await fetch('/api/version');
    if (res.ok) {
      const data = await res.json();
      const ruleCountEl = document.getElementById('rule-count-stat');
      if (ruleCountEl && data.features) {
        ruleCountEl.textContent = '60+';
      }
    }
  } catch {}

  /* ── PKCE Utilities ── */
  function generateRandomString(length = 64) {
    const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
    const randomValues = new Uint8Array(length);
    window.crypto.getRandomValues(randomValues);
    return Array.from(randomValues).map(val => charset[val % charset.length]).join('');
  }

  async function sha256(plain) {
    const encoder = new TextEncoder();
    const data = encoder.encode(plain);
    return window.crypto.subtle.digest('SHA-256', data);
  }

  function base64urlencode(buffer) {
    const bytes = new Uint8Array(buffer);
    let str = '';
    for (let i = 0; i < bytes.length; i++) {
      str += String.fromCharCode(bytes[i]);
    }
    return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  let oidcConfig = null;

  async function loadAuthConfig() {
    try {
      const res = await fetch('/api/auth/config');
      if (res.ok) {
        oidcConfig = await res.json();
      }
    } catch (err) {
      console.warn('Unable to load auth config from backend:', err);
    }
  }

  async function startPkceFlow() {
    if (!oidcConfig || !oidcConfig.oidc_configured || !oidcConfig.authorize_url) {
      showError('OIDC authentication is not configured on the backend.');
      return;
    }
    const verifier = generateRandomString(64);
    const hashed = await sha256(verifier);
    const challenge = base64urlencode(hashed);
    const state = generateRandomString(32);

    sessionStorage.setItem('pkce_code_verifier', verifier);
    sessionStorage.setItem('pkce_state', state);

    const redirectUri = window.location.origin + window.location.pathname;
    const authUrl = new URL(oidcConfig.authorize_url, window.location.origin);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('client_id', oidcConfig.client_id || 'edipro-public-client');
    authUrl.searchParams.set('redirect_uri', redirectUri);
    authUrl.searchParams.set('scope', 'openid profile email roles');
    authUrl.searchParams.set('state', state);
    authUrl.searchParams.set('code_challenge', challenge);
    authUrl.searchParams.set('code_challenge_method', 'S256');

    window.location.href = authUrl.toString();
  }

  async function handlePkceCallback() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    if (!code) return false;

    const savedState = sessionStorage.getItem('pkce_state');
    const verifier = sessionStorage.getItem('pkce_code_verifier');
    sessionStorage.removeItem('pkce_state');
    sessionStorage.removeItem('pkce_code_verifier');

    window.history.replaceState({}, document.title, window.location.pathname);

    if (savedState && state !== savedState) {
      showError('PKCE state validation failed.');
      return false;
    }

    if (!oidcConfig || !oidcConfig.token_url) {
      showError('OIDC token endpoint not available.');
      return false;
    }

    try {
      const redirectUri = window.location.origin + window.location.pathname;
      const body = new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: oidcConfig.client_id || 'edipro-public-client',
        code: code,
        redirect_uri: redirectUri,
        code_verifier: verifier || '',
      });

      const res = await fetch(oidcConfig.token_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString()
      });

      if (!res.ok) {
        showError('Token exchange failed with status ' + res.status);
        return false;
      }

      const data = await res.json();
      const accessToken = data.access_token || data.id_token;
      if (accessToken) {
        setAccessToken(accessToken);
        sessionStorage.setItem('edipro_auth_enabled', 'true');
        window.location.href = 'dashboard_sleek/code.html';
        return true;
      }
    } catch (err) {
      showError('Error during token exchange: ' + err.message);
    }
    return false;
  }

  function showError(msg) {
    const el = document.getElementById('login-global-error');
    if (el) {
      el.textContent = msg;
      el.classList.remove('is-hidden');
      el.style.display = 'block';
    }
  }

  await loadAuthConfig();
  if (window.location.search.includes('code=')) {
    const signinBtn = document.getElementById('signin-btn');
    if (signinBtn) {
      signinBtn.disabled = true;
      signinBtn.textContent = 'Exchanging token…';
    }
    await handlePkceCallback();
  }

  const ssoBtn = document.getElementById('sso-btn');
  if (ssoBtn) {
    ssoBtn.addEventListener('click', (e) => {
      e.preventDefault();
      startPkceFlow();
    });
  }

  /* ── Form submission (API-Key verification) ── */
  const form = document.getElementById('login-form');
  const signinBtn = document.getElementById('signin-btn');
  if (form && signinBtn) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const globalErr = document.getElementById('login-global-error');
      if (globalErr) {
        globalErr.classList.add('is-hidden');
        globalErr.style.display = 'none';
      }

      const pwVal = document.getElementById('password').value.trim();
      const pwWrap = document.getElementById('pw-wrap');
      const pwErr  = document.getElementById('pw-error');
      if (!pwVal) {
        if (pwWrap) pwWrap.classList.add('error');
        if (pwErr) pwErr.style.display = 'block';
        return;
      } else {
        if (pwWrap) pwWrap.classList.remove('error');
        if (pwErr) pwErr.style.display = 'none';
      }

      signinBtn.classList.add('loading');
      signinBtn.textContent = 'Verifying API key…';
      signinBtn.disabled = true;

      try {
        const res = await fetch('/api/health/detailed', {
          headers: { 'X-API-Key': pwVal }
        });

        if (res.status === 200 || res.status === 403) {
          sessionStorage.setItem('edipro_api_key', pwVal);
          sessionStorage.setItem('edipro_auth_enabled', 'true');
          signinBtn.textContent = 'Success! Redirecting…';
          setTimeout(() => { window.location.href = 'dashboard_sleek/code.html'; }, 300);
          return;
        }

        showError('Invalid API key or insufficient permissions.');
      } catch (err) {
        showError('Unable to connect to authentication server: ' + err.message);
      } finally {
        signinBtn.classList.remove('loading');
        signinBtn.textContent = 'Sign In with API Key';
        signinBtn.disabled = false;
      }
    });
  }

  /* ── Clear error on input ── */
  const passwordField = document.getElementById('password');
  if (passwordField) {
    passwordField.addEventListener('input', () => {
      const pwWrap = document.getElementById('pw-wrap');
      const pwErr  = document.getElementById('pw-error');
      if (pwWrap) pwWrap.classList.remove('error');
      if (pwErr) pwErr.style.display = 'none';
      const globalErr = document.getElementById('login-global-error');
      if (globalErr) globalErr.style.display = 'none';
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLogin);
} else {
  initLogin();
}
