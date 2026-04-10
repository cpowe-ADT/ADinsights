import { create } from 'zustand';

export type ToastTone = 'info' | 'success' | 'error';

export interface ToastOptions {
  tone?: ToastTone;
  duration?: number;
}

export interface ToastRecord {
  id: number;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  toasts: ToastRecord[];
  addToast: (message: string, options?: ToastOptions) => void;
  removeToast: (id: number) => void;
}

let nextId = 0;
const timers = new Map<number, ReturnType<typeof setTimeout>>();

const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (message, options) => {
    nextId += 1;
    const id = nextId;
    const tone: ToastTone = options?.tone ?? 'info';
    const duration = options?.duration ?? 4000;

    set((state) => ({ toasts: [...state.toasts, { id, message, tone }] }));

    if (duration > 0) {
      const timeoutId = setTimeout(() => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
        timers.delete(id);
      }, duration);
      timers.set(id, timeoutId);
    }
  },

  removeToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    const timeoutId = timers.get(id);
    if (timeoutId) {
      clearTimeout(timeoutId);
      timers.delete(id);
    }
  },
}));

export default useToastStore;
