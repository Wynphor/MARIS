<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  direction?: 'horizontal' | 'vertical'
}>()

const emit = defineEmits<{
  resize: [delta: number]
  resizeStart: []
  resizeEnd: []
}>()

const dragging = ref(false)
let startPos = 0

function onMouseDown(e: MouseEvent) {
  dragging.value = true
  startPos = props.direction === 'horizontal' ? e.clientX : e.clientY
  emit('resizeStart')
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  const current = props.direction === 'horizontal' ? e.clientX : e.clientY
  emit('resize', current - startPos)
  startPos = current
}

function onMouseUp() {
  dragging.value = false
  emit('resizeEnd')
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
}
</script>

<template>
  <div
    class="split-handle"
    :class="[direction || 'vertical', { dragging }]"
    @mousedown="onMouseDown"
  >
    <div class="split-grip">
      <div v-if="(direction || 'vertical') === 'vertical'" class="grip-dots-h"></div>
      <div v-else class="grip-dots-v"></div>
    </div>
  </div>
</template>

<style scoped>
.split-handle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  transition: background 0.1s;
}

.split-handle.vertical {
  height: 4px;
  cursor: ns-resize;
  background: var(--border);
}

.split-handle.horizontal {
  width: 4px;
  cursor: ew-resize;
  background: var(--border);
}

.split-handle:hover,
.split-handle.dragging {
  background: var(--orange);
}

.split-grip {
  display: flex;
  align-items: center;
  justify-content: center;
}

.grip-dots-h {
  width: 20px;
  height: 2px;
  background: repeating-linear-gradient(
    90deg,
    var(--fg-3) 0px, var(--fg-3) 2px,
    transparent 2px, transparent 5px
  );
  opacity: 0.4;
}

.grip-dots-v {
  width: 2px;
  height: 20px;
  background: repeating-linear-gradient(
    180deg,
    var(--fg-3) 0px, var(--fg-3) 2px,
    transparent 2px, transparent 5px
  );
  opacity: 0.4;
}

.split-handle:hover .grip-dots-h,
.split-handle:hover .grip-dots-v,
.split-handle.dragging .grip-dots-h,
.split-handle.dragging .grip-dots-v {
  opacity: 1;
  background: repeating-linear-gradient(
    90deg, white 0px, white 2px, transparent 2px, transparent 5px
  );
}

.split-handle.dragging.vertical .grip-dots-h {
  background: repeating-linear-gradient(
    90deg, white 0px, white 2px, transparent 2px, transparent 5px
  );
}

.split-handle.dragging.horizontal .grip-dots-v {
  background: repeating-linear-gradient(
    180deg, white 0px, white 2px, transparent 2px, transparent 5px
  );
}
</style>
