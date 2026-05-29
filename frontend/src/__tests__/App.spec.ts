import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import App from '../App.vue'
import router from '../router'

async function mountApp() {
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/login')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

describe('Aquaculture application shell', () => {
  beforeEach(async () => {
    sessionStorage.clear()
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith('/api/v1/auth/login')) {
          return Response.json({
            access_token: 'token-technician',
            refresh_token: 'refresh',
            role: JSON.parse(String(init?.body)).phone === '13800000002' ? 'technician' : 'farmer',
          })
        }
        if (String(input).endsWith('/api/v1/auth/offline-grants')) {
          return Response.json({
            max_days: 7,
            permissions: ['read_cached_dashboard', 'draft_alert_resolution'],
            pond_scope: ['pond-hz-01', 'pond-ref'],
            source_mode: 'simulation',
            expires_at: '2026-06-03T00:00:00Z',
            signed_grant: 'signed-offline-grant',
          })
        }
        if (
          String(input).endsWith('/api/v1/alerts') ||
          String(input).endsWith('/api/v1/ponds/pond-hz-01/recommendations')
        ) {
          return Response.json([])
        }
        if (String(input).endsWith('/api/v1/reports/benefits')) {
          return Response.json({ metrics: [], disclaimer: '演示' })
        }
        return Response.json({ items: [] })
      }),
    )
    await router.push('/login')
  })

  it('offers role login and field interaction affordances', async () => {
    const wrapper = await mountApp()

    expect(wrapper.text()).toContain('智慧水产养殖监测与调控平台')
    expect(wrapper.text()).toContain('选择角色')
    expect(wrapper.find('[data-test="toggle-contrast"]').attributes('aria-label')).toContain('高对比模式')
    expect(wrapper.findAll('[data-test="role-login"]')).toHaveLength(3)
  })

  it('shows actual connectivity state', async () => {
    const wrapper = await mountApp()

    expect(wrapper.text()).toContain('当前在线')

    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
    await flushPromises()
    expect(wrapper.text()).toContain('当前离线')
  })

  it('shows technician navigation but restricts administration', async () => {
    const wrapper = await mountApp()
    await wrapper.find('[data-test="login-technician"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('综合仪表盘')
    expect(wrapper.text()).toContain('水质监测')
    expect(wrapper.text()).toContain('密度调控')
    expect(wrapper.text()).toContain('预警中心')
    expect(wrapper.text()).toContain('效益报表')
    expect(wrapper.text()).not.toContain('运维管理')
  })

  it('requests and displays the restricted seven-day offline authorization after login', async () => {
    const wrapper = await mountApp()
    const fetchMock = vi.mocked(fetch)
    await wrapper.find('[data-test="login-technician"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/offline-grants',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token-technician' }),
      }),
    )
    expect(wrapper.text()).toContain('离线授权有效期至 2026-06-03T00:00:00Z')
    expect(wrapper.text()).toContain('仅允许：只读缓存、处置草稿')
  })

  it('toggles high-contrast class on the console element', async () => {
    const wrapper = await mountApp()
    await wrapper.find('[data-test="login-technician"]').trigger('click')
    await flushPromises()

    const consoleEl = wrapper.find('.console')
    expect(consoleEl.classes()).not.toContain('contrast')

    await wrapper.find('[data-test="toggle-contrast"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('.console').classes()).toContain('contrast')

    await wrapper.find('[data-test="toggle-contrast"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('.console').classes()).not.toContain('contrast')
  })

  it('shows login error when authentication fails', async () => {
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/api/v1/auth/login')) {
        return new Response(null, { status: 500 })
      }
      return Response.json({})
    })
    const wrapper = await mountApp()
    await wrapper.find('[data-test="login-technician"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('请求失败')
    expect(wrapper.find('[data-test="login-error"]').exists()).toBe(true)
  })
})
