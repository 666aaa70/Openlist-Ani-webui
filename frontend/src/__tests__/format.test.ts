import { describe, expect, it } from 'vitest'
import { formatBytes, formatSeasonEpisode, getTaskStateInfo, getTaskStateLabel } from '@/utils/format'

describe('format utilities', () => {
  it('formats file byte sizes cleanly', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1024)).toBe('1.00 KB')
    expect(formatBytes(734_003_200)).toBe('700 MB')
    expect(formatBytes(null)).toBe('-')
  })

  it('formats season and episode badges', () => {
    expect(formatSeasonEpisode(1, 3)).toBe('S01E03')
    expect(formatSeasonEpisode(2, null)).toBe('S02')
    expect(formatSeasonEpisode(null, 12)).toBe('E12')
    expect(formatSeasonEpisode(null, null)).toBeNull()
  })

  it('maps real Openlist-Ani states to categories and Chinese labels', () => {
    expect(getTaskStateInfo('downloading').category).toBe('active')
    expect(getTaskStateInfo('renaming').category).toBe('active')
    expect(getTaskStateInfo('completed').category).toBe('completed')
    expect(getTaskStateInfo('failed').category).toBe('failed')
    expect(getTaskStateLabel('downloading', 'zh-CN')).toBe('离线下载中')
    expect(getTaskStateLabel('completed', 'en-US')).toBe('Completed')
  })
})
