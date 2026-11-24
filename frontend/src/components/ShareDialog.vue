<script setup lang="ts">
import { Check, Copy, Send, X } from 'lucide-vue-next'
import { renderSVG } from 'uqr'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRatings } from '../composables/useRatings'
import { shareUrl } from '../utils/share'

// окно «Поделиться»: ссылка с оценками прямо в адресе (сервер их не хранит) и QR-код – на защите преподаватель
// наводит камеру телефона и видит те же советы у себя
const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const { payload } = useRatings()
const dialog = ref<HTMLDialogElement | null>(null)
const copied = ref(false)

const url = computed(() => shareUrl(`${window.location.origin}${import.meta.env.BASE_URL}`, payload.value))
// QR всегда чёрный на белом – так его прочитает любая камера, и в тёмной теме сайта тоже
const qr = computed(() => renderSVG(url.value, { ecc: 'M', border: 2, whiteColor: '#ffffff', blackColor: '#000000' }))
const canSend = typeof navigator.share === 'function'

watch(
  () => props.open,
  async (open) => {
    await nextTick()
    if (open && !dialog.value?.open) {
      copied.value = false
      dialog.value?.showModal()
    } else if (!open && dialog.value?.open) dialog.value.close()
  },
)

async function copy() {
  try {
    await navigator.clipboard.writeText(url.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // нет доступа к буферу обмена – ссылку можно выделить в поле и скопировать вручную
  }
}

async function send() {
  try {
    await navigator.share({ title: 'KinoCompass', url: url.value })
  } catch {
    // человек закрыл меню «Поделиться» телефона
  }
}

function close() {
  dialog.value?.close()
}

function onClick(event: MouseEvent) {
  if (event.target === dialog.value) close() // нажатие на затемнение вокруг окна
}
</script>

<template>
  <dialog
    ref="dialog"
    class="m-auto max-h-[90vh] w-[min(26rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-line bg-surface p-0 text-ink shadow-[0_20px_60px_rgba(0,0,0,0.35)] backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    :aria-label="t('share.title')"
    @close="emit('close')"
    @click="onClick"
  >
    <div v-if="open" class="space-y-5 p-5 sm:p-6">
      <header class="flex items-start justify-between gap-4">
        <div>
          <h2 class="text-xl font-semibold">{{ t('share.title') }}</h2>
          <p class="mt-1 text-sm text-muted">{{ t('share.lead', { n: payload.length }) }}</p>
        </div>
        <button type="button" class="shrink-0 rounded-lg p-1 text-muted hover:text-ink" :aria-label="t('share.close')" @click="close">
          <X class="h-5 w-5" />
        </button>
      </header>

      <figure class="space-y-2 text-center">
        <!-- SVG собирает uqr из адреса сайта – чужого текста внутри нет -->
        <div class="mx-auto w-52 rounded-xl bg-white p-1.5 [&>svg]:block [&>svg]:h-auto [&>svg]:w-full" role="img" :aria-label="t('share.scan')" v-html="qr" />
        <figcaption class="text-xs text-muted">{{ t('share.scan') }}</figcaption>
      </figure>

      <div class="flex gap-2">
        <input
          :value="url"
          readonly
          class="min-w-0 flex-1 rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-muted outline-none focus:border-accent"
          :aria-label="t('share.link')"
          @focus="($event.target as HTMLInputElement).select()"
        />
        <button type="button" class="flex shrink-0 items-center gap-1.5 rounded-xl bg-accent px-3 py-2 text-sm font-medium text-accent-ink" @click="copy">
          <Check v-if="copied" class="h-4 w-4" />
          <Copy v-else class="h-4 w-4" />
          {{ copied ? t('share.copied') : t('share.copy') }}
        </button>
      </div>
      <button
        v-if="canSend"
        type="button"
        class="flex w-full items-center justify-center gap-2 rounded-xl border border-line px-3 py-2 text-sm transition hover:border-accent hover:text-accent"
        @click="send"
      >
        <Send class="h-4 w-4" /> {{ t('share.send') }}
      </button>
      <p class="text-xs text-muted">{{ t('share.private') }}</p>
    </div>
  </dialog>
</template>
