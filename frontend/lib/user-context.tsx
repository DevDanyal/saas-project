"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { get, post } from "@/lib/api";
import type {
  Notification,
  NotificationList,
  ProcessStats,
  SyncStats,
  User,
} from "@/lib/types";

type UserContextValue = {
  users: User[];
  activeId: string | null;
  setActiveId: (id: string) => void;
  connectGmail: () => Promise<void>;
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

const STORAGE_KEY = "smart-inbox-active-user";

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers] = useState<User[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { users: list } = await get<{ users: User[] }>("/users");
        if (cancelled) return;
        setUsers(list);
        const stored = window.localStorage.getItem(STORAGE_KEY);
        const valid = stored && list.some((u) => u.id === stored) ? stored : null;
        setActiveIdState(valid ?? (list[0]?.id ?? null));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setActiveId = useCallback((id: string) => {
    setActiveIdState(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const connectGmail = useCallback(async () => {
    const { authorization_url } = await get<{ authorization_url: string }>(
      "/auth/google",
    );
    window.location.href = authorization_url;
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
    if (!activeId) throw new Error("No user selected");
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
    if (!activeId) throw new Error("No user selected");
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
        users,
        activeId,
        setActiveId,
        connectGmail,
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