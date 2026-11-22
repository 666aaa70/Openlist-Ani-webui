import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NewDownloadModal from '@/components/downloads/NewDownloadModal.vue'
import { api } from '@/api/client'

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>('@/api/client')
  return {
    ...actual,
    api: {
      ...actual.api,
      resolveMagnet: vi.fn(),
      resolveTorrent: vi.fn(),
      preflightDownload: vi.fn(),
      createDownload: vi.fn(),
    },
  }
})

describe('NewDownloadModal MVP workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('resolves magnet, displays file list, confirms policy conflict, and submits download', async () => {
    const magnet = 'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Frieren'
    vi.mocked(api.resolveMagnet).mockResolvedValue({
      success: true,
      message: 'Resolved magnet metadata',
      title: '[LoliHouse] Frieren - 01-28 [BDRip 1080p]',
      source: 'metadata',
      error_code: null,
      file_count: 2,
      files: [
        { name: 'Frieren/01.mkv', size: 600_000_000, is_video: true },
        { name: 'Frieren/02.mkv', size: 610_000_000, is_video: true },
      ],
      video_file_count: 2,
      inspection_incomplete: false,
      collection_hint: true,
      resource_type: 'magnet',
    })

    vi.mocked(api.preflightDownload).mockResolvedValue({
      success: true,
      message: 'Manual download requires confirmation',
      confirmation_required: true,
      policy_conflicts: [
        {
          key: 'collection:manual',
          code: 'collection_override',
          reason: '检测到合集资源，确认后将绕过自动 RSS 策略',
          matched: 'collection_hint=true',
          details: {},
        },
      ],
      policy_warnings: ['合集将在下载完成后逐集解析'],
      policy_review_token: 'review-tok-xyz',
    })

    vi.mocked(api.createDownload).mockResolvedValue({
      success: true,
      message: 'Manual download queued',
      task: {
        id: 'task-999',
        title: '[LoliHouse] Frieren - 01-28 [BDRip 1080p]',
        download_url: magnet,
        state: 'pending',
        anime_name: null,
        season: null,
        episode: null,
        fansub: 'LoliHouse',
        quality: '1080p',
        error_message: null,
        retry_count: 0,
        created_at: '2026-11-21T10:00:00Z',
        updated_at: '2026-11-21T10:00:00Z',
        started_at: null,
        completed_at: null,
        save_path: '/PikPak/Anime',
        final_path: null,
        final_paths: [],
        warning_count: 0,
        items: [],
      },
      confirmation_required: false,
      policy_conflicts: [],
      policy_warnings: [],
      policy_review_token: null,
    })

    const wrapper = mount(NewDownloadModal, {
      props: { open: true },
      global: { stubs: { Teleport: true } },
    })

    // Paste magnet and trigger resolve
    await wrapper.find('#download-link-input').setValue(magnet)
    await wrapper.find('#resolve-resource-btn').trigger('click')
    await flushPromises()

    expect(api.resolveMagnet).toHaveBeenCalledWith(magnet, 30, expect.any(AbortSignal))
    expect((wrapper.find('#download-title-input').element as HTMLInputElement).value).toBe(
      '[LoliHouse] Frieren - 01-28 [BDRip 1080p]',
    )
    expect(wrapper.text()).toContain('Frieren/01.mkv')
    expect(wrapper.text()).toContain('识别为合集')

    // First submit triggers preflight -> displays conflict panel and requires explicit checkbox
    await wrapper.find('#submit-download-btn').trigger('click')
    await flushPromises()

    expect(api.preflightDownload).toHaveBeenCalledWith({
      download_url: magnet,
      title: '[LoliHouse] Frieren - 01-28 [BDRip 1080p]',
      collection_hint: true,
    })
    expect(api.createDownload).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('检测到合集资源，确认后将绕过自动 RSS 策略')
    expect(
      (wrapper.find('#submit-download-btn').element as HTMLButtonElement).disabled,
    ).toBe(true)

    // User explicitly checks confirmation box and submits
    await wrapper.find('#confirm-policy-conflicts-checkbox').setValue(true)
    await wrapper.find('#submit-download-btn').trigger('click')
    await flushPromises()

    expect(api.createDownload).toHaveBeenCalledWith({
      download_url: magnet,
      title: '[LoliHouse] Frieren - 01-28 [BDRip 1080p]',
      collection_hint: true,
      override_policy: true,
      acknowledged_conflicts: ['collection:manual'],
      policy_review_token: 'review-tok-xyz',
    })
    expect(wrapper.emitted('created')?.[0]).toEqual(['task-999'])
  })
})
