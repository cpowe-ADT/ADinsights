import {
  type FocusEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react';

import { useAuth } from '../auth/AuthContext';
import { loadTenants, type TenantOption } from '../lib/tenants';
import useDashboardStore from '../state/useDashboardStore';

import styles from './TenantSwitcher.module.css';

type LoadState = 'idle' | 'loading' | 'loaded' | 'error';

type HighlightIntent = 'start' | 'end' | 'increment' | 'decrement';

function resolveStatusLabel(tenant: TenantOption, isActive: boolean): string | undefined {
  if (isActive) {
    return 'Active tenant';
  }
  if (typeof tenant.status === 'string' && tenant.status.trim()) {
    const normalized = tenant.status.trim();
    if (normalized.toLowerCase() !== 'active') {
      return normalized.charAt(0).toUpperCase() + normalized.slice(1);
    }
  }
  return undefined;
}

function getAnnouncementForCount(count: number): string {
  if (count === 0) {
    return 'No tenants available.';
  }
  if (count === 1) {
    return 'Loaded one tenant.';
  }
  return `Loaded ${count} tenants.`;
}

const TenantSwitcher = (): JSX.Element => {
  const { tenantId: authTenantId, setActiveTenant: setAuthTenant } = useAuth();
  const { activeTenantId, activeTenantLabel, loadAll } = useDashboardStore((state) => ({
    activeTenantId: state.activeTenantId,
    activeTenantLabel: state.activeTenantLabel,
    loadAll: state.loadAll,
  }));

  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [status, setStatus] = useState<LoadState>('idle');
  const [error, setError] = useState<string>();
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState<number>(-1);
  const [announcement, setAnnouncement] = useState('');

  const listRef = useRef<HTMLUListElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const listboxId = useId();

  const selectedTenantId = useMemo(
    () => activeTenantId ?? authTenantId ?? undefined,
    [activeTenantId, authTenantId],
  );

  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === selectedTenantId),
    [tenants, selectedTenantId],
  );

  const buttonLabel = useMemo(() => {
    if (status === 'loading') {
      return 'Loading tenants…';
    }
    if (selectedTenant) {
      return selectedTenant.name;
    }
    if (activeTenantLabel) {
      return activeTenantLabel;
    }
    if (selectedTenantId) {
      return `Tenant ${selectedTenantId}`;
    }
    return 'Select a tenant';
  }, [status, selectedTenant, activeTenantLabel, selectedTenantId]);

  const hintText = useMemo(() => {
    if (status === 'error' && error) {
      return error;
    }
    if (selectedTenant) {
      return 'Switch dashboards';
    }
    if (status === 'loading') {
      return 'Fetching tenants';
    }
    return 'Choose a tenant';
  }, [error, selectedTenant, status]);

  useEffect(() => {
    setStatus('loading');
    setError(undefined);
    setAnnouncement('Loading tenants…');
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    loadTenants(controller.signal)
      .then((records) => {
        setTenants(records);
        setStatus('loaded');
        setAnnouncement(getAnnouncementForCount(records.length));
      })
      .catch((reason) => {
        if (controller.signal.aborted) {
          return;
        }
        console.error('Failed to load tenants', reason);
        const message =
          reason instanceof Error ? reason.message : 'Unable to load tenants. Please try again.';
        setError(message);
        setStatus('error');
        setAnnouncement(`Unable to load tenants. ${message}`);
      });

    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const focusList = () => {
      if (listRef.current) {
        listRef.current.focus();
      }
    };

    const id = window.requestAnimationFrame(focusList);
    return () => window.cancelAnimationFrame(id);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      if (listRef.current?.contains(target) || buttonRef.current?.contains(target)) {
        return;
      }
      setIsOpen(false);
      setHighlightedIndex(-1);
    };

    window.addEventListener('mousedown', handlePointerDown);
    window.addEventListener('touchstart', handlePointerDown);
    return () => {
      window.removeEventListener('mousedown', handlePointerDown);
      window.removeEventListener('touchstart', handlePointerDown);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!selectedTenantId || activeTenantLabel || status !== 'loaded') {
      return;
    }
    const match = tenants.find((tenant) => tenant.id === selectedTenantId);
    if (match) {
      setAuthTenant(match.id, match.name);
    }
  }, [activeTenantLabel, selectedTenantId, setAuthTenant, status, tenants]);

  const closeMenu = useCallback((focusButton: boolean) => {
    setIsOpen(false);
    setHighlightedIndex(-1);
    if (focusButton) {
      buttonRef.current?.focus();
    }
  }, []);

  const highlightOption = useCallback(
    (intent: HighlightIntent) => {
      setHighlightedIndex((current) => {
        if (!tenants.length) {
          return -1;
        }
        if (intent === 'start') {
          const selectedIndex = tenants.findIndex((tenant) => tenant.id === selectedTenantId);
          return selectedIndex >= 0 ? selectedIndex : 0;
        }
        if (intent === 'end') {
          return tenants.length - 1;
        }
        if (current === -1) {
          const selectedIndex = tenants.findIndex((tenant) => tenant.id === selectedTenantId);
          return selectedIndex >= 0 ? selectedIndex : 0;
        }
        if (intent === 'increment') {
          return (current + 1) % tenants.length;
        }
        if (intent === 'decrement') {
          return (current - 1 + tenants.length) % tenants.length;
        }
        return current;
      });
    },
    [selectedTenantId, tenants],
  );

  const selectTenant = useCallback(
    (tenant: TenantOption | undefined) => {
      if (!tenant) {
        return;
      }
      closeMenu(true);
      if (tenant.id === selectedTenantId) {
        setAnnouncement(`${tenant.name} is already selected.`);
        return;
      }
      setAuthTenant(tenant.id, tenant.name);
      setAnnouncement(`Switched to ${tenant.name}.`);
      void loadAll(tenant.id, { force: true });
    },
    [closeMenu, loadAll, selectedTenantId, setAuthTenant],
  );

  const handleButtonClick = useCallback(() => {
    if (status === 'loading') {
      return;
    }
    setIsOpen((prev) => {
      const nextOpen = !prev;
      if (nextOpen) {
        highlightOption('start');
      }
      return nextOpen;
    });
  }, [highlightOption, status]);

  const handleButtonKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          highlightOption(event.key === 'ArrowUp' ? 'end' : 'start');
        }
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleButtonClick();
      }
    },
    [handleButtonClick, highlightOption, isOpen],
  );

  const handleListKeyDown = useCallback(
    (event: KeyboardEvent<HTMLUListElement>) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        highlightOption('increment');
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        highlightOption('decrement');
      } else if (event.key === 'Home') {
        event.preventDefault();
        highlightOption('start');
      } else if (event.key === 'End') {
        event.preventDefault();
        highlightOption('end');
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closeMenu(true);
      } else if (event.key === 'Tab') {
        closeMenu(false);
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        const tenant = tenants[highlightedIndex];
        selectTenant(tenant);
      }
    },
    [closeMenu, highlightOption, highlightedIndex, selectTenant, tenants],
  );

  const handleListBlur = useCallback(
    (event: FocusEvent<HTMLUListElement>) => {
      const next = event.relatedTarget as HTMLElement | null;
      if (next && (listRef.current?.contains(next) || buttonRef.current?.contains(next))) {
        return;
      }
      closeMenu(false);
    },
    [closeMenu],
  );

  const activeDescendant = useMemo(() => {
    if (highlightedIndex < 0 || !tenants[highlightedIndex]) {
      return undefined;
    }
    return `${listboxId}-option-${tenants[highlightedIndex].id}`;
  }, [highlightedIndex, listboxId, tenants]);

  return (
    <div className={styles.container}>
      <span className={`muted ${styles.label}`} id={`${listboxId}-label`}>
        Tenant
      </span>
      <button
        type="button"
        ref={buttonRef}
        className={styles.trigger}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listboxId : undefined}
        aria-describedby={`${listboxId}-hint`}
        onClick={handleButtonClick}
        onKeyDown={handleButtonKeyDown}
        disabled={status === 'loading'}
      >
        <span className={styles.triggerText}>
          <span className={styles.triggerTenant}>{buttonLabel}</span>
          <span id={`${listboxId}-hint`} className={styles.triggerHint}>
            {hintText}
          </span>
        </span>
        <span className={styles.caret} aria-hidden="true">
          ▾
        </span>
      </button>
      {isOpen ? (
        <div className={styles.panel} role="presentation">
          {tenants.length > 0 ? (
            <ul
              ref={listRef}
              id={listboxId}
              role="listbox"
              tabIndex={-1}
              aria-labelledby={`${listboxId}-label`}
              aria-activedescendant={activeDescendant}
              className={styles.listbox}
              onKeyDown={handleListKeyDown}
              onBlur={handleListBlur}
            >
              {tenants.map((tenant, index) => {
                const optionId = `${listboxId}-option-${tenant.id}`;
                const isSelected = tenant.id === selectedTenantId;
                const isHighlighted = index === highlightedIndex;
                const statusLabel = resolveStatusLabel(tenant, isSelected);
                return (
                  <li
                    key={tenant.id}
                    id={optionId}
                    role="option"
                    aria-selected={isSelected}
                    data-active={isHighlighted ? 'true' : undefined}
                    className={styles.option}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectTenant(tenant)}
                  >
                    <span className={styles.optionName}>{tenant.name}</span>
                    {statusLabel ? (
                      <span className={styles.optionStatus}>{statusLabel}</span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className={styles.empty} role="status">
              No tenants available.
            </div>
          )}
        </div>
      ) : null}
      {status === 'error' && error ? (
        <p className={`${styles.helper} ${styles.helperError}`} role="alert">
          {error}
        </p>
      ) : null}
      <div className={styles.visuallyHidden} aria-live="polite" role="status">
        {announcement}
      </div>
    </div>
  );
};

export default TenantSwitcher;
