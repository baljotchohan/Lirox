import React, { useState } from 'react';
import { Loader2, ChevronDown, ChevronRight, Sparkles, Brain, Wrench, FileText, AlertTriangle } from 'lucide-react';
import type { OrchestratorEvent } from '../types';

interface Props {
  events: OrchestratorEvent[];
  isFinished?: boolean;
}

const PHASE_ICONS: Record<string, React.ReactNode> = {
  agent_progress: <Sparkles className="w-3.5 h-3.5 text-blue-400" />,
  tool_call: <Wrench className="w-3.5 h-3.5 text-lirox-gold" />,
  tool_result: <FileText className="w-3.5 h-3.5 text-green-400" />,
  thinking_phase: <Brain className="w-3.5 h-3.5 text-purple-400" />,
  warning: <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />,
};

export function ThinkingIndicator({ events, isFinished = false }: Props) {
  const [isOpen, setIsOpen] = useState(!isFinished);

  const processEvents = events.filter(ev => !['done', 'error', 'connected'].includes(ev.type));

  if (!processEvents.length) return null;

  return (
    <div className={`flex justify-start my-3 ${!isFinished ? 'animate-fade-in' : ''}`}>
      <div className="w-full max-w-[85%]">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-lirox-bg-card/40 hover:bg-lirox-bg-card border border-transparent hover:border-lirox-border transition-all group cursor-pointer"
        >
          {isOpen ? (
            <ChevronDown className="w-4 h-4 text-lirox-text-secondary group-hover:text-lirox-text-primary transition-colors" />
          ) : (
            <ChevronRight className="w-4 h-4 text-lirox-text-secondary group-hover:text-lirox-text-primary transition-colors" />
          )}
          
          {!isFinished ? (
            <Loader2 className="w-3.5 h-3.5 text-lirox-thinking animate-spin" />
          ) : (
            <Brain className="w-3.5 h-3.5 text-lirox-text-secondary group-hover:text-lirox-thinking transition-colors" />
          )}

          <span className="text-[13px] font-medium text-lirox-text-secondary group-hover:text-lirox-text-primary transition-colors">
            {isFinished ? 'Thought process' : 'Thinking...'}
          </span>
        </button>

        {isOpen && (
          <div className="mt-2 ml-4 pl-5 py-2 border-l-2 border-lirox-border/50 space-y-3">
            {processEvents.map((ev, i) => (
              <div
                key={i}
                className="flex items-start gap-3 text-[13px] text-lirox-text-secondary animate-slide-up"
                style={{ animationDelay: `${!isFinished ? Math.min(i * 50, 500) : 0}ms` }}
              >
                <div className="mt-[3px] shrink-0 bg-lirox-bg p-1.5 rounded-md border border-lirox-border shadow-sm">
                  {PHASE_ICONS[ev.type] || <span className="text-[10px]">●</span>}
                </div>
                <span className="leading-relaxed font-mono text-[12px] break-words pt-1">{ev.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
