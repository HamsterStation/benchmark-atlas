import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import fs from 'node:fs';
import path from 'node:path';

const schema = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'schemas/paper.schema.json'), 'utf8'));
const ajv = new Ajv({ allErrors: true, strict: true });
addFormats(ajv);
const check = ajv.compile(schema);

export function validatePaper(p) {
  if (!check(p)) throw new Error(ajv.errorsText(check.errors, { separator: '\n' }));
  if (p.id !== `arxiv-${p.arxivId.replace('/', '-')}`) throw new Error('ID must match the base arXiv ID');
  if (p.version && p.paperUrl !== `https://arxiv.org/abs/${p.arxivId}v${p.version}`) throw new Error('Paper URL/version mismatch');
  if (p.publishedAt && p.versionUpdatedAt && p.versionUpdatedAt < p.publishedAt) throw new Error('Version predates first publication');
  if (['source_verified', 'human_reviewed'].includes(p.review.status) && (!p.checkedAt || !p.sources.length)) throw new Error('Verified content requires checked sources');
  if (p.review.status === 'human_reviewed' && (!p.review.reviewer || !p.review.reviewedAt)) throw new Error('Human review requires attribution');
  if (p.provenance.method === 'model' && (!p.provenance.generatedAt || !p.provenance.materialHash || !p.provenance.model)) throw new Error('Model provenance is incomplete');
  if (p.provenance.method === 'metadata_only' && (p.summaryZh !== null || p.taskFormat !== null)) throw new Error('Metadata-only records cannot claim a generated summary');
  const verified = ['minimal_verified', 'experiment_reproduced'].includes(p.reproduction.status);
  if (verified && !p.reproduction.runs.length) throw new Error('Reproduction requires actual run records');
  if (!verified && p.reproduction.runs.length) throw new Error('Run records require a matching reproduction status');
  if (p.reproduction.status === 'experiment_reproduced' && !p.reproduction.runs.some(r => r.experiment)) throw new Error('Specify the reproduced experiment');
  if (p.reproduction.status === 'official_docs_unrun' && !p.sources.some(s => ['official_repository', 'official_documentation'].includes(s.kind) && s.checkedAt)) throw new Error('Official documentation must be checked');
  for (const cmd of p.reproduction.commands) {
    if (!p.sources.some(s => s.url === cmd.sourceUrl && s.version === cmd.sourceVersion && s.checkedAt && ['official_repository', 'official_documentation'].includes(s.kind))) throw new Error('Command requires a checked, versioned official source');
  }
  for (const metric of p.metrics) if (!p.sources.some(s => s.url === metric.sourceUrl)) throw new Error('Metric source is missing');
  return p;
}

export function validateCollection(records, { drafts = false } = {}) {
  const ids = new Set();
  for (const p of records) {
    validatePaper(p);
    if (ids.has(p.id)) throw new Error(`Duplicate ID: ${p.id}`);
    ids.add(p.id);
    if (p.isTest) throw new Error(`Test data forbidden in content directories: ${p.id}`);
    if (drafts && (!['metadata_only', 'model'].includes(p.provenance.method) || !['needs_review', 'auto_unreviewed'].includes(p.review.status) || p.checkedAt || p.reproduction.status !== 'unverified' || p.reproduction.commands.length || p.reproduction.runs.length)) throw new Error(`Machine draft crosses editorial boundary: ${p.id}`);
  }
  return records;
}
