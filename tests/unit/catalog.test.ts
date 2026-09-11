import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadCatalog, readDirectory, inPublicationScope, isDraftReady } from '../../src/lib/catalog.mjs';
import { validatePaper, validateCollection } from '../../src/lib/validation.mjs';
import { matches, sortPapers } from '../../src/lib/filter';
import { renderNote } from '../../src/lib/notes.mjs';

const papers = loadCatalog();
const sample = () => structuredClone(papers.find(p => p.acronym === 'SWE-bench')!);
test('the catalog keeps in-scope benchmarks and excludes old publication years', () => {
  assert.ok(papers.length >= 5);
  assert.ok(papers.every(p => p.sources.length && !p.isTest));
  assert.ok(papers.every(p => p.publishedAt && p.publishedAt >= '2023-01-01'));
  assert.ok(!papers.some(p => p.acronym === 'MMLU'));
  assert.ok(sample().checkedAt);
});
test('publication scope blocks restored medical drafts and old papers with new versions', () => {
  assert.equal(inPublicationScope({ ...sample(), publishedAt: '2022-12-31', versionUpdatedAt: '2026-09-10' }), false);
  assert.equal(inPublicationScope({ ...sample(), publishedAt: '2023-01-01' }), true);
  assert.equal(inPublicationScope({ ...sample(), publishedAt: null }), false);
  assert.equal(inPublicationScope({ ...sample(), title: 'Biomedical Ontology Normalization with LLMs' }), false);
  assert.equal(inPublicationScope({ ...sample(), taskFormat: '使用 Agent 进行临床诊断。' }), false);
  assert.equal(inPublicationScope({ ...sample(), summaryZh: '通用评测，可能应用于医学或其他领域。' }), true);
});
test('a code deployment cannot publish drafts from a failed collection', () => {
  const paper = sample();
  paper.provenance.generatedAt = '2026-09-11T02:46:36Z';
  assert.equal(isDraftReady(paper, '2026-09-10T07:40:34Z'), false);
  assert.equal(isDraftReady(paper, null), false);
  assert.equal(isDraftReady(paper, 'invalid'), false);
  assert.equal(isDraftReady(paper, '2026-09-11T02:46:36Z'), true);
  assert.equal(isDraftReady(paper, '2026-09-11T04:00:00Z'), true);
});
test('schema rejects missing fields, invalid dates and unsafe URLs', () => {
  for (const change of [(p: any) => { delete p.title; }, (p: any) => { p.checkedAt = '2026-02-30'; }, (p: any) => { p.officialCode = 'javascript:alert(1)'; }, (p: any) => { p.targets = ['imagined']; }]) {
    const p = sample(); change(p); assert.throws(() => validatePaper(p));
  }
});
test('duplicate IDs and production test data are rejected', () => {
  assert.throws(() => validateCollection([sample(), sample()]), /Duplicate/);
  assert.throws(() => validateCollection([{ ...sample(), isTest: true }]), /Test data/);
});
test('all filters combine and search normalizes case and width', () => {
  const p = sample();
  assert.ok(matches(p, { q: 'ＳＷＥ-bench', target: 'llm', scenario: 'software', capability: 'code' }));
  assert.ok(matches(p, { q: '代码库' }));
  assert.ok(matches(p, { q: 'real-world github' }));
  for (const f of [{ target: 'multimodal' }, { scenario: 'web' }, { capability: 'grounding' }, { q: 'nothing-matches' }]) assert.equal(matches(p, f), false);
});
test('sorting never mutates the input and distinguishes timestamps', () => {
  const first = { ...sample(), id: 'a', addedAt: '2026-09-10', updatedAt: '2026-09-10', publishedAt: '2020-01-01' };
  const second = { ...sample(), id: 'b', addedAt: '2026-09-09', updatedAt: '2026-09-11', publishedAt: '2025-01-01' };
  const list = [first, second];
  assert.equal(sortPapers(list)[0].id, 'a');
  assert.equal(sortPapers(list, 'updated')[0].id, 'b');
  assert.equal(sortPapers(list, 'published')[0].id, 'b');
  assert.equal(list[0].id, 'a');
});
test('reproduction cannot be asserted without records and checked commands', () => {
  const p = sample(); p.reproduction.status = 'minimal_verified';
  assert.throws(() => validatePaper(p), /actual run|run records/);
  const q = sample(); q.reproduction.commands = [{ text: 'invented', sourceUrl: q.paperUrl, sourceVersion: 'v3', context: 'test' }];
  assert.throws(() => validatePaper(q), /official source/);
});
test('Markdown never becomes executable HTML or MDX', () => {
  const html = renderNote('# Safe\n<script>globalThis.pwned=1</script>\n\n[x](javascript:alert(1))\n\n{process.exit(1)}');
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(html.includes('{process.exit(1)}'));
});
test('draft boundary rejects verified claims', () => {
  assert.throws(() => validateCollection([sample()], { drafts: true }), /boundary/);
  assert.ok(readDirectory('data/drafts').every(p => !p.isTest));
});
test('metadata-only records cannot smuggle a claimed generated summary', () => {
  const p = sample(); p.provenance.method = 'metadata_only';
  assert.throws(() => validatePaper(p), /Metadata-only/);
});
