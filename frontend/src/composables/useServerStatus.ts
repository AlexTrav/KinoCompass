import { ref } from 'vue'
import { listenServer, type ServerSignal } from '../api/client'

// состояние сервера для плашки: 'slow' – долго нет ответа (скорее всего, Render просыпается), 'fail' – ошибка сети
const state = ref<ServerSignal>('ok')
listenServer((signal) => {
  state.value = signal
})

export function useServerStatus() {
  return { state }
}
