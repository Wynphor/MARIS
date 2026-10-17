import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type SidebarPanel = 'overview' | 'files' | 'settings'
export type RightPanel = 'chat' | 'data'
export type BottomTab = 'pipeline' | 'terminal' | 'output' | 'problems'
export type EditorTab = 'editor' | 'data'

export const useLayoutStore = defineStore('layout', () => {
  // ── Primary Sidebar ──
  const sidebarOpen = ref(true)
  const sidebarPanel = ref<SidebarPanel>('overview')
  const sidebarWidth = ref(260)

  // ── Secondary Sidebar (right — AI panel) ──
  const rightSidebarOpen = ref(true)
  const rightSidebarPanel = ref<RightPanel>('chat')
  const rightSidebarWidth = ref(360)

  // ── Bottom Panel ──
  const bottomOpen = ref(true)
  const bottomTab = ref<BottomTab>('pipeline')
  const bottomHeight = ref(280)

  // ── Editor Tabs ──
  const editorTabs = ref<EditorTab[]>(['editor'])
  const activeEditorTab = ref<EditorTab>('editor')

  // ── Actions ──
  function toggleSidebar(panel?: SidebarPanel) {
    if (panel && sidebarPanel.value === panel && sidebarOpen.value) {
      sidebarOpen.value = false
    } else {
      sidebarOpen.value = true
      if (panel) sidebarPanel.value = panel
    }
  }

  function toggleRightSidebar(panel?: RightPanel) {
    if (panel && rightSidebarPanel.value === panel && rightSidebarOpen.value) {
      rightSidebarOpen.value = false
    } else {
      rightSidebarOpen.value = true
      if (panel) rightSidebarPanel.value = panel
    }
  }

  function toggleBottom(tab?: BottomTab) {
    if (tab && bottomTab.value === tab && bottomOpen.value) {
      bottomOpen.value = false
    } else {
      bottomOpen.value = true
      if (tab) bottomTab.value = tab
    }
  }

  function openEditorTab(tab: EditorTab) {
    if (!editorTabs.value.includes(tab)) {
      editorTabs.value.push(tab)
    }
    activeEditorTab.value = tab
  }

  function closeEditorTab(tab: EditorTab) {
    const idx = editorTabs.value.indexOf(tab)
    if (idx === -1) return
    editorTabs.value.splice(idx, 1)
    if (activeEditorTab.value === tab) {
      activeEditorTab.value = editorTabs.value[Math.max(0, idx - 1)] || 'editor'
    }
    // Always keep at least editor
    if (editorTabs.value.length === 0) {
      editorTabs.value = ['editor']
      activeEditorTab.value = 'editor'
    }
  }

  // ── Persist sizes ──
  function loadSizes() {
    try {
      const raw = localStorage.getItem('mathmodel_layout')
      if (raw) {
        const s = JSON.parse(raw)
        if (s.sidebarWidth) sidebarWidth.value = s.sidebarWidth
        if (s.rightSidebarWidth) rightSidebarWidth.value = s.rightSidebarWidth
        if (s.bottomHeight) bottomHeight.value = s.bottomHeight
        if (s.sidebarOpen !== undefined) sidebarOpen.value = s.sidebarOpen
        if (s.rightSidebarOpen !== undefined) rightSidebarOpen.value = s.rightSidebarOpen
        if (s.bottomOpen !== undefined) bottomOpen.value = s.bottomOpen
      }
    } catch { /* ignore */ }
  }

  function saveSizes() {
    try {
      localStorage.setItem('mathmodel_layout', JSON.stringify({
        sidebarWidth: sidebarWidth.value,
        rightSidebarWidth: rightSidebarWidth.value,
        bottomHeight: bottomHeight.value,
        sidebarOpen: sidebarOpen.value,
        rightSidebarOpen: rightSidebarOpen.value,
        bottomOpen: bottomOpen.value,
      }))
    } catch { /* ignore */ }
  }

  return {
    sidebarOpen, sidebarPanel, sidebarWidth,
    rightSidebarOpen, rightSidebarPanel, rightSidebarWidth,
    bottomOpen, bottomTab, bottomHeight,
    editorTabs, activeEditorTab,
    toggleSidebar, toggleRightSidebar, toggleBottom,
    openEditorTab, closeEditorTab,
    loadSizes, saveSizes,
  }
})
