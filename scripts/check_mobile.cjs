/* Read-only mobile checks. Run against an isolated app with seeded data:
 * node scripts/check_mobile.cjs http://127.0.0.1:8013 .tmp_audit_cookie.json .tmp_mobile_review
 * Requires Playwright, Chrome and Playwright WebKit. Session JSON is optional;
 * without it only public pages are checked. Never prints the session value.
 */
const { chromium, webkit } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const base = (process.argv[2] || 'http://127.0.0.1:8013').replace(/\/$/, '');
const sessionFile = process.argv[3];
const interactionsOnly = process.env.MOBILE_INTERACTIONS_ONLY === '1';
const output = path.resolve(process.argv[4] || '.tmp_mobile_review');
fs.mkdirSync(output, { recursive: true });
const publicPaths = ['/', '/pricing', '/auth/login', '/auth/register', '/help', '/blog', '/support', '/changelog', '/changelog/mobile-dashboard-and-site-polish', '/pdd/', '/qa/', '/lessio/', '/lessio/blog'];
const appPaths = ['/app/today', '/app/inbox', '/app/upcoming', '/app/calendar?view=week', '/app/settings', '/app/stats', '/app/activity', '/app/labels', '/app/team', '/app/my-data', '/miniapp/', '/miniapp/calendar', '/qa/ask'];
const widths = [320, 360, 390, 430, 768, 1024, 1440];
let report = { checks: [], errors: [], failures: [] };

