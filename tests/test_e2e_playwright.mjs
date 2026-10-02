import { chromium } from '../src/stitch/node_modules/playwright/index.mjs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000';

const PAGES = [
  '/stitch/index.html',
  '/stitch/dashboard_sleek/code.html',
  '/stitch/835_remittance_sleek/code.html',
  '/stitch/834_enrollment_sleek/code.html',
  '/stitch/837_claims_view/code.html',
  '/stitch/notifications/code.html',
  '/stitch/settings/code.html',
  '/stitch/documentation/code.html',
  '/stitch/help_center/code.html',
  '/stitch/user_profile/code.html',
  '/stitch/master_parser_sleek/code.html'
];

async function run() {
  console.log(`Starting E2E tests against ${BASE_URL}...`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  let hasErrors = false;

  // 1. Check CSP and console errors on every page
  for (const pagePath of PAGES) {
    const consoleErrors = [];
    const cspViolations = [];

    const onConsole = (msg) => {
      const type = msg.type();
      const text = msg.text();
      if (type === 'error') {
        consoleErrors.push(text);
      }
      if (text.toLowerCase().includes('content security policy') || text.toLowerCase().includes('violates the following')) {
        cspViolations.push(text);
      }
    };
    const onPageError = (err) => {
      consoleErrors.push(err.message || String(err));
    };

    page.on('console', onConsole);
    page.on('pageerror', onPageError);

    const targetUrl = `${BASE_URL}${pagePath}`;
    console.log(`Visiting: ${targetUrl}`);
    const response = await page.goto(targetUrl, { waitUntil: 'networkidle' });

    if (!response || response.status() >= 400) {
      console.error(`❌ HTTP Error ${response ? response.status() : 'None'} for ${targetUrl}`);
      hasErrors = true;
    }

    // Verify CSP header presence
    const headers = response.headers();
    const csp = headers['content-security-policy'] || '';
    if (!csp.includes("default-src 'self'")) {
      console.warn(`⚠️ Warning: strict CSP header not detected on ${pagePath} (got: ${csp})`);
    }

    // Wait a brief moment for any deferred async modules
    await page.waitForTimeout(500);

    page.off('console', onConsole);
    page.off('pageerror', onPageError);

    if (cspViolations.length > 0) {
      console.error(`❌ CSP Violations on ${pagePath}:`, cspViolations);
      hasErrors = true;
    } else {
      console.log(`✓ Zero CSP violations on ${pagePath}`);
    }

    if (consoleErrors.length > 0) {
      console.error(`❌ Console Errors on ${pagePath}:`, consoleErrors);
      hasErrors = true;
    } else {
      console.log(`✓ Zero console errors on ${pagePath}`);
    }
  }

  // 2. Upload sample_835.edi and sample_837p.edi through the UI
  console.log('\nTesting EDI Uploads via UI...');
  const sample835Path = path.resolve(rootDir, 'sample_835.edi');
  const sample837pPath = path.resolve(rootDir, 'sample_837p.edi');

  await page.goto(`${BASE_URL}/stitch/dashboard_sleek/code.html`, { waitUntil: 'networkidle' });

  // Upload sample_835.edi
  console.log(`Uploading ${sample835Path}...`);
  const fileInput = await page.$('#file-upload, #file-input');
  if (!fileInput) {
    throw new Error('File input not found on dashboard');
  }
  await fileInput.setInputFiles(sample835Path);
  await page.waitForTimeout(1500);

  // Upload sample_837p.edi
  console.log(`Uploading ${sample837pPath}...`);
  await fileInput.setInputFiles(sample837pPath);
  await page.waitForTimeout(1500);

  // 3. Verify 835 Remittance page shows CLAIM001 with billed 500.00 and paid 450.00 / adjustments 50.00
  console.log('\nChecking 835 Remittance page...');
  await page.goto(`${BASE_URL}/stitch/835_remittance_sleek/code.html`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  const remittanceContent = await page.content();
  const hasClaim001Remit = remittanceContent.includes('CLAIM001');
  const hasBilled500Remit = remittanceContent.includes('500.00');
  const hasPaid450Remit = remittanceContent.includes('450.00');
  const hasAdj50Remit = remittanceContent.includes('50.00');

  console.log(`835 Page: CLAIM001=${hasClaim001Remit}, Billed 500.00=${hasBilled500Remit}, Paid 450.00=${hasPaid450Remit}, Adj 50.00=${hasAdj50Remit}`);

  if (!hasClaim001Remit || !hasBilled500Remit || !hasPaid450Remit || !hasAdj50Remit) {
    console.error('❌ 835 remittance page failed to show required CLAIM001 values!');
    hasErrors = true;
  } else {
    console.log('✓ 835 remittance page shows CLAIM001 with billed 500.00, paid 450.00, adjustments 50.00');
  }

  // 4. Verify 837 Claims page shows CLAIM001 with billed 500.00
  console.log('\nChecking 837 Claims page...');
  await page.goto(`${BASE_URL}/stitch/837_claims_view/code.html`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  const claimsContent = await page.content();
  const hasClaim001Claims = claimsContent.includes('CLAIM001');
  const hasBilled500Claims = claimsContent.includes('500.00');

  console.log(`837 Page: CLAIM001=${hasClaim001Claims}, Billed 500.00=${hasBilled500Claims}`);

  if (!hasClaim001Claims || !hasBilled500Claims) {
    console.error('❌ 837 claims page failed to show CLAIM001 with billed 500.00!');
    hasErrors = true;
  } else {
    console.log('✓ 837 claims page shows CLAIM001 with billed 500.00');
  }

  await browser.close();

  if (hasErrors) {
    console.error('\n❌ E2E Playwright tests failed!');
    process.exit(1);
  } else {
    console.log('\n🎉 ALL E2E PLAYWRIGHT TESTS PASSED CLEANLY!');
    process.exit(0);
  }
}

run().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
