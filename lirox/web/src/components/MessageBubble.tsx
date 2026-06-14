import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles, User } from 'lucide-react';
import type { ChatMessage } from '../types';
import { ThinkingIndicator } from './ThinkingIndicator';

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  
  // Exclude 'done' and 'error' events from events to show in thinking
  const processEvents = message.events?.filter(ev => !['done', 'error', 'connected'].includes(ev.type)) || [];

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in my-6">
        <div className="max-w-[75%] px-5 py-3.5 rounded-2xl bg-lirox-bg-card text-lirox-text-primary text-[15px] leading-relaxed break-words">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message (Claude style)
  return (
    <div className="flex justify-start animate-fade-in my-6 w-full">
      <div className="flex gap-4 w-full">
        {/* Avatar */}
        <div className="w-8 h-8 rounded shrink-0 bg-lirox-gold/20 flex items-center justify-center mt-1 border border-lirox-gold/10">
          <Sparkles className="w-4 h-4 text-lirox-gold" />
        </div>

        <div className="flex-1 min-w-0 flex flex-col gap-3">
          <div className="font-medium text-[14px] text-lirox-text-primary mt-1.5 flex items-center gap-2">
            Lirox
            <span className="text-[10px] text-lirox-text-secondary font-mono opacity-50 font-normal">
              {new Date(message.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          {/* Thinking Indicator for Assistant Messages */}
          {processEvents.length > 0 && (
            <div className="-ml-1">
              <ThinkingIndicator events={processEvents} isFinished={true} />
            </div>
          )}
          
          <div className="markdown-content text-[15.5px] leading-relaxed w-full break-words">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
