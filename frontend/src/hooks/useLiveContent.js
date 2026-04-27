import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

/**
 * Subscribes to /api/ws and invokes onPublished({scope, ...}) whenever the
 * server broadcasts a content_published event. Auto-reconnects with backoff.
 */
export default function useLiveContent(onPublished) {
  const { API } = useAuth();
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const cbRef = useRef(onPublished);
  cbRef.current = onPublished;

  const buildWsUrl = useCallback(() => {
    // API is e.g. https://portal.example.com  → wss://portal.example.com/api/ws
    const u = new URL(API);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    u.pathname = "/api/ws";
    return u.toString();
  }, [API]);

  useEffect(() => {
    let stopped = false;
    let backoff = 1000;
    let retryTimer = null;

    const open = () => {
      if (stopped) return;
      try {
        const ws = new WebSocket(buildWsUrl());
        wsRef.current = ws;
        ws.onopen = () => { setConnected(true); backoff = 1000; };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === "content_published" && cbRef.current) cbRef.current(msg);
          } catch { /* ignore non-JSON */ }
        };
        ws.onclose = () => {
          setConnected(false);
          if (stopped) return;
          retryTimer = setTimeout(open, backoff);
          backoff = Math.min(backoff * 2, 15000);
        };
        ws.onerror = () => { try { ws.close(); } catch { /* */ } };
      } catch {
        retryTimer = setTimeout(open, backoff);
        backoff = Math.min(backoff * 2, 15000);
      }
    };

    open();
    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      try { wsRef.current?.close(); } catch { /* */ }
    };
  }, [buildWsUrl]);

  return connected;
}
