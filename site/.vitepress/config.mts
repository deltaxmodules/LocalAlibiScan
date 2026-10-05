import { defineConfig } from 'vitepress';

// O manual do LocalAlibiScan, publicado no GitHub Pages (daí o base path) por
// .github/workflows/pages.yml.
export default defineConfig({
  lang: 'en',
  title: 'LocalAlibiScan',
  description: 'Every claim has an alibi. What every project on your disk is — proven with file and line.',
  base: '/LocalAlibiScan/',
  cleanUrls: true,
  lastUpdated: false,
  ignoreDeadLinks: [/^\/example\//],
  head: [
    ['meta', { name: 'theme-color', content: '#10b981' }],
    ['link', { rel: 'icon', type: 'image/png', href: '/LocalAlibiScan/favicon.png', media: '(prefers-color-scheme: light)' }],
    ['link', { rel: 'icon', type: 'image/png', href: '/LocalAlibiScan/favicon-dark.png', media: '(prefers-color-scheme: dark)' }],
    ['meta', { property: 'og:image', content: 'https://deltaxmodules.github.io/LocalAlibiScan/og.png' }],
    ['meta', { property: 'og:title', content: 'LocalAlibiScan — every claim has an alibi' }],
  ],
  themeConfig: {
    logo: { light: '/brand/icon.png', dark: '/brand/icon-dark.png', alt: '' },
    siteTitle: 'LocalAlibiScan',
    nav: [
      { text: 'Get started', link: '/guide/get-started' },
      { text: 'Commands', link: '/reference/commands' },
      { text: 'Example report', link: 'https://deltaxmodules.github.io/LocalAlibiScan/example/' },
    ],
    sidebar: [
      {
        text: 'Start here',
        items: [
          { text: 'What is LocalAlibiScan?', link: '/' },
          { text: 'Install and first dashboard', link: '/guide/get-started' },
          { text: 'Claims: statuses and evidence', link: '/guide/claims' },
        ],
      },
      {
        text: 'Using it',
        items: [
          { text: 'Is it even a project?', link: '/guide/folder-verdict' },
          { text: 'The dashboard', link: '/guide/dashboard' },
          { text: 'One project in depth', link: '/guide/scan' },
          { text: 'Documentation that lies', link: '/guide/docs-vs-code' },
          { text: 'What changed', link: '/guide/refresh' },
          { text: 'Graphical interface', link: '/guide/ui' },
        ],
      },
      {
        text: 'Local AI (optional)',
        items: [
          { text: 'Explain this project', link: '/guide/explain' },
          { text: 'Ask a question', link: '/guide/ask' },
        ],
      },
      {
        text: 'Good to know',
        items: [
          { text: 'Guarantees and privacy', link: '/guide/privacy' },
          { text: 'Known limitations', link: '/guide/limitations' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'Commands', link: '/reference/commands' },
          { text: 'Configuration', link: '/reference/configuration' },
          { text: 'Detected technologies', link: '/reference/technologies' },
        ],
      },
    ],
    search: { provider: 'local' },
    socialLinks: [{ icon: 'github', link: 'https://github.com/deltaxmodules/LocalAlibiScan' }],
    outline: { level: [2, 3], label: 'On this page' },
    footer: { message: 'MIT License · local · read-only · open source', copyright: 'LocalAlibiScan by deltaXmodules' },
  },
});
