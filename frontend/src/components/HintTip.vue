<script setup lang="ts">
import { useEventListener } from '@vueuse/core'
import { CircleHelp } from 'lucide-vue-next'
import { nextTick, ref, useId } from 'vue'

// короткая подсказка «?» простыми словами: наведение или нажатие (на телефоне), Esc закрывает.
// Выводится в <body> с position: fixed – её не обрезают таблицы и карточки; положение считается от значка и
// прижимается к краям окна, при нехватке места снизу – открывается вверх
defineProps<{ text: string }>()
const open = ref(false)
const id = useId()
const button = ref<HTMLButtonElement | null>(null)
const tip = ref<HTMLElement | null>(null)
const style = ref<Record<string, string>>({})
const MARGIN = 8
const GAP = 8

async function place() {
  const anchor = button.value?.getBoundingClientRect()
  if (!anchor) return
  const width = Math.min(256, window.innerWidth - 2 * MARGIN)
  const left = Math.min(Math.max(anchor.left + anchor.width / 2 - width / 2, MARGIN), window.innerWidth - width - MARGIN)
  style.value = { left: `${left}px`, top: `${anchor.bottom + GAP}px`, width: `${width}px` }
  await nextTick()
  const height = tip.value?.offsetHeight ?? 0
  if (anchor.bottom + GAP + height > window.innerHeight - MARGIN && anchor.top - GAP - height > MARGIN) {
    style.value = { ...style.value, top: `${anchor.top - GAP - height}px` }
  }
}

function show() {
  open.value = true
  place()
}

function hide() {
  open.value = false
}

useEventListener(window, 'scroll', hide, { passive: true, capture: true })
useEventListener(window, 'resize', hide)
</script>

<template>
  <span class="inline-flex align-middle" @mouseenter="show" @mouseleave="hide">
    <button
      ref="button"
      type="button"
      class="rounded-full p-0.5 text-muted transition hover:text-accent focus-visible:text-accent"
      :aria-describedby="open ? id : undefined"
      :aria-expanded="open"
      aria-label="?"
      @click.stop.prevent="open ? hide() : show()"
      @blur="hide"
      @keydown.esc="hide"
    >
      <CircleHelp class="h-4 w-4" />
    </button>
    <Teleport to="body">
      <Transition enter-active-class="transition-opacity duration-150" enter-from-class="opacity-0" leave-active-class="transition-opacity duration-100" leave-to-class="opacity-0">
        <span
          v-if="open"
          :id="id"
          ref="tip"
          role="tooltip"
          :style="style"
          class="pointer-events-none fixed z-50 rounded-xl border border-line bg-surface p-3 text-left text-xs font-normal normal-case leading-snug tracking-normal text-ink shadow-xl"
        >
          {{ text }}
        </span>
      </Transition>
    </Teleport>
  </span>
</template>
