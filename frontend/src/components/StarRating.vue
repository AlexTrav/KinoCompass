<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

// пять звёзд с половинками (оценки MovieLens – от 0,5 до 5 с шагом 0,5): левая половина звезды – полбалла;
// с клавиатуры – стрелки, Delete убирает оценку
const props = withDefaults(defineProps<{ modelValue: number; size?: number }>(), { size: 22 })
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
const { t } = useI18n()
const hover = ref(0)
const uid = useId()
const shown = computed(() => hover.value || props.modelValue)

function valueAt(event: MouseEvent, star: number) {
  const box = (event.currentTarget as HTMLElement).getBoundingClientRect()
  return event.clientX - box.left < box.width / 2 ? star - 0.5 : star
}

function fill(star: number) {
  return Math.max(0, Math.min(1, shown.value - (star - 1))) * 100
}

function key(event: KeyboardEvent) {
  const step = { ArrowRight: 0.5, ArrowUp: 0.5, ArrowLeft: -0.5, ArrowDown: -0.5 }[event.key]
  if (step !== undefined) {
    event.preventDefault()
    emit('update:modelValue', Math.max(0.5, Math.min(5, (props.modelValue || 0) + step)))
  } else if (event.key === 'Delete' || event.key === 'Backspace') {
    emit('update:modelValue', 0)
  }
}
</script>

<template>
  <div
    class="inline-flex select-none items-center"
    role="slider"
    tabindex="0"
    :aria-label="t('rate.stars', { n: modelValue || 0 })"
    aria-valuemin="0"
    aria-valuemax="5"
    :aria-valuenow="modelValue"
    @keydown="key"
    @mouseleave="hover = 0"
  >
    <button
      v-for="star in 5"
      :key="star"
      type="button"
      tabindex="-1"
      class="relative cursor-pointer p-0.5 transition-transform hover:scale-110"
      :style="{ width: `${size + 4}px`, height: `${size + 4}px` }"
      @mousemove="hover = valueAt($event, star)"
      @click.stop.prevent="emit('update:modelValue', valueAt($event, star))"
    >
      <svg :width="size" :height="size" viewBox="0 0 24 24" aria-hidden="true">
        <defs>
          <clipPath :id="`c${star}-${uid}`">
            <rect x="0" y="0" :width="(24 * fill(star)) / 100" height="24" />
          </clipPath>
        </defs>
        <path
          d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z"
          fill="none"
          stroke="var(--muted)"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
        <path
          d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z"
          fill="var(--accent)"
          stroke="var(--accent)"
          stroke-width="1.5"
          stroke-linejoin="round"
          :clip-path="`url(#c${star}-${uid})`"
        />
      </svg>
    </button>
  </div>
</template>
