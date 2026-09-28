"use client";

/**
 * The dashboard bell's data: an examiner/admin's own notifications, loaded on mount and
 * pushed live over a per-user websocket - same reconnect-on-drop shape as
 * `useLiveView.ts`'s signaling socket, just one shared channel instead of one per
 * candidate tile.
 */

import { useEffect, useRef, useState } from "react";

import { api, API_BASE, tokens } from "@/lib/api";

const WS_SUBPROTOCOL = "exam-notifications.v1";

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  session_id: string | null;
  result_id: string | null;
  is_read: boolean;
  created_at: string;
}

type PushMessage = {
  type: "notification";
  notification: AppNotification;
};

export function useNotifications(enabled: boolean) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const retries = useRef(0);
  const stoppedRef = useRef(false);

  async function load() {
    try {
      const data = await api.get<AppNotification[]>("/notifications");
      setItems(data);
    } catch {
      /* the socket (or the next mount) will catch it up */
    }
  }

  function scheduleReconnect() {
    if (stoppedRef.current) return;
    const delay = Math.min(20_000, 1_500 * 2 ** retries.current);
    retries.current += 1;
    reconnectTimer.current = window.setTimeout(connect, delay);
  }

  function connect() {
    if (stoppedRef.current) return;
    const access = tokens.access();
    if (!access) return;

    const url = `${API_BASE.replace(/^http/, "ws")}/notifications/ws`;
    let socket: WebSocket;
    try {
      socket = new WebSocket(url, [WS_SUBPROTOCOL, access]);
    } catch {
      scheduleReconnect();
      return;
    }
    socketRef.current = socket;

    socket.onopen = () => {
      retries.current = 0;
    };
    socket.onmessage = (event) => {
      let message: PushMessage;
      try {
        message = JSON.parse(event.data as string);
      } catch {
        return;
      }
      if (message.type === "notification") {
        setItems((current) => {
          if (current.some((n) => n.id === message.notification.id)) return current;
          return [message.notification, ...current];
        });
      }
    };
    socket.onclose = () => {
      socketRef.current = null;
      if (stoppedRef.current) return;
      scheduleReconnect();
    };
    socket.onerror = () => {
      // onclose always follows; the reconnect is scheduled there.
    };
  }

  useEffect(() => {
    if (!enabled) return;
    stoppedRef.current = false;
    void load();
    connect();

    return () => {
      stoppedRef.current = true;
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
      socketRef.current?.close(1000, "Left dashboard");
      socketRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  async function markRead(id: string) {
    setItems((current) => current.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    try {
      await api.post(`/notifications/${id}/read`);
    } catch {
      /* a failed mark-read is not worth surfacing - it will show unread again on reload */
    }
  }

  const unreadCount = items.filter((n) => !n.is_read).length;
  return { items, unreadCount, markRead };
}
