import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import App from '../App.vue'
import router from '../router'
import { createPlatformFetch } from './helpers/mock-platform-fetch'

enableAutoUnmount(afterEach)

async function signedIn(role: 'farmer' | 'technician' | 'admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/login')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [pinia, router] } })
  await wrapper.find(`[data-test="login-${role}"]`).trigger('click')
  await flushPromises()
  return wrapper
}

describe('Operational workflow', () => {
  beforeEach(async () => {
    sessionStorage.clear()
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
    vi.stubGlobal('fetch', createPlatformFetch().fetch)
    await router.push('/login')
  })

  it('loads official observations through the authenticated platform API', async () => {
    const fetchMock = vi.mocked(fetch)

    await signedIn('technician')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/login',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/ponds/pond-ref/readings',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-technician' }),
      }),
    )
  })

  it('presents authentic observation provenance separately from pond actions', async () => {
    const wrapper = await signedIn('technician')
    await router.push('/monitoring')
    await flushPromises()

    expect(wrapper.text()).toContain('外部官方观测站点')
    expect(wrapper.text()).toContain('USGS 01463500')
    expect(wrapper.text()).toContain('外部观测')
    expect(wrapper.text()).toContain('临时数据')
    expect(wrapper.text()).toContain('UTC')
    expect(wrapper.findAll('[data-test="reading-row"]').length).toBeGreaterThanOrEqual(20)
  })

  it('completes a visibly simulated oxygen alert response', async () => {
    const fetchMock = vi.mocked(fetch)
    const wrapper = await signedIn('farmer')
    await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/demo/ponds/pond-hz-01/low-oxygen',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(wrapper.text()).toContain('等待技术员复核')
  })

  it('requires technician review before farmer execution and feedback requests', async () => {
    const fetchMock = vi.mocked(fetch)
    const farmer = await signedIn('farmer')
    await farmer.find('[data-test="inject-low-oxygen"]').trigger('click')
    await flushPromises()
    expect(farmer.find('[data-test="confirm-recommendation"]').exists()).toBe(false)

    await router.push('/login')
    await farmer.find('[data-test="login-technician"]').trigger('click')
    await flushPromises()
    await farmer.find('[data-test="review-recommendation"]').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/recommendations/rec-1/review',
      expect.objectContaining({ method: 'PATCH' }),
    )

    await router.push('/login')
    await farmer.find('[data-test="login-farmer"]').trigger('click')
    await flushPromises()
    await farmer.find('[data-test="confirm-recommendation"]').trigger('click')
    await flushPromises()
    await farmer.find('[data-test="execute-simulation"]').trigger('click')
    await flushPromises()
    await farmer.find('[data-test="resolve-alert"]').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/executions/exec-1/feedback',
      expect.objectContaining({ method: 'PATCH' }),
    )
    expect(farmer.text()).toContain('已处置，等待技术员复核关闭')
    farmer.unmount()

    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/dashboard')
    const restored = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()
    expect(restored.text()).toContain('已处置，等待技术员复核关闭')

    await router.push('/login')
    await restored.find('[data-test="login-technician"]').trigger('click')
    await flushPromises()
    await restored.find('[data-test="close-alert"]').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/alerts/alert-1/close',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(restored.text()).toContain('预警已关闭')
  })

  it('shows evidence-only operations and unverified report caveat', async () => {
    const fetchMock = vi.mocked(fetch)
    const tech = await signedIn('technician')
    await router.push('/reports')
    await flushPromises()
    expect(tech.text()).toContain('塘口处置效益月度报告')
    expect(tech.text()).toContain('128.4 CNY')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/reports/benefits',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-technician' }),
      }),
    )
    await tech.find('[data-test="export-report"]').trigger('click')
    await flushPromises()
    expect(tech.text()).toContain('标识脱敏策略 v1')
    tech.unmount()

    const admin = await signedIn('admin')
    await router.push('/operations')
    await flushPromises()
    expect(admin.text()).toContain('审计与运维')
    expect(admin.text()).toContain('归档操作记录审批与证据')
    expect(admin.text()).toContain('24 条官方外部观测')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/operations/health',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-admin' }),
      }),
    )
    await admin.find('[data-test="archive-evidence"]').trigger('click')
    await flushPromises()
    expect(admin.text()).toContain('ARCH-APPROVAL-')
  })

  it('runs the simulated density analysis and technician review through APIs', async () => {
    const fetchMock = vi.mocked(fetch)
    const technician = await signedIn('technician')
    await router.push('/density')
    await flushPromises()
    await technician.find('[data-test="analyze-density"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/media-samples',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/density-analyses/analysis-1/review',
      expect.objectContaining({ method: 'PATCH' }),
    )
    expect(technician.text()).toContain('density-demo-v1')
    expect(technician.text()).toContain('± 4')
  })

  it('restores protected operations data after an authenticated direct page load', async () => {
    sessionStorage.setItem('aquaculture-role', 'admin')
    sessionStorage.setItem('aquaculture-token', 'token-admin')
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/operations')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('24 条官方外部观测')
  })

  it('restores reports and monitoring data after authenticated direct page loads', async () => {
    sessionStorage.setItem('aquaculture-role', 'technician')
    sessionStorage.setItem('aquaculture-token', 'token-technician')
    let pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/reports')
    let wrapper = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('128.4 CNY')
    wrapper.unmount()

    pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/monitoring')
    wrapper = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()
    expect(wrapper.findAll('[data-test="reading-row"]').length).toBe(24)
  })

  it('restores an existing server workflow after refreshing the dashboard', async () => {
    const original = await signedIn('farmer')
    await original.find('[data-test="inject-low-oxygen"]').trigger('click')
    await flushPromises()
    original.unmount()

    sessionStorage.setItem('aquaculture-role', 'farmer')
    sessionStorage.setItem('aquaculture-token', 'token-farmer')
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/dashboard')
    const restored = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()
    expect(restored.text()).toContain('等待技术员复核')
  })

  it('blocks direct route access outside the active role scope', async () => {
    const tech = await signedIn('technician')
    await router.push('/operations')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/dashboard')
    expect(tech.text()).not.toContain('归档控制')
    tech.unmount()

    sessionStorage.clear()
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/monitoring')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('uses cached monitoring output offline and blocks online-only surfaces', async () => {
    const fetchMock = vi.mocked(fetch)
    let wrapper = await signedIn('admin')
    await router.push('/monitoring')
    await flushPromises()
    const readingRequests = () =>
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith('/api/v1/ponds/pond-ref/readings'),
      ).length
    const onlineRequestCount = readingRequests()

    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
    await flushPromises()
    expect(wrapper.text()).toContain('离线缓存数据')
    wrapper.unmount()

    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/monitoring')
    wrapper = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('当前离线')
    expect(wrapper.text()).toContain('离线缓存数据')
    expect(wrapper.text()).toContain('最后同步时间')
    expect(readingRequests()).toBe(onlineRequestCount)
    expect(wrapper.text()).not.toContain('效益报表')
    expect(wrapper.text()).not.toContain('运维管理')

    await router.push('/operations')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/dashboard')
    expect(wrapper.find('[data-test="archive-evidence"]').exists()).toBe(false)
  })

  it('does not show simulated control actions when the grant permits cached-only work', async () => {
    const wrapper = await signedIn('farmer')
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
    await flushPromises()

    expect(wrapper.text()).toContain('当前离线')
    expect(wrapper.find('[data-test="inject-low-oxygen"]').exists()).toBe(false)
  })

  it('does not restore offline cached views without a valid offline grant', async () => {
    const wrapper = await signedIn('farmer')
    wrapper.unmount()
    sessionStorage.removeItem('aquaculture-offline-grant')
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })

    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/monitoring')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')

    sessionStorage.setItem(
      'aquaculture-offline-grant',
      JSON.stringify({
        maxDays: 7,
        permissions: ['read_cached_dashboard'],
        pondScope: ['pond-ref'],
        expiresAt: '2020-01-01T00:00:00Z',
        signedGrant: 'expired-grant',
      }),
    )
    await router.push('/monitoring')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('leaves an open protected view when connectivity drops without a valid grant', async () => {
    sessionStorage.setItem('aquaculture-role', 'farmer')
    sessionStorage.setItem('aquaculture-token', 'token-farmer')
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/monitoring')
    const wrapper = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()
    expect(wrapper.findAll('[data-test="reading-row"]').length).toBe(24)

    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
  })
})