(async () => {
  for (const engine of ['chromium', 'webkit']) {
    const browser = await (engine === 'webkit' ? webkit : chromium).launch(engine === 'webkit' ? { headless: true } : { channel: 'chrome', headless: true });
    try {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, reducedMotion: 'reduce', serviceWorkers: 'block' });
      // Simulate unavailable external CDNs. Essential UI assets must be local.
      await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin ? route.continue() : route.abort());
      const page = await context.newPage();
      page.on('pageerror', error => report.errors.push({ engine, url: page.url(), error: error.message }));
      async function check(name, operation) {
        try { await operation(); report.checks.push({ engine, name }); }
        catch (error) { report.failures.push({ engine, name, error: error.message }); console.log('FAIL', engine, name, error.message); }
      }
      async function layout(url, sizes = widths) {
        const response = await page.goto(base + url, { waitUntil: 'domcontentloaded' });
        assert.equal(response.status(), 200, `${url} returns ${response.status()}`);
        await page.evaluate(() => document.fonts.ready);
        await page.waitForTimeout(250);
        for (const width of sizes) {
          await page.setViewportSize({ width, height: width === 1024 ? 768 : 844 });
          await page.waitForTimeout(500);
          await check(`${url} at ${width}px`, async () => {
            const dimensions = await page.evaluate(() => {
              const clipped = [...document.querySelectorAll('main .card, main form')].filter(container => {
                if (!container.clientWidth || container.scrollWidth <= container.clientWidth + 3 || ['auto','scroll'].includes(getComputedStyle(container).overflowX)) return false;
                const bounds = container.getBoundingClientRect();
                return [...container.querySelectorAll('*')].some(child => {
                  if (!child.textContent.trim()) return false;
                  const rect = child.getBoundingClientRect();
                  if (!rect.width || rect.right <= bounds.right + 3) return false;
                  for (let node = child; node && node !== container; node = node.parentElement) {
                    const style = getComputedStyle(node);
                    if (['absolute','fixed'].includes(style.position) || ['auto','scroll'].includes(style.overflowX)) return false;
                  }
                  return true;
                });
              }).map(e => e.className);
              return { width: innerWidth, body: document.documentElement.scrollWidth, main: document.querySelector('main')?.clientWidth, clipped };
            });
            assert.ok(dimensions.body <= width + 2, JSON.stringify(dimensions));
            assert.ok(!dimensions.main || dimensions.main >= Math.min(240, width - 32), JSON.stringify(dimensions));
            assert.equal(dimensions.clipped.length, 0, JSON.stringify(dimensions.clipped));
          });
        }
      }
      if (!interactionsOnly) {
        for (const url of publicPaths) { console.log(engine, url); await layout(url); }
        await page.goto(base + '/blog');
        const article = await page.locator('a[href^="/blog/"]').evaluateAll(links => links.map(a => a.getAttribute('href')).find(href => /^\/blog\/[^/]+$/.test(href) && !href.includes('feed.')));
        if (article) await layout(article);
      }
      if (sessionFile) {
        const session = JSON.parse(fs.readFileSync(sessionFile, 'utf8')).session;
        await context.addCookies([{ name: 'session', value: session, url: base }]);
        if (!interactionsOnly) for (const url of appPaths) { console.log(engine, url); await layout(url); }
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto(base + '/app/root');
        await page.waitForTimeout(350);
        const nav = page.getByRole('navigation', { name: 'Разделы панели владельца' }).last();
        await check('Root opens on overview', async () => {
          assert.ok(await page.locator('#overview').isVisible());
          assert.ok(!await page.locator('#billing').isVisible());
        });
        for (const [id, title] of [['overview', 'Обзор'], ['billing', 'Платежи'], ['users', 'Люди'], ['support', 'Поддержка']]) {
          await nav.getByRole('link', { name: title, exact: true }).click();
          await page.waitForTimeout(200);
          for (const width of [320, 390, 768, 844]) {
            await page.setViewportSize({ width, height: width === 844 ? 390 : 844 });
            await page.waitForTimeout(180);
            await check(`Root ${id} at ${width}px`, async () => {
              assert.ok(await page.locator('#' + id).isVisible());
              assert.equal(await nav.getByRole('link', { name: title, exact: true }).getAttribute('aria-current'), 'page');
              assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
            });
          }
          await page.setViewportSize({ width: 390, height: 844 });
          await page.screenshot({ path: path.join(output, `${engine}-root-${id}.png`), fullPage: false });
        }
        await check('Saving an admin note preserves an unsent reply', async () => {
          const note = page.getByRole('textbox', { name: 'Заметка администратора', exact: true }).first();
          const reply = page.getByRole('textbox', { name: 'Ответ автору обращения', exact: true }).first();
          if (!(await note.count())) return;
          let payload;
          const noteText = `Mobile audit note ${engine} ${Date.now()}`;
          await context.route('**/api/admin/complaints/*', async route => {
            assert.equal(route.request().method(), 'PATCH');
            payload = route.request().postDataJSON();
            await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
          });
          await reply.fill('Draft retained during note save');
          await note.fill(noteText);
          await reply.focus();
          await page.waitForFunction(text => [...document.querySelectorAll('[data-original-note]')].some(e => e.dataset.originalNote === text), noteText);
          assert.equal(payload.admin_note, noteText);
          assert.equal(await reply.inputValue(), 'Draft retained during note save');
          await reply.blur();
          await context.unroute('**/api/admin/complaints/*');
        });
        await page.locator('#support h2').first().click();
        await nav.getByRole('link', { name: 'Платежи', exact: true }).click();
        await page.locator('#billing').waitFor({ state: 'visible' });
        await check('Mobile ledger uses cards and collapsed filters', async () => {
          assert.ok(await page.locator('.payment-card').first().isVisible());
          assert.ok(!await page.locator('#billing table').isVisible());
          assert.ok(!await page.locator('#billing .owner-filters').evaluate(e => e.open));
          assert.equal(await page.locator('.payment-card').count(), 10);
        });
        await page.locator('#billing input[name="billing_q"]').fill('very-long-buyer');
        await page.locator('#billing button[type="submit"]').first().click();
        await page.waitForURL('**/app/root?**');
        await page.waitForTimeout(250);
        await check('Search keeps mobile payment screen and CSV filters', async () => {
          assert.ok(await page.locator('#billing').isVisible());
          assert.equal(await page.locator('#billing input[name="billing_q"]').inputValue(), 'very-long-buyer');
          const href = await page.getByRole('link', { name: 'Скачать платежи в CSV' }).getAttribute('href');
          assert.ok(href.includes('q=very-long-buyer'));
          const csv = await context.request.get(base + href);
          assert.equal(csv.status(), 200);
          assert.ok(csv.headers()['content-type'].includes('text/csv'));
        });
        await page.locator('#billing .owner-filters > summary').click();
        await page.locator('select[name="billing_status"]').selectOption('pending');
        await page.locator('#billing button[type="submit"]').last().click();
        await page.waitForURL('**billing_status=pending**');
        await check('Advanced filters submit while preserving search', async () => {
          assert.equal(await page.locator('#billing input[name="billing_q"]').inputValue(), 'very-long-buyer');
          assert.equal(await page.locator('select[name="billing_status"]').inputValue(), 'pending');
          assert.equal(await page.locator('.payment-card').count(), 10);
        });
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.waitForFunction(() => !Alpine.$data(document.querySelector('[x-data][class="min-h-screen flex"]')).mobile);
        await page.locator('#overview').waitFor({state:'visible'});
        await check('Desktop keeps all sections and table', async () => {
          for (const id of ['overview', 'billing', 'users', 'support']) assert.ok(await page.locator('#' + id).isVisible());
          assert.ok(await page.locator('#billing table').isVisible());
          assert.ok(!await page.locator('.payment-card').first().isVisible());
        });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto(base + '/app/inbox');
        await page.waitForTimeout(350);
        if (!(await page.locator('.task-actions:visible').count()) && await page.locator('#completed-block').count()) {
          await page.locator('#completed-block > button').click();
        }
        await check('Task menu is visible without hover', async () => {
          const button = page.locator('.task-actions:visible').first();
          assert.equal(await button.evaluate(e => getComputedStyle(e).opacity), '1');
          assert.ok((await button.boundingBox()).height >= 44);
          await button.click();
          assert.ok(await page.locator('#task-ctx-menu').isVisible());
          await page.keyboard.press('Escape');
        });
        await check('Task details fit the phone and close without mutation', async () => {
          await page.locator('.task-title > button:visible').first().click();
          const dialog = page.getByRole('dialog', { name: 'Подробности задачи' });
          await dialog.waitFor({ state: 'visible' });
          const rect = await dialog.boundingBox();
          assert.ok(rect && rect.width <= 390 && rect.x >= 0, JSON.stringify(rect));
          assert.ok((await dialog.getByRole('button', { name: 'Закрыть панель' }).boundingBox()).height >= 44);
          await dialog.getByRole('button', { name: 'Закрыть панель' }).click();
          await dialog.waitFor({ state: 'detached' });
        });
        await page.getByRole('button', { name: 'Уведомления', exact: true }).click();
        await check('Notification panel stays in phone viewport', async () => {
          const rect = await page.locator('.app-topbar .card').boundingBox();
          assert.ok(rect && rect.x >= 0 && rect.x + rect.width <= 392, JSON.stringify(rect));
        });
        await page.goto(base + '/app/root#billing');
        await page.waitForTimeout(250);
        await page.getByRole('button', { name: /Сменить тему/ }).click();
        await page.getByRole('button', { name: /Сменить тему/ }).click();
        await page.screenshot({ path: path.join(output, `${engine}-root-theme.png`) });
      }
      await context.close();
    } finally { await browser.close(); }
  }
  assert.equal(report.errors.length, 0, JSON.stringify(report.errors));
})().catch(error => report.failures.push({ error: error.message })).finally(() => {
  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ checks: report.checks.length, failures: report.failures, errors: report.errors }, null, 2));
  process.exitCode = report.failures.length || report.errors.length ? 1 : 0;
});
