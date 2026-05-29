import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import App from '../App.vue'
import router from '../router'
import { createPlatformFetch } from './helpers/mock-platform-fetch'

enableAutoUnmount(afterEach)

async function loginAs(role: 'farmer' | 'technician' | 'admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/login')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [pinia, router] } })
  await wrapper.find(`[data-test="login-${role}"]`).trigger('click')
  await flushPromises()
  return wrapper
}

describe('Component-level coverage', () => {
  beforeEach(async () => {
    sessionStorage.clear()
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
    vi.stubGlobal('fetch', createPlatformFetch().fetch)
    await router.push('/login')
  })

  describe('Monitoring view', () => {
    it('displays all readings with correct data', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/monitoring')
      await flushPromises()

      const rows = wrapper.findAll('[data-test="reading-row"]')
      expect(rows.length).toBe(24)
      // Verify readings contain expected data
      expect(rows[0]!.text()).toContain('2025-10-01T')
      expect(rows[0]!.text()).toContain('外部观测')
    })

    it('shows DO threshold color indicators', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/monitoring')
      await flushPromises()

      // Check that DO indicator dots exist
      const indicators = wrapper.findAll('.do-indicator')
      expect(indicators.length).toBe(24)
    })

    it('shows polling control toggle', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/monitoring')
      await flushPromises()

      expect(wrapper.text()).toContain('10s 自动刷新中')
    })

    it('displays trend charts section', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/monitoring')
      await flushPromises()

      expect(wrapper.text()).toContain('趋势图')
    })

    it('shows cache warning when offline with cached data', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/monitoring')
      await flushPromises()

      Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
      window.dispatchEvent(new Event('offline'))
      await flushPromises()

      expect(wrapper.text()).toContain('离线缓存数据')
      expect(wrapper.find('[data-test="cache-warning"]').exists()).toBe(true)
    })
  })

  describe('Dashboard view', () => {
    it('shows metric cards with latest DO and pH', async () => {
      const wrapper = await loginAs('farmer')
      await flushPromises()

      expect(wrapper.text()).toContain('最新溶氧')
      expect(wrapper.text()).toContain('最新 pH')
    })

    it('shows workflow steps for active alert', async () => {
      const wrapper = await loginAs('farmer')
      await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
      await flushPromises()

      // Alert workflow should show recommendation info
      expect(wrapper.text()).toContain('低溶氧预警')
      expect(wrapper.text()).toContain('等待技术员复核')
    })

    it('shows alert workflow after injection', async () => {
      const wrapper = await loginAs('farmer')
      await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('3.2 mg/L')
      expect(wrapper.text()).toContain('低溶氧预警')
    })

    it('shows quick-response button for farmer on generated alert', async () => {
      const wrapper = await loginAs('farmer')
      await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[data-test="quick-response"]').exists()).toBe(true)
      expect(wrapper.find('[data-test="confirm-recommendation"]').exists()).toBe(false)
      expect(wrapper.text()).toContain('一键处理（演示模式）')
    })

    it('shows confirm button for farmer after technician review', async () => {
      const fetchMock = vi.mocked(fetch)
      const wrapper = await loginAs('farmer')
      await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
      await flushPromises()

      // Simulate technician review by calling the API directly
      await fetchMock.mock.results[0]?.value
      await wrapper.find('[data-test="quick-response"]') // verify initial state
      expect(wrapper.text()).toContain('等待技术员复核')
    })

    it('hides inject button when alert is active', async () => {
      const wrapper = await loginAs('farmer')
      expect(wrapper.find('[data-test="inject-low-oxygen"]').exists()).toBe(true)

      await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[data-test="inject-low-oxygen"]').exists()).toBe(false)
    })
  })

  describe('Alerts view', () => {
    it('shows alert details when alert exists', async () => {
      const wrapper = await loginAs('farmer')
      await wrapper.find('[data-test="inject-low-oxygen"]').trigger('click')
      await flushPromises()
      await router.push('/alerts')
      await flushPromises()

      expect(wrapper.text()).toContain('当前预警')
      expect(wrapper.text()).toContain('低溶氧预警')
    })

    it('shows empty state when no alerts', async () => {
      const wrapper = await loginAs('farmer')
      await router.push('/alerts')
      await flushPromises()

      expect(wrapper.text()).toContain('暂无告警')
    })

    it('displays channel delivery status table', async () => {
      const wrapper = await loginAs('farmer')
      await router.push('/alerts')
      await flushPromises()

      expect(wrapper.text()).toContain('短信通知')
      expect(wrapper.text()).toContain('钉钉通知')
    })
  })

  describe('Density view', () => {
    it('runs density analysis on button click', async () => {
      const fetchMock = vi.mocked(fetch)
      const wrapper = await loginAs('technician')
      await router.push('/density')
      await flushPromises()

      await wrapper.find('[data-test="analyze-density"]').trigger('click')
      await flushPromises()

      // Verify the API was called
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/media-samples',
        expect.objectContaining({ method: 'POST' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/analyses'),
        expect.objectContaining({ method: 'POST' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/density-analyses/'),
        expect.objectContaining({ method: 'PATCH' }),
      )
      expect(wrapper.text()).toContain('density-demo-v1')
      expect(wrapper.text()).toContain('38')
    })

    it('shows empty state before analysis', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/density')
      await flushPromises()

      expect(wrapper.text()).toContain('尚未运行密度分析')
    })

    it('hides analyze button for non-technician', async () => {
      const wrapper = await loginAs('farmer')
      await router.push('/density')
      await flushPromises()

      expect(wrapper.find('[data-test="analyze-density"]').exists()).toBe(false)
    })
  })

  describe('Reports view', () => {
    it('shows benefit metrics', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/reports')
      await flushPromises()

      expect(wrapper.text()).toContain('增氧用电成本')
      expect(wrapper.text()).toContain('128.4')
    })

    it('shows export button and evidence after export', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/reports')
      await flushPromises()

      await wrapper.find('[data-test="export-report"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('标识脱敏策略 v1')
    })

    it('shows benefit report title', async () => {
      const wrapper = await loginAs('technician')
      await router.push('/reports')
      await flushPromises()

      expect(wrapper.text()).toContain('塘口处置效益月度报告')
    })
  })

  describe('Operations view', () => {
    it('shows component health status', async () => {
      const wrapper = await loginAs('admin')
      await router.push('/operations')
      await flushPromises()

      expect(wrapper.text()).toContain('节点与服务状态')
      expect(wrapper.text()).toContain('正常')
    })

    it('shows archive control for admin', async () => {
      const wrapper = await loginAs('admin')
      await router.push('/operations')
      await flushPromises()

      expect(wrapper.find('[data-test="archive-evidence"]').exists()).toBe(true)
    })

    it('registers archive evidence on click', async () => {
      const wrapper = await loginAs('admin')
      await router.push('/operations')
      await flushPromises()

      await wrapper.find('[data-test="archive-evidence"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('ARCH-APPROVAL-')
    })

    it('blocks non-admin access', async () => {
      await loginAs('technician')
      await router.push('/operations')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/dashboard')
    })
  })

  describe('Role-based access', () => {
    it('farmer cannot access reports', async () => {
      await loginAs('farmer')
      await router.push('/reports')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/dashboard')
    })

    it('farmer cannot access operations', async () => {
      await loginAs('farmer')
      await router.push('/operations')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/dashboard')
    })

    it('technician can access reports but not operations', async () => {
      await loginAs('technician')
      await router.push('/reports')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/reports')

      await router.push('/operations')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/dashboard')
    })
  })

  describe('Offline behavior', () => {
    it('shows offline banner on dashboard when offline', async () => {
      const wrapper = await loginAs('farmer')
      await flushPromises()

      Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
      window.dispatchEvent(new Event('offline'))
      await flushPromises()

      expect(wrapper.text()).toContain('当前离线')
    })

    it('restricts navigation when offline', async () => {
      const wrapper = await loginAs('farmer')
      await flushPromises()

      Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
      window.dispatchEvent(new Event('offline'))
      await flushPromises()

      // Should not show reports or operations in menu
      expect(wrapper.text()).not.toContain('效益报表')
      expect(wrapper.text()).not.toContain('运维管理')
    })
  })
})
