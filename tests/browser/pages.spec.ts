import { test, expect } from '@playwright/test';
import { matches } from '../../src/lib/filter';

test('built homepage and subpath resources load without errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', r => { if (r.url().startsWith('http://127.0.0.1') && r.status() >= 400) errors.push(r.url()); });
  await page.goto('./?review=needs_review&reproduction=minimal_verified');
  const total = (await (await page.request.get('search-index.json')).json()).length;
  await expect(page.getByRole('heading', { level: 1 })).toContainText('理解评测');
  await expect(page.locator('#result-count')).toHaveText(`显示 ${total} / ${total} 篇论文`);
  await expect(page.locator('.paper-card')).toHaveCount(total);
  await expect(page.locator('[name=review], [name=reproduction], .status, .repro-status')).toHaveCount(0);
  await expect(page.locator('#filters select')).toHaveCount(4);
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
  for (const q of ['SWE-bench', 'Real-World GitHub Issues', '2,294']) {
    await search.fill(q);
    await expect(page.locator('.paper-card:visible')).toHaveCount(papers.filter((p: any) => matches(p, { q })).length);
    await expect(page.locator('[data-paper-id="arxiv-2310.06770"]')).toBeVisible();
  }
  await search.fill('');
  await page.locator('[name=target]').selectOption('agent');
  await page.locator('[name=scenario]').selectOption('web');
  await page.locator('[name=capability]').selectOption('tool-use');
  const filtered = papers.filter((p: any) => matches(p, { target: 'agent', scenario: 'web', capability: 'tool-use' })).length;
  await expect(page.locator('.paper-card:visible')).toHaveCount(filtered);
  await expect(page.locator('[data-paper-id="arxiv-2307.13854"]')).toBeVisible();
  await page.reload();
  await expect(page.locator('.paper-card:visible')).toHaveCount(filtered);
  await search.fill('no-match-test-fixture-987654321');
  await expect(page.locator('#empty-state')).toBeVisible();
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.locator('.paper-card:visible')).toHaveCount(total);
});
test('detail pages show summaries, sourced methods and distinct paper dates', async ({ page, request }) => {
  const response = await request.get('search-index.json');
  for (const p of await response.json()) {
    const detail = await request.get(`papers/${p.id}/`);
    expect(detail.status()).toBe(200);
    const html = await detail.text();
    expect(html).toContain('论文首发日期');
    expect(html).toContain('论文版本更新时间');
    expect(html).toContain('中文简介');
    expect(html).toContain('复现方法');
    expect(html).toContain('来源与材料范围');
    expect(html).not.toContain('本站核查日期');
    expect(html).not.toContain('人工审核人');
    expect(html).not.toContain('class="repro-status"');
  }
  await page.goto('papers/arxiv-2310.06770/');
  await expect(page.locator('#reproduction .command code')).toContainText('swebench eval');
  await expect(page.locator('#reproduction .command a')).toHaveAttribute('href', /github\.com\/SWE-bench\/SWE-bench\/blob\/[a-f0-9]{40}\//);
  await expect(page.locator('#reproduction .method-links a')).toBeVisible();
  await page.goto('papers/arxiv-2311.12983/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('GAIA: a benchmark for General AI Assistants');
  await expect(page.locator('body')).toContainText('暂未提供独立代码入口');
  await expect(page.locator('#reproduction')).toContainText('暂未整理可引用的官方运行步骤');
  await expect(page.locator('#reproduction pre')).toHaveCount(0);
  await expect(page.locator('.status, .repro-status')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole('link', { name: '返回论文索引' }).click();
  await expect(page).toHaveURL(/\/benchmark-atlas\/#catalog$/);
});

test('removed years and medical entries have no index entries or generated detail routes', async ({ request }) => {
  const papers = await (await request.get('search-index.json')).json();
  expect(papers.every((p: any) => p.publishedAt >= '2023-01-01')).toBeTruthy();
  for (const id of ['arxiv-2009.03300', 'arxiv-2103.03874', 'arxiv-2107.03374', 'arxiv-2110.14168', 'arxiv-2211.09110', 'arxiv-2609.10055']) {
    expect(papers.some((p: any) => p.id === id)).toBeFalsy();
    expect((await request.get(`papers/${id}/`)).status()).toBe(404);
  }
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

test('all entries share date sorting and direct method links without status fields', async ({ page }) => {
  await page.goto('./');
  const papers = await (await page.request.get('search-index.json')).json();
  for (const p of papers) {
    expect(p).not.toHaveProperty('review');
    expect(p).not.toHaveProperty('reproduction');
  }
  await expect(page.locator('#paper-grid > .paper-card')).toHaveCount(papers.length);
  await expect(page.locator('#automatic-section')).toHaveCount(0);
  await expect(page.locator('[name=sort]')).toHaveValue('published');
  const newest = papers.reduce((a: any, b: any) => (a.publishedAt || '') > (b.publishedAt || '') ? a : b).publishedAt;
  const firstId = await page.locator('#paper-grid > .paper-card').first().getAttribute('data-paper-id');
  expect(papers.find((p: any) => p.id === firstId).publishedAt).toBe(newest);
  for (const [order, field] of [['added', 'addedAt'], ['updated', 'updatedAt'], ['published', 'publishedAt']]) {
    await page.locator('[name=sort]').selectOption(order);
    await page.reload();
    await expect(page.locator('#result-count')).toHaveText(`显示 ${papers.length} / ${papers.length} 篇论文`);
    await expect(page.locator('[name=sort]')).toHaveValue(order);
    const ids = await page.locator('#paper-grid > .paper-card').evaluateAll(cards => cards.map(card => (card as HTMLElement).dataset.paperId));
    const dates = ids.map(id => papers.find((p: any) => p.id === id)[field] || '');
    expect(dates).toEqual([...dates].sort().reverse());
  }
  await page.locator('[name=sort]').selectOption('added');
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.locator('[name=sort]')).toHaveValue('published');
  await expect(page.getByRole('link', { name: '复现方法 ↗' })).toHaveCount(papers.length);
  await page.getByRole('link', { name: '复现方法 ↗' }).first().click();
  await expect(page).toHaveURL(/\/papers\/[^/]+\/#reproduction$/);
  await expect(page.getByRole('heading', { name: '复现方法', exact: true })).toBeVisible();
});
