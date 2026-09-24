import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const REFRESH_STORAGE_KEY = "ivs_refresh_token";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_STORAGE_KEY);
}

export function setStoredRefreshToken(token: string | null) {
  if (token) localStorage.setItem(REFRESH_STORAGE_KEY, token);
  else localStorage.removeItem(REFRESH_STORAGE_KEY);
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getStoredRefreshToken();
  if (!refresh) return null;

  try {
    const resp = await axios.post(`${API_BASE_URL}/api/token/refresh/`, { refresh });
    const newAccess = resp.data.access as string;
    // SIMPLE_JWT'da ROTATE_REFRESH_TOKENS=True - har yangilashda eski refresh
    // token bekor qilinadi (blacklist) va yangisi qaytadi. Uni ham saqlashimiz
    // shart, aks holda keyingi yangilashda 401 bilan sessiya uzilib qoladi.
    const newRefresh = resp.data.refresh as string | undefined;
    setAccessToken(newAccess);
    if (newRefresh) setStoredRefreshToken(newRefresh);
    return newAccess;
  } catch {
    setAccessToken(null);
    setStoredRefreshToken(null);
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;

      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccess = await refreshPromise;

      if (newAccess) {
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${newAccess}`;
        return api(original);
      }
    }

    return Promise.reject(error);
  },
);

export async function loginRequest(username: string, password: string) {
  const resp = await axios.post(`${API_BASE_URL}/api/token/`, { username, password });
  const { access, refresh } = resp.data as { access: string; refresh: string };
  setAccessToken(access);
  setStoredRefreshToken(refresh);
  return access;
}

export async function tryRestoreSession(): Promise<boolean> {
  const newAccess = await refreshAccessToken();
  return !!newAccess;
}

export function logout() {
  setAccessToken(null);
  setStoredRefreshToken(null);
}
