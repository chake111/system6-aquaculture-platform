import { onUnmounted, ref } from 'vue'

export function usePolling(fn: () => Promise<void>, intervalMs: number) {
  const timer = ref<ReturnType<typeof setInterval> | null>(null)
  const isPolling = ref(true)

  function start() {
    if (timer.value) return
    isPolling.value = true
    timer.value = setInterval(async () => {
      try {
        await fn()
      } catch {
        // polling errors silently ignored; will retry next interval
      }
    }, intervalMs)
  }

  function stop() {
    if (timer.value) {
      clearInterval(timer.value)
      timer.value = null
    }
    isPolling.value = false
  }

  function toggle() {
    if (isPolling.value) {
      stop()
    } else {
      start()
    }
  }

  onUnmounted(stop)

  return { start, stop, toggle, isPolling }
}
