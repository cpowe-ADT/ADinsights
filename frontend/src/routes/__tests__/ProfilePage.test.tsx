import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ProfilePage from '../ProfilePage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchProfile: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchProfile: phase2ApiMock.fetchProfile,
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin' }, logout: vi.fn() }),
}));

vi.mock('../../components/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
}));

const mockProfile = {
  user: {
    id: 'u1',
    email: 'tester@example.com',
    first_name: 'Test',
    last_name: 'User',
    tenant: 'acme',
    timezone: 'America/Jamaica',
    roles: ['admin', 'viewer'],
  },
  tenant_id: 'tenant-123',
};

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders user profile after loading', async () => {
    phase2ApiMock.fetchProfile.mockResolvedValue(mockProfile);

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('My Profile')).toBeInTheDocument();
    });

    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('tester@example.com')).toBeInTheDocument();
    expect(screen.getByText('America/Jamaica')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('viewer')).toBeInTheDocument();
    expect(screen.getByText('tenant-123')).toBeInTheDocument();
  });

  it('renders roles as pills', async () => {
    phase2ApiMock.fetchProfile.mockResolvedValue(mockProfile);

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('My Profile')).toBeInTheDocument();
    });

    const adminPill = screen.getByText('admin');
    expect(adminPill).toHaveClass('phase2-pill');
    const viewerPill = screen.getByText('viewer');
    expect(viewerPill).toHaveClass('phase2-pill');
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.fetchProfile.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Profile unavailable')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('has sign out button', async () => {
    phase2ApiMock.fetchProfile.mockResolvedValue(mockProfile);

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Sign out')).toBeInTheDocument();
    });
  });
});
