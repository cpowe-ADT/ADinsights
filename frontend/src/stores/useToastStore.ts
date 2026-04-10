import { create } from 'zustand';

export type ToastTone = 'info' | 'success' | 'error';

interface ToastRecord {
  id: number;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  toasts: ToastRecord[];
  nextId: number;
  pushToast: (message: string, options?: { tone?: ToastTone; duration?: number }) => void;
  removeToast: (id: number) => void;
}

const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  nextId: 1,

  pushToast: (message, options) => {
    const id = get().nextId;
    const tone: ToastTone = options?.tone ?? 'info';
    const duration = options?.duration ?? 4000;

    set((state) => ({
      toasts: [...state.toasts, { id, message, tone }],
      nextId: state.nextId + 1,
    }));

    if (duration > 0) {
      setTimeout(() => {
        get().removeToast(id);
      }, duration);
    }
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },
}));

export default useToastStore;
