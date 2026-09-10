import { test, expect } from '@playwright/test';
import { matches } from '../../src/lib/filter';

test('built homepage and subpath resources load without errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', r => { if (r.url().startsWith('http://127.0.0.1') && r.status() >= 400) errors.push(r.url()); });
  await page.goto('./');
  const total = (await (await page.request.get('search-index.json')).json()).length;
  await expect(page.getByRole('heading', { level: 1 })).toContainText('理解评测');
  await expect(page.locator('#result-count')).toHaveText(`显示 ${total} / ${total} 篇论文`);
  await expect(page.locator('.paper-card')).toHaveCount(total);
  await expect(page.locator('body')).toContainText('最近成功部署');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});
test('search title, acronym and Chinese summary, combine filters and clear', async ({ page }) => {
  await page.goto('./');
  const papers = await (await page.request.get('search-index.json')).json();
  const total = papers.length;
  await expect(page.locator('#result-count')).toHaveText(`显示 ${total} / ${total} 篇论文`);
  const search = page.getByRole('searchbox', { name: '搜索论文' });
  for (const q of ['MMLU', 'Massive Multitask', '57 个学科']) {
    await search.fill(q);
    await expect(page.locator('.paper-card:visible')).toHaveCount(papers.filter((p: any) => matches(p, { q })).length);
    await expect(page.locator('[data-paper-id="arxiv-2009.03300"]')).toBeVisible();
  }
  await search.fill('');
  await page.locator('[name=target]').selectOption('agent');
  await page.locator('[name=scenario]').selectOption('web');
  await page.locator('[name=capability]').selectOption('tool-use');
  await page.locator('[name=review]').selectOption('source_verified');
  await page.locator('[name=reproduction]').selectOption('official_docs_unrun');
  const filtered = papers.filter((p: any) => matches(p, { target: 'agent', scenario: 'web', capability: 'tool-use', review: 'source_verified', reproduction: 'official_docs_unrun' })).length;
  await expect(page.locator('.paper-card:visible')).toHaveCount(filtered);
  await expect(page.locator('[data-paper-id="arxiv-2307.13854"]')).toBeVisible();
  await page.reload();
  await expect(page.locator('.paper-card:visible')).toHaveCount(filtered);
  await search.fill('no-match-test-fixture-987654321');
  await expect(page.locator('#empty-state')).toBeVisible();
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.locator('.paper-card:visible')).toHaveCount(total);
});
test('all detail pages exist and show distinct dates and source scope', async ({ page, request }) => {
  const response = await request.get('search-index.json');
  for (const p of await response.json()) {
    const detail = await request.get(`papers/${p.id}/`);
    expect(detail.status()).toBe(200);
    const html = await detail.text();
    expect(html).toContain('论文首发日期');
    expect(html).toContain('论文版本更新时间');
    expect(html).toContain('本站核查日期');
    expect(html).toContain('人工运行记录');
  }
  await page.goto('papers/arxiv-2311.12983/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('GAIA: a benchmark for General AI Assistants');
  await expect(page.locator('body')).toContainText('官方代码：待核查');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole('link', { name: '返回论文索引' }).click();
  await expect(page).toHaveURL(/\/benchmark-atlas\/#catalog$/);
});
test('taxonomy and rules remain navigable on mobile', async ({ page }) => {
  await page.goto('./');
  await page.getByRole('navigation').getByRole('link', { name: '分类说明' }).click();
  await expect(page.getByRole('heading', { name: '论文贡献类型' })).toBeVisible();
  await expect(page.locator('body')).toContainText('仅使用 Benchmark');
  await page.getByRole('navigation').getByRole('link', { name: '收录规则' }).click();
  await expect(page.locator('body')).toContainText('不使用 MDX');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
