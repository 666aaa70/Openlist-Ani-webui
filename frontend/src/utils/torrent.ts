import type { ResolveFileItem } from '@/types/api'

export type DetectedResourceType = 'magnet' | 'torrent' | 'unknown'

const VIDEO_EXTS = new Set([
  '.mp4',
  '.mkv',
  '.avi',
  '.mov',
  '.flv',
  '.wmv',
  '.webm',
  '.mpg',
  '.mpeg',
])

const INCOMPLETE_ERROR_CODES = new Set([
  'libtorrent_unavailable',
  'metadata_fetch_failed',
  'metadata_timeout',
  'file_list_unavailable',
])

export function detectResourceType(raw: string): DetectedResourceType {
  const cleaned = raw.trim()
  const lower = cleaned.toLowerCase()
  if (lower.startsWith('magnet:?')) {
    return 'magnet'
  }
  if (lower.startsWith('http://') || lower.startsWith('https://')) {
    return 'torrent'
  }
  return 'unknown'
}

export function isVideoFilename(filename: string): boolean {
  const dotIdx = filename.lastIndexOf('.')
  if (dotIdx < 0) return false
  return VIDEO_EXTS.has(filename.slice(dotIdx).toLowerCase())
}

export function computeCollectionAssessment(params: {
  files: ResolveFileItem[]
  errorCode: string | null
  resourceType: 'magnet' | 'torrent'
}): {
  videoCount: number
  inspectionIncomplete: boolean
  collectionHint: boolean
} {
  const videoCount = params.files.filter((f) => f.is_video || isVideoFilename(f.name)).length
  const inspectionIncomplete =
    params.resourceType === 'magnet' &&
    params.errorCode !== null &&
    INCOMPLETE_ERROR_CODES.has(params.errorCode)
  const collectionHint = videoCount > 1 || inspectionIncomplete
  return { videoCount, inspectionIncomplete, collectionHint }
}

/**
 * Determine if resolver failure still allows the user to manually supply a real title.
 * Mirrors official Openlist-Ani resolve_magnet.py / resolve_torrent.py guidance.
 */
export function allowsManualTitleFallback(
  resourceType: 'magnet' | 'torrent',
  errorCode: string | null,
): boolean {
  if (resourceType === 'magnet') {
    return errorCode === 'metadata_timeout' || errorCode === 'metadata_fetch_failed'
  }
  return false
}
