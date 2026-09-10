import { loadCatalog } from '../lib/catalog.mjs';
export const prerender = true;
export function GET() {
  const papers = loadCatalog().map(({ id, title, acronym, summaryZh, targets, scenarios, capabilities, review, reproduction, addedAt, updatedAt, publishedAt }) => ({ id, title, acronym, summaryZh, targets, scenarios, capabilities, review, reproduction: { status: reproduction.status }, addedAt, updatedAt, publishedAt }));
  return new Response(JSON.stringify(papers), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
