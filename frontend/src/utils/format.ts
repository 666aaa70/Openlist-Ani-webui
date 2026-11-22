import type { LanguageCode, TaskStateString } from '@/types/api'

export type TaskCategory = 'active' | 'completed' | 'failed' | 'cancelled'

export interface StateDisplayInfo {
  labelZh: string
  labelEn: string
  stageIndex: number
  category: TaskCategory
  tone: 'sky' | 'amber' | 'emerald' | 'rose' | 'slate'
}

const STATE_MAP: Record<string, StateDisplayInfo> = {
  pending: {
    labelZh: '等待处理',
    labelEn: 'Pending',
    stageIndex: 1,
    category: 'active',
    tone: 'slate',
  },
  downloading: {
    labelZh: '离线下载中',
    labelEn: 'Downloading',
    stageIndex: 2,
    category: 'active',
    tone: 'sky',
  },
  downloaded: {
    labelZh: '已下载待整理',
    labelEn: 'Downloaded',
    stageIndex: 3,
    category: 'active',
    tone: 'sky',
  },
  resolving: {
    labelZh: '解析合集文件',
    labelEn: 'Resolving Files',
    stageIndex: 3,
    category: 'active',
    tone: 'amber',
  },
  renaming: {
    labelZh: '重命名整理中',
    labelEn: 'Renaming',
    stageIndex: 4,
    category: 'active',
    tone: 'amber',
  },
  renamed: {
    labelZh: '已完成重命名',
    labelEn: 'Renamed',
    stageIndex: 4,
    category: 'active',
    tone: 'emerald',
  },
  notifying: {
    labelZh: '发送通知中',
    labelEn: 'Notifying',
    stageIndex: 5,
    category: 'active',
    tone: 'amber',
  },
  completed: {
    labelZh: '已完成',
    labelEn: 'Completed',
    stageIndex: 5,
    category: 'completed',
    tone: 'emerald',
  },
  failed: {
    labelZh: '失败',
    labelEn: 'Failed',
    stageIndex: 0,
    category: 'failed',
    tone: 'rose',
  },
  cancelled: {
    labelZh: '已取消 / 跳过',
    labelEn: 'Cancelled',
    stageIndex: 0,
    category: 'cancelled',
    tone: 'slate',
  },
  skipped: {
    labelZh: '已跳过',
    labelEn: 'Skipped',
    stageIndex: 0,
    category: 'cancelled',
    tone: 'slate',
  },
}

export function getTaskStateInfo(state: TaskStateString): StateDisplayInfo {
  return (
    STATE_MAP[state] ?? {
      labelZh: state,
      labelEn: state,
      stageIndex: 0,
      category: 'active',
      tone: 'slate',
    }
  )
}

export function getTaskStateLabel(state: TaskStateString, lang: LanguageCode = 'zh-CN'): string {
  const info = getTaskStateInfo(state)
  return lang === 'en-US' ? info.labelEn : info.labelZh
}

export function isActiveState(state: TaskStateString): boolean {
  return getTaskStateInfo(state).category === 'active'
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes) || bytes < 0) {
    return '-'
  }
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx += 1
  }
  return `${size >= 100 || idx === 0 ? size.toFixed(0) : size.toFixed(size >= 10 ? 1 : 2)} ${units[idx]}`
}

export function formatDateTime(iso: string | null | undefined, lang: LanguageCode = 'zh-CN'): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(lang === 'en-US' ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatSeasonEpisode(season: number | null, episode: number | null): string | null {
  if (season === null && episode === null) return null
  const s = season !== null ? `S${String(season).padStart(2, '0')}` : ''
  const e = episode !== null ? `E${String(episode).padStart(2, '0')}` : ''
  return `${s}${e}` || null
}

export function shortTaskId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id
}
