import { describe, expect, it } from 'vitest'
import {
  allowsManualTitleFallback,
  computeCollectionAssessment,
  detectResourceType,
  isVideoFilename,
} from '@/utils/torrent'

describe('torrent utilities', () => {
  it('detects magnet links and http(s) torrent links accurately', () => {
    expect(detectResourceType('magnet:?xt=urn:btih:0123456789abcdef')).toBe('magnet')
    expect(detectResourceType('  MAGNET:?xt=urn:btih:abcdef  ')).toBe('magnet')
    expect(detectResourceType('https://example.org/test.torrent')).toBe('torrent')
    expect(detectResourceType('http://tracker.local/file.torrent')).toBe('torrent')
    expect(detectResourceType('ftp://example.org/file.torrent')).toBe('unknown')
    expect(detectResourceType('just some anime title')).toBe('unknown')
  })

  it('recognizes official Openlist-Ani video extensions', () => {
    expect(isVideoFilename('01.mkv')).toBe(true)
    expect(isVideoFilename('folder/ep02.MP4')).toBe(true)
    expect(isVideoFilename('subs/ep01.ass')).toBe(false)
    expect(isVideoFilename('readme.txt')).toBe(false)
  })

  it('computes collection_hint matching Openlist-Ani official rules', () => {
    const single = computeCollectionAssessment({
      files: [
        { name: 'ep01.mkv', size: 1000, is_video: true },
        { name: 'ep01.ass', size: 100, is_video: false },
      ],
      errorCode: null,
      resourceType: 'magnet',
    })
    expect(single).toEqual({
      videoCount: 1,
      inspectionIncomplete: false,
      collectionHint: false,
    })

    const multi = computeCollectionAssessment({
      files: [
        { name: 'ep01.mkv', size: 1000, is_video: true },
        { name: 'ep02.mkv', size: 1000, is_video: true },
      ],
      errorCode: null,
      resourceType: 'torrent',
    })
    expect(multi.collectionHint).toBe(true)
    expect(multi.videoCount).toBe(2)

    const incomplete = computeCollectionAssessment({
      files: [],
      errorCode: 'metadata_timeout',
      resourceType: 'magnet',
    })
    expect(incomplete.inspectionIncomplete).toBe(true)
    expect(incomplete.collectionHint).toBe(true)
  })

  it('distinguishes manual title fallback from hard resolver errors', () => {
    expect(allowsManualTitleFallback('magnet', 'metadata_timeout')).toBe(true)
    expect(allowsManualTitleFallback('magnet', 'libtorrent_unavailable')).toBe(false)
    expect(allowsManualTitleFallback('magnet', 'invalid_magnet')).toBe(false)
    expect(allowsManualTitleFallback('torrent', 'torrent_parse_failed')).toBe(false)
  })
})
