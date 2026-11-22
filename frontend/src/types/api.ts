/**
 * Strict TypeScript definitions mirroring TwooSix/Openlist-Ani HTTP schemas
 * and the Openlist-Ani-webui backend API contracts.
 */

export type ThemeMode = 'dark' | 'light'
export type LanguageCode = 'zh-CN' | 'en-US'

/**
 * Exact states returned by Openlist-Ani DownloadJob.api_state().
 */
export type OpenlistTaskState =
  | 'pending'
  | 'downloading'
  | 'downloaded'
  | 'resolving'
  | 'renaming'
  | 'renamed'
  | 'notifying'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type TaskStateString = OpenlistTaskState | (string & {})

export interface ApiErrorPayload {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface AuthUserResponse {
  authenticated: boolean
  username: string
  csrf_token: string
}

export interface LogoutResponse {
  success: boolean
  message: string
}

export interface UpstreamWorkersStatus {
  running: number
  expected: number
}

export interface ServiceHealthResponse {
  webui_status: 'ok'
  upstream_reachable: boolean
  upstream_live: boolean
  upstream_ready: boolean
  upstream_status: string
  degraded: Record<string, string>
  workers: UpstreamWorkersStatus | null
  latency_ms: number | null
  error_code: string | null
  error_message: string | null
  checked_at: string
}

export interface ResolveFileItem {
  name: string
  size: number
  is_video: boolean
}

export interface ResolveResourceResponse {
  success: boolean
  message: string
  title: string | null
  source: 'dn' | 'metadata' | 'torrent_file' | null
  error_code: string | null
  file_count: number | null
  files: ResolveFileItem[]
  video_file_count: number
  inspection_incomplete: boolean
  collection_hint: boolean
  resource_type: 'magnet' | 'torrent'
}

export interface PolicyConflictResponse {
  key: string
  code: string
  reason: string
  matched: string
  details: Record<string, unknown>
}

export interface DownloadPreflightRequest {
  download_url: string
  title: string
  collection_hint: boolean
}

export interface DownloadPreflightResponse {
  success: boolean
  message: string
  confirmation_required: boolean
  policy_conflicts: PolicyConflictResponse[]
  policy_warnings: string[]
  policy_review_token: string | null
}

export interface CreateDownloadRequest {
  download_url: string
  title: string
  collection_hint: boolean
  override_policy: boolean
  acknowledged_conflicts: string[]
  policy_review_token: string | null
}

export interface DownloadItemResponse {
  item_key: string
  state: string
  source_path: string | null
  final_path: string | null
  error: string | null
  anime_name: string | null
  season: number | null
  episode: number | null
}

export interface DownloadTaskResponse {
  id: string
  title: string
  download_url: string
  state: TaskStateString
  anime_name: string | null
  season: number | null
  episode: number | null
  fansub: string | null
  quality: string | null
  error_message: string | null
  retry_count: number
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
  save_path: string
  final_path: string | null
  final_paths: string[]
  warning_count: number
  items: DownloadItemResponse[]
}

export interface DownloadListResponse {
  tasks: DownloadTaskResponse[]
  total: number
  active_count: number
  completed_count: number
  failed_count: number
  cancelled_count: number
  synced_at: string
}

export interface CreateDownloadResponse {
  success: boolean
  message: string
  task: DownloadTaskResponse | null
  confirmation_required: boolean
  policy_conflicts: PolicyConflictResponse[]
  policy_warnings: string[]
  policy_review_token: string | null
}

export interface SettingsResponse {
  upstream_configured: boolean
  upstream_masked: string
  api_timeout_seconds: number
  poll_interval_seconds: number
  theme: ThemeMode
  language: LanguageCode
}

export interface UpdateSettingsRequest {
  upstream_url?: string | null
  api_timeout_seconds?: number
  poll_interval_seconds?: number
  theme?: ThemeMode
  language?: LanguageCode
}
