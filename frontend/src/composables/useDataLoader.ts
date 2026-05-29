import { ref } from 'vue'

export function useDataLoader(loadFn: () => Promise<void>) {
  const loadError = ref(false)

  async function load() {
    try {
      await loadFn()
      loadError.value = false
    } catch {
      loadError.value = true
    }
  }

  return { loadError, retry: load, load }
}
