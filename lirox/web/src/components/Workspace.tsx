import React, { useEffect, useRef } from 'react';
import { Terminal as TerminalIcon, Code2, X, FileCode2 } from 'lucide-react';
import { useChatStore } from '../stores/chatStore';

export function Workspace() {
  const { activeFile, terminalOutput, setActiveFile, clearTerminal } = useChatStore();
  const terminalRef = useRef<HTMLDivElement>(null);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalOutput]);

  const hasTerminal = terminalOutput.length > 0;
  const hasFile = activeFile !== null;

  return (
    <div className="w-full h-full flex flex-col bg-[#161616] border-l border-lirox-border">
      {/* Editor Panel */}
      {hasFile && (
        <div className={`flex flex-col ${hasTerminal ? 'h-2/3 border-b border-lirox-border' : 'h-full'}`}>
          {/* File Header Tabs */}
          <div className="flex items-center h-10 bg-[#1A1A1A] border-b border-lirox-border overflow-x-auto no-scrollbar">
            <div className="flex items-center gap-2 px-4 h-full bg-[#161616] border-t-2 border-t-lirox-lion border-r border-r-lirox-border min-w-fit">
              <FileCode2 className="w-4 h-4 text-lirox-lion" />
              <span className="text-sm text-lirox-text-primary font-mono">{activeFile.name}</span>
              <button 
                onClick={() => setActiveFile(null)}
                className="ml-2 p-0.5 rounded hover:bg-lirox-bg-hover text-lirox-text-secondary transition"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          
          {/* Editor Content (Mock) */}
          <div className="flex-1 overflow-auto bg-[#161616] p-4 text-sm font-mono text-[#CCCCCC] leading-relaxed">
            <pre className="!bg-transparent !p-0 !border-none !m-0">
              <code>{activeFile.content}</code>
            </pre>
          </div>
        </div>
      )}

      {/* Terminal Panel */}
      {hasTerminal && (
        <div className={`flex flex-col bg-[#0F0F0F] ${hasFile ? 'h-1/3' : 'h-full'}`}>
          <div className="flex items-center justify-between h-9 px-3 border-b border-lirox-border/50 bg-[#1A1A1A]">
            <div className="flex items-center gap-2">
              <TerminalIcon className="w-4 h-4 text-lirox-text-secondary" />
              <span className="text-xs uppercase tracking-wider text-lirox-text-secondary font-semibold">Terminal</span>
            </div>
            <button 
              onClick={clearTerminal}
              className="p-1 rounded hover:bg-lirox-bg-hover text-lirox-text-secondary transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div 
            ref={terminalRef}
            className="flex-1 overflow-auto p-3 font-mono text-[13px] text-lirox-text-secondary leading-relaxed"
          >
            {terminalOutput.map((line, i) => (
              <div key={i} className={line.includes('error') ? 'text-lirox-error' : line.includes('success') ? 'text-lirox-success' : 'text-[#EBEBEB]'}>
                {line}
              </div>
            ))}
            <div className="mt-2 flex items-center text-[#EBEBEB] opacity-70">
              <span className="text-lirox-success mr-2">➜</span>
              <span className="text-lirox-lion mr-2">~/lirox</span>
              <span className="animate-pulse">_</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
