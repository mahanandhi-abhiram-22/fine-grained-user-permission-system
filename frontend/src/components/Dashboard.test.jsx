import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from '../services/api';
import App from '../App.jsx';
import Dashboard from './Dashboard.jsx';

const firstPage = {
  count: 21,
  next: 'http://127.0.0.1:8000/api/employees/?page=2',
  previous: null,
  results: [{
    id: 1,
    user: 5,
    employee_code: 'EMP-001',
    first_name: 'First',
    last_name: 'Page',
    department: 'Engineering',
  }],
};

const secondPage = {
  count: 21,
  next: null,
  previous: 'http://127.0.0.1:8000/api/employees/?page=1',
  results: [{
    id: 2,
    user: 6,
    employee_code: 'EMP-002',
    first_name: 'Second',
    last_name: 'Page',
    department: 'Finance',
  }],
};

describe('permission-aware dashboard', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => cleanup());

  it('does not grant employee actions to a superuser without function codes', async () => {
    api.get.mockResolvedValueOnce({ data: { id: 5, is_superuser: true, permissions: [] } });

    render(<Dashboard onLogout={vi.fn()} />);

    expect(await screen.findByText('Superuser account; employee function permissions still apply.')).toBeInTheDocument();
    expect(screen.queryByText('Employee Directory')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Manage user permissions' })).not.toBeInTheDocument();
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it('loads registered functions and replaces another user\'s permission set', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['ASSIGN_PERMISSION'] } })
      .mockResolvedValueOnce({ data: {
        users: [{ id: 7, email: 'member@example.test', permissions: [] }],
        functions: [{ code: 'VIEW_EMPLOYEE', name: 'View Employee' }, { code: 'VIEW_SELF', name: 'View Self' }],
      } });
    api.post.mockResolvedValueOnce({ data: { detail: 'Permissions updated successfully.' } });

    render(<Dashboard onLogout={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Manage user permissions' }));
    fireEvent.change(await screen.findByLabelText('Target user'), { target: { value: '7' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /VIEW_SELF/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save permissions' }));

    expect(await screen.findByText('Permissions updated successfully.')).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/permissions/assign/', {
      user_id: 7,
      function_codes: ['VIEW_SELF'],
    });
  });

  it('renders paginated results and follows next and previous links', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_EMPLOYEE'] } })
      .mockResolvedValueOnce({ data: firstPage })
      .mockResolvedValueOnce({ data: secondPage })
      .mockResolvedValueOnce({ data: firstPage });

    render(<Dashboard onLogout={vi.fn()} />);

    expect(await screen.findByText('Total employees: 21')).toBeInTheDocument();
    expect(screen.getByText('EMP-001')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText('EMP-002')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled();
    expect(api.get).toHaveBeenNthCalledWith(3, secondPage.previous.replace('?page=1', '?page=2'));

    fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(await screen.findByText('EMP-001')).toBeInTheDocument();
  });

  it('shows an employee API error without discarding the dashboard', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_EMPLOYEE'] } })
      .mockRejectedValueOnce({ response: { data: { detail: 'Employee list unavailable.' } } });

    render(<Dashboard onLogout={vi.fn()} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Employee list unavailable.');
    expect(screen.getByText('Employee Directory')).toBeInTheDocument();
  });

  it('shows My Profile to a user holding VIEW_SELF', async () => {
    api.get.mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_SELF'] } });

    render(<Dashboard onLogout={vi.fn()} />);

    expect(await screen.findByRole('button', { name: 'My Profile' })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it('hides My Profile from a user without VIEW_SELF', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_EMPLOYEE'] } })
      .mockResolvedValueOnce({ data: firstPage });

    render(<Dashboard onLogout={vi.fn()} />);

    expect(await screen.findByText('Employee Directory')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'My Profile' })).not.toBeInTheDocument();
  });

  it('renders the caller employee record returned by /employees/me/', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_SELF'] } })
      .mockResolvedValueOnce({
        data: {
          id: 9,
          user: 5,
          employee_code: 'EMP-009',
          first_name: 'Self',
          last_name: 'Viewer',
          department: 'Security',
        },
      });

    render(<Dashboard onLogout={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'My Profile' }));

    expect(await screen.findByText('EMP-009')).toBeInTheDocument();
    expect(screen.getByText('Self')).toBeInTheDocument();
    expect(screen.getByText('Viewer')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/employees/me/');
  });

  it('explains a missing profile when /employees/me/ returns 404', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_SELF'] } })
      .mockRejectedValueOnce({ response: { status: 404, data: { detail: 'Employee profile not found.' } } });

    render(<Dashboard onLogout={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'My Profile' }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('No employee profile found for your account.');
  });

  it('explains a conflicting profile when /employees/me/ returns 409', async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: ['VIEW_SELF'] } })
      .mockRejectedValueOnce({
        response: { status: 409, data: { detail: 'Multiple employee records are associated with this user.' } },
      });

    render(<Dashboard onLogout={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'My Profile' }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('Multiple employee records are associated with this user.');
  });

  it('returns to login when the API reports an expired session', async () => {
    localStorage.setItem('access_token', 'expired-placeholder');
    api.get.mockResolvedValueOnce({ data: { id: 5, is_superuser: false, permissions: [] } });

    render(<App />);
    window.dispatchEvent(new Event('auth:expired'));

    expect(await screen.findByText('Employee Portal Login')).toBeInTheDocument();
  });
});