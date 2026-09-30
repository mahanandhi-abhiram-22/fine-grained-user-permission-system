import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import api from './api.js';

const unauthorizedResponse = (config) => ({
  data: { detail: 'Authentication credentials were not provided.' },
  status: 401,
  statusText: 'Unauthorized',
  headers: {},
  config,
});

const unauthorizedError = (config) => new axios.AxiosError(
  'Unauthorized',
  axios.AxiosError.ERR_BAD_REQUEST,
  config,
  null,
  unauthorizedResponse(config),
);

describe('API authentication lifecycle', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    api.defaults.adapter = undefined;
    vi.restoreAllMocks();
  });

  it('refreshes once and retries a protected request with the new access token', async () => {
    localStorage.setItem('access_token', 'expired-access');
    localStorage.setItem('refresh_token', 'valid-refresh');
    const adapter = vi.fn(async (config) => {
      if (config.headers.Authorization === 'Bearer expired-access') {
        throw unauthorizedError(config);
      }
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
    });
    api.defaults.adapter = adapter;
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { access: 'new-access' } });

    const response = await api.get('/protected/');

    expect(response.data).toEqual({ ok: true });
    expect(adapter).toHaveBeenCalledTimes(2);
    expect(adapter.mock.calls[1][0].headers.Authorization).toBe('Bearer new-access');
    expect(refresh).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/accounts/token/refresh/',
      { refresh: 'valid-refresh' },
    );
    expect(localStorage.getItem('access_token')).toBe('new-access');
  });

  it('clears the local session and emits auth:expired when refresh fails', async () => {
    localStorage.setItem('access_token', 'expired-access');
    localStorage.setItem('refresh_token', 'expired-refresh');
    api.defaults.adapter = async (config) => {
      throw unauthorizedError(config);
    };
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('Refresh rejected'));
    const sessionExpired = vi.fn();
    window.addEventListener('auth:expired', sessionExpired);

    await expect(api.get('/protected/')).rejects.toThrow('Refresh rejected');

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(sessionExpired).toHaveBeenCalledTimes(1);
    window.removeEventListener('auth:expired', sessionExpired);
  });

  it('does not try refresh after invalid login credentials', async () => {
    api.defaults.adapter = async (config) => {
      throw unauthorizedError(config);
    };
    const refresh = vi.spyOn(axios, 'post');

    await expect(api.post('/accounts/login/', { email: 'bad@example.test', password: 'wrong' }))
      .rejects.toMatchObject({ response: { status: 401 } });

    expect(refresh).not.toHaveBeenCalled();
  });
});