import { ref } from 'vue'

export function createLoading() {
  const loading = ref<Set<string>>(new Set())

  function isLoading(key: string) {
    return loading.value.has(key)
  }

  async function withLoading<T = void>(key: string, fn: () => Promise<T>): Promise<T | undefined> {
    if (loading.value.has(key)) return
    loading.value = new Set([...loading.value, key])
    try {
      return await fn()
    } finally {
      const next = new Set(loading.value)
      next.delete(key)
      loading.value = next
    }
  }

  return { loading, isLoading, withLoading }
}
