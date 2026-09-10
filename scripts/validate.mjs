import fs from 'node:fs';
import path from 'node:path';
import { loadCatalog, readDirectory, root } from '../src/lib/catalog.mjs';
import { validateCollection } from '../src/lib/validation.mjs';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

try {
  const ajv = new Ajv({ allErrors: true });
  addFormats(ajv);
  const triageSchema = JSON.parse(fs.readFileSync(path.join(root, 'schemas/triage.schema.json'), 'utf8'));
  const checkTriage = ajv.compile(triageSchema);
  for (const assessment of readDirectory('data/triage')) {
    if (!checkTriage(assessment)) throw new Error(`Invalid triage ${assessment.id}: ${ajv.errorsText(checkTriage.errors)}`);
    if (assessment.id !== `arxiv-${assessment.arxivId.replace('/', '-')}`) throw new Error('Triage ID mismatch');
    if (assessment.score !== assessment.evidence.reduce((sum, e) => sum + e.weight, 0) || assessment.score > assessment.scoreMax) throw new Error('Triage score mismatch');
  }
  console.log(`triage: ${readDirectory('data/triage').length} valid assessments`);
  for (const group of ['curated', 'drafts']) {
    const records = validateCollection(readDirectory(`data/${group}`), { drafts: group === 'drafts' });
    for (const p of records) for (const run of p.reproduction.runs) {
      if (run.notePath !== `${p.id}.md` || !fs.existsSync(path.join(root, 'notes', run.notePath))) throw new Error(`Missing matching human note: ${p.id}`);
    }
    console.log(`${group}: ${records.length} valid records`);
  }
  console.log(`Publication: ${loadCatalog().length} records; schema and editorial boundaries valid.`);
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
}
