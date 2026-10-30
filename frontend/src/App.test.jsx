import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HashRouter } from 'react-router-dom'

vi.mock('./api.js', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
import { api } from './api.js'
import App from './App.jsx'

globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }

const profile = { id: 1, full_name: 'Alex Dev', username: 'alexdev', email: 'alex@example.com', created_at: '2026-01-01T00:00:00Z', is_admin: true }
let signedIn = false

function mockApi() {
  api.get.mockImplementation(async path => {
    if (path === '/api/auth/me') { if (!signedIn) throw new Error('Not signed in'); return { data: profile } }
    if (path === '/api/profile') return { data: { user: profile, theme: 'dark', timezone: 'Asia/Kolkata' } }
    if (path === '/api/admin/overview') return { data: { total_users: 1, new_this_week: 1, new_last_30_days: 1 } }
    if (path === '/api/analytics/weekly') return { data: { weekly: [], recent_activity: [], summary: { tasks_today: 0, completed_today: 0, pending_today: 0, completion_rate: 0, coding_solved: 0, current_streak: 0 } } }
    if (path === '/api/analytics/monthly') return { data: { daily: [], summary: { completed_month: 0, created_month: 0, completion_rate: 0, coding_solved: 0 } } }
    if (path === '/api/activities') return { data: { items: [] } }
    if (path === '/api/coding/questions') return { data: [{ id: 1, title: 'Two Sum', category: 'Arrays', difficulty: 'Easy' }] }
    if (path === '/api/coding/progress') return { data: [] }
    return { data: {} }
  })
  api.post.mockImplementation(async path => { if (path.includes('/auth/')) signedIn = true; return { data: profile } })
  api.put.mockResolvedValue({ data: {} })
  api.patch.mockResolvedValue({ data: {} })
  api.delete.mockResolvedValue({ data: {} })
}

function mount() { return render(<HashRouter><App /></HashRouter>) }

describe('DevStride frontend flows', () => {
  beforeEach(() => { signedIn = false; window.location.hash = '#/'; mockApi() })
  afterEach(cleanup)

  it('shows the public landing page and opens account registration', async () => {
    const user = userEvent.setup()
    mount()
    expect(await screen.findByRole('heading', { name: /make progress/i })).toBeTruthy()
    await user.click(screen.getByRole('link', { name: /start your stride/i }))
    expect(await screen.findByRole('heading', { name: /start your stride/i })).toBeTruthy()
    expect(screen.getByLabelText(/email address/i)).toBeTruthy()
  })

  it('registers and navigates through the dashboard, coding, analytics, and profile', async () => {
    const user = userEvent.setup()
    mount()
    await user.click(await screen.findByRole('link', { name: /start your stride/i }))
    await user.type(screen.getByLabelText(/full name/i), 'Alex Dev')
    await user.type(screen.getByLabelText(/username/i), 'alexdev')
    await user.type(screen.getByLabelText(/email address/i), 'alex@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'Long-secure-pass-123')
    await user.type(screen.getByLabelText(/confirm password/i), 'Long-secure-pass-123')
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeTruthy()
    await user.click(screen.getByRole('link', { name: /coding practice/i }))
    expect(await screen.findByRole('heading', { name: 'Arrays' })).toBeTruthy()
    await user.click(screen.getByRole('link', { name: 'Analytics' }))
    expect(await screen.findByRole('heading', { name: /monthly consistency/i })).toBeTruthy()
    await user.click(screen.getByRole('link', { name: /profile/i }))
    expect(await screen.findByRole('heading', { name: /personal details/i })).toBeTruthy()
    await user.click(screen.getByRole('link', { name: /founder overview/i }))
    expect(await screen.findByText('Registered accounts')).toBeTruthy()
    expect(screen.getAllByText('1', { selector: '.metric-value' })).toHaveLength(3)
    await user.click(screen.getByRole('button', { name: /open navigation/i }))
    await user.click(screen.getByRole('link', { name: /activities/i }))
    await user.click(await screen.findByRole('button', { name: /new activity/i }))
    await user.type(screen.getByLabelText(/activity name/i), 'Review a pull request')
    await user.click(screen.getByRole('button', { name: /create activity/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/activities', expect.objectContaining({ title: 'Review a pull request' })))
  })

  it('redirects private routes to login and accepts a login', async () => {
    const user = userEvent.setup()
    window.location.hash = '#/dashboard'
    mount()
    expect(await screen.findByRole('heading', { name: /log in to devstride/i })).toBeTruthy()
    await user.type(screen.getByLabelText(/email or username/i), 'alexdev')
    await user.type(screen.getByLabelText(/^password$/i), 'Long-secure-pass-123')
    await user.click(screen.getByRole('button', { name: /^log in/i }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Overview' })).toBeTruthy())
  })
})
