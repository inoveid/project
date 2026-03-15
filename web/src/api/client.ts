export const BASE_URL = "/api";

function getToken(): string | null {
  return localStorage.getItem("ac_token");
}

export function setToken(token: string): void {
  localStorage.setItem("ac_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("ac_token");
}

export function hasToken(): boolean {
  return !!localStorage.getItem("ac_token");
}

export async function fetchApi<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearToken();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    const body = await response.text();
    // Try to extract detail from FastAPI error response
    let message = body;
    try {
      const json = JSON.parse(body);
      if (json.detail) {
        message = typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail);
      }
    } catch {
      // body is not JSON, use as-is
    }
    throw new Error(message || `Ошибка ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
