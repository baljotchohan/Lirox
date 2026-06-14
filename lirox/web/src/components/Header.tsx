import React from 'react';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import type { ConnectionStatus } from '../types';

interface Props {
  status: ConnectionStatus;
  profile: { user_name?: string; agent_name?: string } | null;
}

export function Header({ status, profile }: Props) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-[#1A1A1A]">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-[15px] font-semibold text-[#EBEBEB]">
            {profile?.agent_name || 'Lirox'}
          </h1>
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#2D2D2D]">
          {status === 'connected' && (
            <>
              <Wifi className="w-3.5 h-3.5 text-[#10b981]" />
              <span className="text-[11px] text-[#A0A0A0]">Connected</span>
            </>
          )}
          {status === 'connecting' && (
            <>
              <Loader2 className="w-3.5 h-3.5 text-[#f59e0b] animate-spin" />
              <span className="text-[11px] text-[#A0A0A0]">Connecting</span>
            </>
          )}
          {(status === 'disconnected' || status === 'reconnecting') && (
            <>
              <WifiOff className="w-3.5 h-3.5 text-[#ef4444]" />
              <span className="text-[11px] text-[#A0A0A0]">
                {status === 'reconnecting' ? 'Reconnecting...' : 'Disconnected'}
              </span>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
