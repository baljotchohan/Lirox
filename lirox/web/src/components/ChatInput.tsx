import React, { useState, useRef, useCallback, KeyboardEvent } from 'react';
import { ArrowUp, Paperclip, Plus } from 'lucide-react';
import { CommandPalette } from './CommandPalette';

interface Props {
  onSend: (text: string, isCommand: boolean) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [input, setInput] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const [cmdIndex, setCmdIndex] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    const isCommand = text.startsWith('/');
    onSend(text, isCommand);
    setInput('');
    setShowCommands(false);
    setCmdIndex(0);
    inputRef.current?.focus();
    if (inputRef.current) inputRef.current.style.height = '24px';
  }, [input, onSend]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommands) {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setCmdIndex((i: number) => Math.max(0, i - 1));
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setCmdIndex((i: number) => i + 1);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault();
        return;
      }
      if (e.key === 'Escape') {
        setShowCommands(false);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (value: string) => {
    setInput(value);
    if (value.startsWith('/') && !value.includes(' ')) {
      setShowCommands(true);
      setCmdIndex(0);
    } else {
      setShowCommands(false);
    }
  };

  const handleCommandSelect = (cmd: string) => {
    setInput(cmd + ' ');
    setShowCommands(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative pb-4 pt-2 w-full">
      {showCommands && (
        <CommandPalette
          filter={input}
          onSelect={handleCommandSelect}
          selectedIndex={cmdIndex}
        />
      )}

      <div className="flex flex-col bg-[#1A1A1A] border border-lirox-border rounded-xl px-3 py-2.5 focus-within:border-[#444] transition-colors shadow-sm">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message Lirox..."
          disabled={disabled}
          rows={1}
          className="w-full bg-transparent border-none outline-none resize-none text-[#EBEBEB] placeholder-[#666] text-[14px] leading-relaxed max-h-32 min-h-[24px] px-1"
          onInput={(e: React.FormEvent<HTMLTextAreaElement>) => {
            const t = e.target as HTMLTextAreaElement;
            t.style.height = '24px';
            t.style.height = Math.min(t.scrollHeight, 128) + 'px';
          }}
        />

        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1">
            <button
              onClick={() => {}}
              className="p-1.5 rounded-md text-[#A0A0A0] hover:text-[#EBEBEB] hover:bg-[#2D2D2D] transition-all flex items-center gap-1.5"
              title="Attach File"
            >
              <Plus className="w-4 h-4" />
              <span className="text-xs font-medium pr-1">Attach</span>
            </button>

            <button
              onClick={() => { setInput('/'); setShowCommands(true); inputRef.current?.focus(); }}
              className="p-1.5 rounded-md text-[#A0A0A0] hover:text-[#EBEBEB] hover:bg-[#2D2D2D] transition-all"
              title="Commands"
            >
              <Paperclip className="w-4 h-4" />
            </button>
          </div>

          <button
            onClick={handleSubmit}
            disabled={disabled || !input.trim()}
            className={`p-1.5 rounded-md transition-all ${
              input.trim() && !disabled
                ? 'bg-lirox-lion text-[#111] hover:bg-lirox-lion-light'
                : 'bg-[#2D2D2D] text-[#888] cursor-not-allowed'
            }`}
          >
            <ArrowUp className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="text-center mt-3">
        <span className="text-[11px] text-[#666]">
          Type '/' for commands or press Enter to send
        </span>
      </div>
    </div>
  );
}
