<script setup lang="ts">
import Shell from './components/layout/Shell.vue'
</script>

<template>
  <n-message-provider>
    <Shell />
  </n-message-provider>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-0: #0a0a0a;
  --bg-1: #111111;
  --bg-2: #191919;
  --bg-3: #222222;
  --bg-hover: #1a1a1a;
  --bg-active: #252525;
  --fg-1: #e0e0e0;
  --fg-2: #999999;
  --fg-3: #555555;
  --orange: #e87a35;
  --orange-dim: #c0662a;
  --orange-glow: rgba(232,122,53,0.12);
  --green: #3dd68c;
  --red: #f06060;
  --yellow: #e8c050;
  --blue: #5090f0;
  --border: #1f1f1f;
  --border-l: #2a2a2a;
  --r: 6px;
  --font: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  --mono: 'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace;

  /* Aliases for Naive UI compatibility */
  --bg-base: var(--bg-0); --bg-surface: var(--bg-1); --bg-elevated: var(--bg-2);
  --bg-input: var(--bg-2); --text-primary: var(--fg-1); --text-secondary: var(--fg-2);
  --text-muted: var(--fg-3); --accent: var(--orange); --accent-dim: var(--orange-dim);
  --accent-glow: var(--orange-glow); --accent-text: #f0a060; --success: var(--green);
  --warning: var(--yellow); --error: var(--red); --info: var(--blue);
  --border-light: var(--border); --border-focus: var(--orange);
  --radius-sm: var(--r); --radius-md: 10px; --radius-lg: 14px;
  --font-sans: var(--font); --font-mono: var(--mono);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; background: var(--bg-0); color: var(--fg-1); font-family: var(--font); font-size: 13px; -webkit-font-smoothing: antialiased; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-l); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--fg-3); }

/* ── Shared Page Styles ── */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; padding: 12px 16px; }
.page-title { font-size: 15px; font-weight: 700; color: var(--fg-1); letter-spacing: -0.3px; }
.page-desc { font-size: 11px; color: var(--fg-3); margin-top: 2px; }
.section-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--fg-3); margin-bottom: 8px; }

/* ── Naive UI Dark Theme Overrides ── */
.n-card { background: var(--bg-1) !important; border: 1px solid var(--border) !important; border-radius: var(--r) !important; }
.n-card .n-card-header__title { color: var(--fg-1) !important; font-weight: 600 !important; font-size: 12px !important; }
.n-button { font-weight: 500 !important; border-radius: 4px !important; font-size: 12px !important; }
.n-button--primary-type { background: var(--orange) !important; border-color: var(--orange) !important; }
.n-button--primary-type:hover { background: var(--orange-dim) !important; }
.n-select .n-base-selection { background: var(--bg-2) !important; border-color: var(--border) !important; }
.n-tag { border-radius: 3px !important; font-size: 10px !important; }
.n-empty .n-empty__description { color: var(--fg-3) !important; }
.n-data-table { --n-th-color: var(--bg-2) !important; --n-td-color: var(--bg-1) !important; --n-border-color: var(--border) !important; }
.n-data-table .n-data-table-th { color: var(--fg-2) !important; font-size: 11px !important; }
.n-data-table .n-data-table-td { color: var(--fg-1) !important; font-size: 12px !important; }
.n-input { --n-color: var(--bg-2) !important; --n-border: var(--border) !important; --n-text-color: var(--fg-1) !important; }
.n-input-number { --n-color: var(--bg-2) !important; }
.n-switch { --n-rail-color-active: var(--orange) !important; }
.n-progress { --n-rail-color: var(--bg-3) !important; --n-fill-color: var(--orange) !important; }
.n-message-container .n-message { background: var(--bg-2) !important; border: 1px solid var(--border) !important; }
.n-modal { background: var(--bg-1) !important; }
</style>
