import React, { useState, useMemo } from 'react';
import type { CommandInfo } from '../types';

const COMMANDS: CommandInfo[] = [
  { command: '/help', description: 'Show all commands' },
  { command: '/code', description: 'Enter persistent coding mode' },
  { command: '/setup', description: 'Run setup wizard' },
  { command: '/history', description: 'View past conversations' },
  { command: '/session', description: 'Current session details' },
  { command: '/models', description: 'List available AI providers' },
  { command: '/use-model', description: 'Switch default AI provider' },
  { command: '/memory', description: 'Show learning statistics' },
  { command: '/profile', description: 'View user profile' },
  { command: '/reset', description: 'Clear current session' },
  { command: '/recall', description: 'Show learned facts about you' },
  { command: '/workspace', description: 'Set active directory' },
  { command: '/expand thinking', description: 'View last reasoning trace' },
  { command: '/export-memory', description: 'Save learnings to JSON' },
  { command: '/import-memory', description: 'Import external learnings' },
  { command: '/rag add', description: 'Add folder to RAG knowledge base' },
  { command: '/rag status', description: 'Show RAG store statistics' },
  { command: '/rag reindex', description: 'Rebuild RAG index' },
  { command: '/rag query', description: 'Test-query the RAG knowledge base' },
  { command: '/version', description: 'Show version' },
];

interface Props {
  filter: string;
  onSelect: (cmd: string) => void;
  selectedIndex: number;
}

export function CommandPalette({ filter, onSelect, selectedIndex }: Props) {
  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return COMMANDS.filter(c => c.command.includes(q) || c.description.toLowerCase().includes(q));
  }, [filter]);

  if (!filtered.length) return null;

  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 glass border border-lirox-border rounded-xl overflow-hidden shadow-2xl z-50 max-h-[320px] overflow-y-auto">
      {filtered.map((cmd, i) => (
        <button
          key={cmd.command}
          onClick={() => onSelect(cmd.command)}
          className={`w-full flex items-center justify-between px-4 py-2.5 text-left transition-colors ${
            i === selectedIndex
              ? 'bg-lirox-gold/10 text-lirox-gold'
              : 'text-lirox-text-primary hover:bg-lirox-bg-hover'
          }`}
        >
          <span className="font-mono text-sm">{cmd.command}</span>
          <span className="text-xs text-lirox-text-secondary ml-4">{cmd.description}</span>
        </button>
      ))}
    </div>
  );
}
