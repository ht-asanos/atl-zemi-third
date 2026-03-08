const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

export async function apiClient<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    ;(headers as Record<string, string>)['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail || res.statusText)
  }

  return res.json()
}
