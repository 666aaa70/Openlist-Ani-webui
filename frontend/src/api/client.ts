import type {
  ApiErrorPayload,
  AuthUserResponse,
  CreateDownloadRequest,
  CreateDownloadResponse,
  DownloadListResponse,
  DownloadPreflightRequest,
  DownloadPreflightResponse,
  DownloadTaskResponse,
  LogoutResponse,
  ResolveResourceResponse,
  ServiceHealthResponse,
  SettingsResponse,
  UpdateSettingsRequest,
} from '@/types/api'

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.details = details
  }
}

let csrfTokenGetter: () => string | null = () => null
let unauthorizedHandler: (() => void) | null = null

export function configureApiClient(options: {
  getCsrfToken: () => string | null
  onUnauthorized: () => void
}): void {
  csrfTokenGetter = options.getCsrfToken
  unauthorizedHandler = options.onUnauthorized
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  skipUnauthorizedRedirect?: boolean
  signal?: AbortSignal
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  if (method !== 'GET') {
    const token = csrfTokenGetter()
    if (token) {
      headers['X-CSRF-Token'] = token
    }
  }

  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: 'include',
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiClientError(0, 'aborted', '请求已取消')
    }
    throw new ApiClientError(0, 'network_error', '无法连接到 WebUI 服务端，请检查网络或容器运行状态')
  }

  let parsed: unknown = null
  const text = await response.text()
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = null
    }
  }

  if (!response.ok) {
    const errPayload = (parsed && typeof parsed === 'object' ? parsed : {}) as Partial<ApiErrorPayload>
    const code = errPayload.code || `http_${response.status}`
    const message = errPayload.message || `请求失败 (${response.status})`
    const details = errPayload.details || {}

    if (response.status === 401 && !options.skipUnauthorizedRedirect && unauthorizedHandler) {
      unauthorizedHandler()
    }
    throw new ApiClientError(response.status, code, message, details)
  }

  return parsed as T
}

export const api = {
  // Auth
  login(username: string, password: string): Promise<AuthUserResponse> {
    return request<AuthUserResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: { username, password },
      skipUnauthorizedRedirect: true,
    })
  },

  logout(): Promise<LogoutResponse> {
    return request<LogoutResponse>('/api/v1/auth/logout', {
      method: 'POST',
    })
  },

  me(): Promise<AuthUserResponse> {
    return request<AuthUserResponse>('/api/v1/auth/me', {
      method: 'GET',
      skipUnauthorizedRedirect: true,
    })
  },

  // Health
  getHealth(): Promise<ServiceHealthResponse> {
    return request<ServiceHealthResponse>('/api/v1/health')
  },

  // Resolve
  resolveMagnet(magnet: string, metadataTimeout = 30): Promise<ResolveResourceResponse> {
    return request<ResolveResourceResponse>('/api/v1/resolve/magnet', {
      method: 'POST',
      body: { magnet, metadata_timeout: metadataTimeout },
    })
  },

  resolveTorrent(url: string): Promise<ResolveResourceResponse> {
    return request<ResolveResourceResponse>('/api/v1/resolve/torrent', {
      method: 'POST',
      body: { url },
    })
  },

  // Downloads
  preflightDownload(payload: DownloadPreflightRequest): Promise<DownloadPreflightResponse> {
    return request<DownloadPreflightResponse>('/api/v1/downloads/preflight', {
      method: 'POST',
      body: payload,
    })
  },

  createDownload(payload: CreateDownloadRequest): Promise<CreateDownloadResponse> {
    return request<CreateDownloadResponse>('/api/v1/downloads', {
      method: 'POST',
      body: payload,
    })
  },

  listDownloads(): Promise<DownloadListResponse> {
    return request<DownloadListResponse>('/api/v1/downloads')
  },

  getDownload(taskId: string): Promise<DownloadTaskResponse> {
    return request<DownloadTaskResponse>(`/api/v1/downloads/${encodeURIComponent(taskId)}`)
  },

  // Settings
  getSettings(): Promise<SettingsResponse> {
    return request<SettingsResponse>('/api/v1/settings')
  },

  updateSettings(payload: UpdateSettingsRequest): Promise<SettingsResponse> {
    return request<SettingsResponse>('/api/v1/settings', {
      method: 'PUT',
      body: payload,
    })
  },

  testConnection(): Promise<ServiceHealthResponse> {
    return request<ServiceHealthResponse>('/api/v1/settings/test-connection', {
      method: 'POST',
    })
  },
}
