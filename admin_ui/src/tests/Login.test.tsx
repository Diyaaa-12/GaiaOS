import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Login } from '../pages/Login';
import * as client from '../api/client';
import { AUTH_TOKEN_KEY } from '../utils/auth';

// Mock the API client module so we don't hit a real server.
vi.mock('../api/client', () => ({
  login: vi.fn(),
  ApiError: class ApiError extends Error {
    status: string;
    httpStatus?: number;
    constructor(status: string, httpStatus?: number, message?: string) {
      super(message ?? status);
      this.status = status;
      this.httpStatus = httpStatus;
      this.name = 'ApiError';
    }
  },
}));

const renderLoginWithRoutes = (initialEntry = '/login') =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/metrics" element={<div>Metrics Destination</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders email and password inputs', () => {
    renderLoginWithRoutes();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('calls login() and redirects to /metrics on success', async () => {
    const mockLogin = vi.mocked(client.login).mockResolvedValue('mock-token');

    renderLoginWithRoutes();

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'admin@gaiaos.internal' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'secret123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin@gaiaos.internal', 'secret123');
    });

    await waitFor(() => {
      expect(screen.getByText('Metrics Destination')).toBeInTheDocument();
    });
  });

  it('automatically redirects to /metrics when user is already authenticated', () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'already-logged-in-token');

    renderLoginWithRoutes();

    expect(screen.getByText('Metrics Destination')).toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  });

  it('shows an error message when credentials are invalid', async () => {
    const { ApiError } = await import('../api/client');
    vi.mocked(client.login).mockRejectedValue(
      new ApiError('unauthorized', 401, 'Invalid email or password.'),
    );

    renderLoginWithRoutes();
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'wrongpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/invalid email or password/i);
  });

  it('shows unreachable error when API cannot be reached', async () => {
    const { ApiError } = await import('../api/client');
    vi.mocked(client.login).mockRejectedValue(
      new ApiError('unreachable', undefined, 'Cannot reach GaiaOS API'),
    );

    renderLoginWithRoutes();
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'admin@gaiaos.internal' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot reach gaiaos api/i);
  });
});
