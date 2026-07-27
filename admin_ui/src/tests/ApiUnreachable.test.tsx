import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ApiUnreachable } from '../components/ApiUnreachable';
import { ApiError } from '../api/client';

describe('ApiUnreachable component', () => {
  it('renders the cannot-reach banner for an unreachable error', () => {
    const error = new ApiError('unreachable', undefined, 'Cannot reach GaiaOS API');
    render(<ApiUnreachable error={error} intervalMs={30_000} />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/cannot reach gaiaos api/i);
    expect(alert).toHaveTextContent(/retrying every 30s/i);
  });

  it('renders an HTTP-error banner for a server error', () => {
    const error = new ApiError('server_error', 500, 'HTTP 500');
    render(<ApiUnreachable error={error} />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/api error \(http 500\)/i);
  });

  it('renders a forbidden banner for a 403 error', () => {
    const error = new ApiError('forbidden', 403, 'ADMIN role required');
    render(<ApiUnreachable error={error} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(/admin role required/i);
  });
});
