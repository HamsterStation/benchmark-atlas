import fs from 'node:fs';
import path from 'node:path';
import { loadCatalog, readDirectory, root } from '../src/lib/catalog.mjs';
import { validateCollection } from '../src/lib/validation.mjs';

try {
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
