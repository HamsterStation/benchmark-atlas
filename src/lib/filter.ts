export type SearchPaper = {
  id: string; title: string; acronym: string | null; summaryZh: string | null;
  targets: string[]; scenarios: string[]; capabilities: string[];
  review: { status: string }; reproduction: { status: string };
  addedAt: string; updatedAt: string; publishedAt: string | null;
};
export type Filters = { q?: string; target?: string; scenario?: string; capability?: string; review?: string; reproduction?: string };
const normalize = (s: string) => s.normalize('NFKC').toLocaleLowerCase().trim();
export function matches(p: SearchPaper, f: Filters): boolean {
  const query = normalize(f.q || '');
  return (!query || normalize([p.title, p.acronym, p.summaryZh].filter(Boolean).join(' ')).includes(query))
    && (!f.target || p.targets.includes(f.target))
    && (!f.scenario || p.scenarios.includes(f.scenario))
    && (!f.capability || p.capabilities.includes(f.capability))
    && (!f.review || p.review.status === f.review)
    && (!f.reproduction || p.reproduction.status === f.reproduction);
}
export function sortPapers<T extends SearchPaper>(papers: T[], order = 'added'): T[] {
  const field = order === 'updated' ? 'updatedAt' : order === 'published' ? 'publishedAt' : 'addedAt';
  return [...papers].sort((a, b) => (b[field] || '').localeCompare(a[field] || '') || a.id.localeCompare(b.id));
}
