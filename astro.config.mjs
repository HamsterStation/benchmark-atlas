import { defineConfig } from 'astro/config';

const base = process.env.BASE_PATH || '/benchmark-atlas';
if (!/^\/(?:[A-Za-z0-9_.-]+\/?)*$/.test(base)) throw new Error('Invalid BASE_PATH');

export default defineConfig({
  site: process.env.SITE_URL || 'https://example.github.io',
  base,
  output: 'static',
  trailingSlash: 'always',
  build: { format: 'directory' },
});
