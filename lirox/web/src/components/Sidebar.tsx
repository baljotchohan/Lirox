import React from 'react';
import { History, Settings, User, PanelLeftClose, PanelLeft, Plus, Folder } from 'lucide-react';
import { useChatStore } from '../stores/chatStore';

export function Sidebar() {
  const { isSidebarOpen, toggleSidebar, profile } = useChatStore();

  if (!isSidebarOpen) {
    return (
      <button 
        onClick={toggleSidebar}
        className="absolute top-4 left-4 z-50 p-2 rounded-md bg-transparent hover:bg-lirox-bg-hover text-lirox-text-secondary transition-colors border border-transparent hover:border-lirox-border"
      >
        <PanelLeft className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="w-64 h-full bg-[#111111] border-r border-lirox-border flex flex-col transition-all duration-300">
      {/* Top Header */}
      <div className="flex items-center justify-between p-4 h-14 border-b border-lirox-border/50">
        <h1 className="text-lirox-text-primary font-medium tracking-wide flex items-center gap-2">
          <span className="text-lirox-lion font-serif font-bold text-lg">L</span>
          Lirox
        </h1>
        <button 
          onClick={toggleSidebar}
          className="p-1.5 rounded-md hover:bg-lirox-bg-hover text-lirox-text-secondary transition-colors"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button className="w-full flex items-center justify-center gap-2 bg-transparent border border-lirox-border hover:border-lirox-lion/50 text-lirox-text-primary rounded-md py-2 px-4 transition-all group">
          <Plus className="w-4 h-4 text-lirox-lion group-hover:scale-110 transition-transform" />
          <span className="text-sm">New Session</span>
        </button>
      </div>

      {/* Sessions History List */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <div className="text-xs font-semibold text-lirox-text-secondary uppercase tracking-widest mb-3 pl-2">
          Recent Sessions
        </div>
        <div className="space-y-1">
          {[
            'Implement Python Scraper',
            'React Split Pane UI',
            'Fix Tailwind Config',
            'Debug API Route'
          ].map((session, i) => (
            <button key={i} className="w-full text-left flex items-center gap-2 px-2 py-2 rounded-md hover:bg-lirox-bg-hover text-sm text-lirox-text-secondary hover:text-lirox-text-primary transition-colors truncate">
              <History className="w-3.5 h-3.5 shrink-0 opacity-50" />
              <span className="truncate">{session}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Workspace / Folders */}
      <div className="border-t border-lirox-border/50 p-3">
        <div className="w-full text-left flex items-center gap-2 px-2 py-2 rounded-md hover:bg-lirox-bg-hover text-sm text-lirox-text-secondary hover:text-lirox-text-primary transition-colors cursor-pointer">
          <Folder className="w-4 h-4 shrink-0 text-lirox-lion/70" />
          <span className="truncate">Open Folder</span>
        </div>
      </div>

      {/* Bottom Profile & Settings */}
      <div className="p-3 border-t border-lirox-border/50 space-y-1 bg-[#0a0a0a]">
        <button className="w-full flex items-center gap-3 px-2 py-2 rounded-md hover:bg-lirox-bg-hover text-sm text-lirox-text-secondary hover:text-lirox-text-primary transition-colors">
          <Settings className="w-4 h-4" />
          <span>Settings</span>
        </button>
        <button className="w-full flex items-center gap-3 px-2 py-2 rounded-md hover:bg-lirox-bg-hover text-sm text-lirox-text-secondary hover:text-lirox-text-primary transition-colors">
          <User className="w-4 h-4" />
          <span className="truncate">{profile?.user_name || 'Operator'}</span>
        </button>
      </div>
    </div>
  );
}
