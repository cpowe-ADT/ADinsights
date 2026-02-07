import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type VirtualRowsOptions = {
  enabled: boolean;
  rowCount: number;
  rowHeight: number;
  overscan?: number;
};

type VirtualRowsResult = {
  containerRef: React.RefObject<HTMLDivElement>;
  startIndex: number;
  endIndex: number;
  paddingTop: number;
  paddingBottom: number;
  isVirtualized: boolean;
};

const useVirtualRows = ({
  enabled,
  rowCount,
  rowHeight,
  overscan = 6,
}: VirtualRowsOptions): VirtualRowsResult => {
  const containerRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  const [scrollState, setScrollState] = useState({ scrollTop: 0, viewportHeight: 0 });

  const updateState = useCallback(() => {
    const node = containerRef.current;
    if (!node) {
      return;
    }
    setScrollState({ scrollTop: node.scrollTop, viewportHeight: node.clientHeight });
  }, []);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    const node = containerRef.current;
    if (!node) {
      return undefined;
    }

    const handleScroll = () => {
      if (frameRef.current !== null) {
        return;
      }
      frameRef.current = window.requestAnimationFrame(() => {
        frameRef.current = null;
        updateState();
      });
    };

    updateState();
    node.addEventListener('scroll', handleScroll, { passive: true });

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(handleScroll);
      resizeObserver.observe(node);
    }

    return () => {
      node.removeEventListener('scroll', handleScroll);
      resizeObserver?.disconnect();
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [enabled, updateState]);

  const virtualState = useMemo(() => {
    if (!enabled || scrollState.viewportHeight === 0) {
      return { startIndex: 0, endIndex: rowCount, paddingTop: 0, paddingBottom: 0 };
    }

    const visibleCount = Math.ceil(scrollState.viewportHeight / rowHeight);
    const start = Math.max(0, Math.floor(scrollState.scrollTop / rowHeight) - overscan);
    const end = Math.min(rowCount, start + visibleCount + overscan * 2);

    return {
      startIndex: start,
      endIndex: end,
      paddingTop: start * rowHeight,
      paddingBottom: Math.max(0, (rowCount - end) * rowHeight),
    };
  }, [enabled, overscan, rowCount, rowHeight, scrollState]);

  return {
    containerRef,
    isVirtualized: enabled && rowCount > 0,
    ...virtualState,
  };
};

export default useVirtualRows;
