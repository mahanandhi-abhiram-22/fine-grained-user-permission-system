import axios from 'axios';

// The backend base URL can be overridden at build/dev time with VITE_API_URL
// (see frontend/.env.example). The default keeps `npm run dev` working with no
// extra configuration against a backend on the default Django port.
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
});

let refreshRequest;

const clearSession = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.dispatchEvent(new Event('auth:expired'));
};

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

api.interceptors.response.use((response) => response, async (error) => {
  const originalRequest = error.config;
  const requestUrl = originalRequest?.url || '';
  const isPublicTokenRequest = requestUrl.includes('/accounts/login/') || requestUrl.includes('/accounts/token/refresh/');

  if (error.response?.status !== 401 || !originalRequest || originalRequest._retry || isPublicTokenRequest) {
    return Promise.reject(error);
  }

  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) {
    clearSession();
    return Promise.reject(error);
  }

  originalRequest._retry = true;
  try {
    if (!refreshRequest) {
      refreshRequest = axios.post(`${API_BASE_URL}/accounts/token/refresh/`, { refresh: refreshToken })
        .then((response) => response.data.access)
        .finally(() => {
          refreshRequest = null;
        });
    }
    const accessToken = await refreshRequest;
    if (!accessToken) {
      throw new Error('Token refresh returned no access token.');
    }
    localStorage.setItem('access_token', accessToken);
    originalRequest.headers = originalRequest.headers || {};
    originalRequest.headers.Authorization = `Bearer ${accessToken}`;
    return api(originalRequest);
  } catch (refreshError) {
    clearSession();
    return Promise.reject(refreshError);
  }
});

export default api;
