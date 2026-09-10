import fs from 'node:fs';
import path from 'node:path';
import { validateCollection } from './validation.mjs';

export const root = process.cwd();
export const taxonomy = JSON.parse(fs.readFileSync(path.join(root, 'config/taxonomy.json'), 'utf8'));
export const publication = JSON.parse(fs.readFileSync(path.join(root, 'config/publication.json'), 'utf8'));
const { scope } = JSON.parse(fs.readFileSync(path.join(root, 'config/quality.json'), 'utf8'));
const excludedTopic = new RegExp(scope.excluded_topic_pattern, 'i');

export function inPublicationScope(paper) {
  return Boolean(paper.publishedAt && Number(paper.publishedAt.slice(0, 4)) >= scope.min_published_year
    && !excludedTopic.test(`${paper.title} ${paper.taskFormat || ''}`));
}

export function readDirectory(dir) {
  const location = path.join(root, dir);
  if (!fs.existsSync(location)) return [];
  return fs.readdirSync(location).filter(f => f.endsWith('.json')).sort().map(f => {
    const p = JSON.parse(fs.readFileSync(path.join(location, f), 'utf8'));
    if (f !== `${p.id}.json`) throw new Error(`Filename/ID mismatch: ${f}`);
    return p;
  });
}

export function loadCatalog(mode = process.env.PUBLISH_MODE || publication.mode) {
  if (!['auto', 'review'].includes(mode)) throw new Error('Invalid publication mode');
  const curated = validateCollection(readDirectory('data/curated'));
  const drafts = validateCollection(readDirectory('data/drafts'), { drafts: true });
  const ids = new Set(curated.map(p => p.id));
  // A newer machine version never replaces a curated record, even in auto mode.
  const automatic = mode === 'auto' ? drafts.filter(p => !ids.has(p.id) && p.publication === 'listed' && p.summaryZh && ['introduces_benchmark', 'evaluation_framework'].includes(p.role)).map(p => ({ ...p, review: { status: 'auto_unreviewed', reviewer: null, reviewedAt: null } })) : [];
  // Apply current scope to restored drafts too, so old state cannot republish removed topics.
  return [...curated.filter(p => p.publication === 'listed'), ...automatic].filter(inPublicationScope);
}

export function readStatus() {
  return {
    collection: JSON.parse(fs.readFileSync(path.join(root, 'automation/state.json'), 'utf8')).last_successful_collection_at,
    deployment: JSON.parse(fs.readFileSync(path.join(root, 'automation/deployment.json'), 'utf8')).last_successful_deployment_at,
  };
}
