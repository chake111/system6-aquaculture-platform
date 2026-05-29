export function createRequest(getAccessToken: () => string | null, onUnauthorized: () => void) {
  return async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {}
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
    if (init.body) headers['Content-Type'] = 'application/json'
    let response: Response
    try {
      response = await fetch(path, { ...init, headers })
    } catch {
      throw new Error('网络不通，检查一下网络？')
    }
    if (response.status === 401) {
      onUnauthorized()
      return undefined as T
    }
    if (!response.ok) throw new Error(`请求失败 (${response.status})`)
    try {
      return (await response.json()) as T
    } catch {
      throw new Error('服务端返回了意料之外的数据')
    }
  }
}
