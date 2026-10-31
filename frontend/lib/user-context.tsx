"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { ApiError, get, post } from "@/lib/api";
import type {
  Notification,
  NotificationList,
  ProcessStats,
  SyncStats,
  User,
} from "@/lib/types";

type UserContextValue = {
  user: User | null;
  activeId: string | null;
  authChecked: boolean;
  connectGmail: () => Promise<void>;
  logout: () => Promise<void>;
  syncInbox: () => Promise<SyncStats>;
  processAll: () => Promise<ProcessStats>;
  notifications: Notification[];
  unreadCount: number;
  loadNotifications: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  busy: boolean;
  error: string | null;
};

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const activeId = user?.id ?? null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await get<User>("/auth/me");
        if (!cancelled) setUser(me);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          setUser(null);
        } else {
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (!cancelled) setAuthChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const connectGmail = useCallback(async () => {
    const { authorization_url } = await get<{ authorization_url: string }>(
      "/auth/google",
    );
    window.location.assign(authorization_url);
  }, []);

  const logout = useCallback(async () => {
    await post("/auth/logout");
    setUser(null);
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await get<NotificationList>(`/notifications/${activeId}`);
        if (cancelled) return;
        setNotifications(data.notifications);
        setUnreadCount(data.unread_count);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  const loadNotifications = useCallback(async () => {
    if (!activeId) return;
    const data = await get<NotificationList>(`/notifications/${activeId}`);
    setNotifications(data.notifications);
    setUnreadCount(data.unread_count);
  }, [activeId]);

  const markRead = useCallback(
    async (id: string) => {
      await post(`/notifications/${id}/read`);
      await loadNotifications();
    },
    [loadNotifications],
  );

  const syncInbox = useCallback(async () => {
    if (!activeId) throw new Error("Not signed in");
    setBusy(true);
    setError(null);
    try {
      return await post<SyncStats>(`/emails/sync/${activeId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [activeId]);

  const processAll = useCallback(async () => {
    if (!activeId) throw new Error("Not signed in");
    setBusy(true);
    setError(null);
    try {
      return await post<ProcessStats>(`/emails/process-all/${activeId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [activeId]);

  return (
    <UserContext.Provider
      value={{
        user,
        activeId,
        authChecked,
        connectGmail,
        logout,
        syncInbox,
        processAll,
        notifications,
        unreadCount,
        loadNotifications,
        markRead,
        busy,
        error,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
