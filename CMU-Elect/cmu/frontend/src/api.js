const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api").replace(/\/$/, "");

function getErrorMessage(data, fallback = "Request failed.") {
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") return data.detail;
    const messages = Object.values(data)
      .flatMap(value => Array.isArray(value) ? value : [value])
      .filter(value => typeof value === "string");
    if (messages.length) return messages.join(" ");
  }
  return fallback;
}

export async function api(path, options = {}) {
  const token = localStorage.getItem("token");
  const headers = {
    ...(options.headers || {}),
  };

  // Let the browser set the multipart boundary when uploading files.
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (token) headers.Authorization = `Token ${token}`;

  let response;
  try {
    response = await fetch(`${API}${path}`, { ...options, headers });
  } catch (_) {
    throw new Error(
      "Unable to connect to the CMU-ELECT API. Make sure Django is running on the configured API address."
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401) {
      clearAuth();
    }
    throw new Error(
      getErrorMessage(data, `Server error (${response.status}). Please try again.`)
    );
  }

  return data;
}

export function healthCheck() {
  return api("/health/");
}

export function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export function mediaUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  const origin = API.replace(/\/api$/, "");
  return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
}
