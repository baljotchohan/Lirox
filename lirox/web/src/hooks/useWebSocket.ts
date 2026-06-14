// [WEB-5] WebSocket hook with auto-reconnect and event parsing
import { useEffect, useRef, useCallback, useState } from 'react';
import type { OrchestratorEvent, ConnectionStatus } from '../types';

const WS_URL = `ws://${window.location.hostname}:${window.location.port === '5173' ? '3210' : window.location.port}/ws/chat`;
const MAX_RECONNECT_DELAY = 30000;

export function useWebSocket(onEvent: (event: OrchestratorEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const [status, setStatus] = useState<ConnectionStatus>('connecting');

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttempt.current = 0;
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as OrchestratorEvent;
        if (data.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
          return;
        }
        onEvent(data);
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      const delay = Math.min(1000 * 2 ** reconnectAttempt.current, MAX_RECONNECT_DELAY);
      reconnectAttempt.current++;
      setStatus('reconnecting');
      reconnectTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [onEvent]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((msg: { type: string; text: string }) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { send, status };
}
