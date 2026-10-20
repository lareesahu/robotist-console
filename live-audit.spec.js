const { test, expect } = require('@playwright/test');
const fs = require('fs');

const ORIGIN = 'https://www.robotist.com.au';
const viewports = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 1024, height: 768 },
  mobile: { width: 390, height: 844 },
};

function canonical(raw) {
  const url = new URL(raw, ORIGIN);
  if (url.origin !== ORIGIN) return null;
  url.hash = '';
  url.search = '';
  return url.href;
}

async function scrollFullPage(page) {
  await page.evaluate(async () => {
    const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
    const step = Math.max(320, Math.floor(innerHeight * 0.8));
    for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
      scrollTo(0, y);
      await pause(20);
    }
    scrollTo(0, document.documentElement.scrollHeight);
    await pause(60);
  });
}

async function gotoWithRetry(page, url) {
  let lastError;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    } catch (error) {
      lastError = error;
      await page.waitForTimeout(500);
    }
  }
  throw lastError;
}

test('production crawl and responsive usability audit', async ({ browser, request }) => {
  test.setTimeout(600000);
  const crawlPage = await browser.newPage({ viewport: viewports.desktop });
  const queue = [`${ORIGIN}/`];
  const urls = [];
  const seen = new Set();
  const linkFailures = [];

  while (queue.length && urls.length < 60) {
    const url = queue.shift();
    if (seen.has(url)) continue;
    seen.add(url);
    const response = await gotoWithRetry(crawlPage, url);
    if (!response || response.status() >= 400) {
      linkFailures.push({ url, status: response?.status() || 0 });
      continue;
    }
    urls.push(url);
    const links = await crawlPage.locator('a[href]').evaluateAll((els) => els.map(a => a.href));
    for (const href of links) {
      const clean = canonical(href);
      if (clean && !seen.has(clean) && !queue.includes(clean)) queue.push(clean);
    }
  }
  await crawlPage.close();

  const issues = [];
  const consoleErrors = [];
  const page = await browser.newPage({ viewport: viewports.desktop });
  let currentDevice = 'desktop';
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push({ device: currentDevice, url: page.url(), text: msg.text() });
  });
  for (const url of urls) {
    const response = await gotoWithRetry(page, url);
    for (const [device, viewport] of Object.entries(viewports)) {
      currentDevice = device;
      await page.setViewportSize(viewport);
      await scrollFullPage(page);
      const result = await page.evaluate(() => {
        const visible = el => {
          const r = el.getBoundingClientRect();
          const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        };
        const smallPriorityControls = [...document.querySelectorAll('.nav-toggle, .nav-cta, .btn-primary, .btn-secondary, .btn-ghost, .filter-pill, .inquiry-link')]
          .filter(visible)
          .map(el => {
            const r = el.getBoundingClientRect();
            return { text: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 60), width: Math.round(r.width), height: Math.round(r.height) };
          })
          .filter(x => x.width < 44 || x.height < 44);
        return {
          title: document.title,
          h1: document.querySelector('h1')?.textContent.trim() || '',
          horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
          brokenImages: [...document.images].filter(img => img.complete && img.naturalWidth === 0).map(img => img.currentSrc || img.src),
          deadHashLinks: [...document.querySelectorAll('a[href="#"]')].length,
          unnamedLinks: [...document.querySelectorAll('a')].filter(a => visible(a) && !((a.getAttribute('aria-label') || a.textContent || '').trim()) && !a.querySelector('img[alt]')).length,
          duplicateIds: [...document.querySelectorAll('[id]')].map(el => el.id).filter((id, i, all) => all.indexOf(id) !== i),
          smallPriorityControls,
        };
      });
      if (!response || response.status() >= 400) issues.push({ device, url, type: 'status', value: response?.status() || 0 });
      for (const [type, value] of Object.entries(result)) {
        if (['title', 'h1'].includes(type)) {
          if (!value) issues.push({ device, url, type, value });
        } else if (Array.isArray(value) ? value.length : value) {
          issues.push({ device, url, type, value });
        }
      }
    }
  }
  await page.close();

  const mobile = await browser.newPage({ viewport: viewports.mobile });
  await gotoWithRetry(mobile, `${ORIGIN}/`);
  await mobile.locator('.nav-toggle').click();
  const menuVisible = await mobile.locator('.nav-links').evaluate(el => getComputedStyle(el).display !== 'none');
  const pills = mobile.locator('.filter-pill');
  let filterWorked = false;
  if (await pills.count()) {
    await pills.nth(Math.min(1, (await pills.count()) - 1)).click();
    filterWorked = await pills.nth(Math.min(1, (await pills.count()) - 1)).getAttribute('class').then(c => c.includes('active'));
  }
  await mobile.locator('a:has-text("Get Started")').first().click();
  const homeModalVisible = await mobile.locator('#inquiryModal').isVisible().catch(() => false);
  await mobile.close();

  const product = await browser.newPage({ viewport: viewports.mobile });
  await gotoWithRetry(product, `${ORIGIN}/products/fourier-gr-3.html`);
  await product.locator('a:has-text("Inquire Now")').first().click();
  const productModalVisible = await product.locator('#inquiryModal').isVisible().catch(() => false);
  await product.close();

  const contact = await browser.newPage({ viewport: viewports.tablet });
  await gotoWithRetry(contact, `${ORIGIN}/contact.html`);
  const fields = contact.locator('input, textarea, select');
  let contactFieldsUsable = (await fields.count()) > 0;
  for (let i = 0; i < await fields.count(); i++) {
    const field = fields.nth(i);
    if (!(await field.isVisible()) || !(await field.isEnabled())) continue;
    const tag = await field.evaluate(el => el.tagName);
    const type = await field.getAttribute('type');
    if (tag === 'SELECT') await field.selectOption({ index: Math.min(1, (await field.locator('option').count()) - 1) }).catch(() => {});
    else if (!['submit', 'button', 'checkbox', 'radio'].includes(type || '')) await field.fill(type === 'email' ? 'audit@example.com' : 'Audit test');
  }
  await contact.close();

  const report = {
    pagesDiscovered: urls.length,
    responsivePageChecks: urls.length * Object.keys(viewports).length,
    viewports,
    linkFailures,
    issues,
    consoleErrors,
    interactions: { menuVisible, filterWorked, homeModalVisible, productModalVisible, contactFieldsUsable },
    urls,
  };
  fs.writeFileSync('live-audit-report.json', JSON.stringify(report, null, 2));

  expect(linkFailures).toEqual([]);
  expect(issues).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(report.interactions).toEqual({ menuVisible: true, filterWorked: true, homeModalVisible: true, productModalVisible: true, contactFieldsUsable: true });
});
