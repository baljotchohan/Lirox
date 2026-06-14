import React, { useRef, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Workspace } from './components/Workspace';
import { ChatInput } from './components/ChatInput';
import { MessageBubble } from './components/MessageBubble';
import { ThinkingIndicator } from './components/ThinkingIndicator';
import { WelcomeScreen } from './components/WelcomeScreen';
import { useChatStore } from './stores/chatStore';
import { useWebSocket } from './hooks/useWebSocket';
import { PanelLeft } from 'lucide-react';
import type { OrchestratorEvent, ChatMessage } from './types';

export default function App() {
  const { messages, pendingEvents, isProcessing, activeFile, terminalOutput, isSidebarOpen, toggleSidebar } = useChatStore();
  const addUserMessage = useChatStore((s: { addUserMessage: (c: string) => string }) => s.addUserMessage);
  const handleEvent = useChatStore((s: { handleEvent: (e: OrchestratorEvent) => void }) => s.handleEvent);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Memoize event handler to prevent reconnects
  const onEvent = useCallback((event: OrchestratorEvent) => {
    handleEvent(event);
  }, [handleEvent]);

  const { send, status } = useWebSocket(onEvent);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pendingEvents]);

  const handleSend = useCallback((text: string, isCommand: boolean) => {
    if (isCommand) {
      // Add user message for command visibility
      addUserMessage(text);
      send({ type: 'command', text });
    } else {
      addUserMessage(text);
      send({ type: 'query', text });
    }
  }, [addUserMessage, send]);

  const handleSuggestion = useCallback((text: string) => {
    addUserMessage(text);
    send({ type: 'query', text });
  }, [addUserMessage, send]);

  const hasWorkspace = activeFile !== null || terminalOutput.length > 0;

  return (
    <div className="h-screen w-full flex bg-lirox-bg relative overflow-hidden text-lirox-text-primary selection:bg-lirox-lion/20 selection:text-lirox-lion">
      
      {/* Sidebar */}
      <Sidebar />

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden relative">
        
        {/* Toggle Sidebar Button (if closed) */}
        {!isSidebarOpen && (
          <button 
            onClick={toggleSidebar}
            className="absolute top-4 left-4 z-50 p-1.5 rounded-md bg-[#1A1A1A] border border-[#2A2A2A] hover:bg-lirox-bg-hover text-lirox-text-secondary transition-colors shadow-sm"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        )}

        {/* Chat Area */}
        <div className={`flex flex-col h-full bg-[#0F0F0F] transition-all duration-300 ${hasWorkspace ? 'w-1/2 min-w-[400px]' : 'w-full'}`}>
          {/* Header/Status Indicator (minimal) */}
          <div className="h-10 flex items-center justify-end px-4 border-b border-lirox-border bg-[#0F0F0F]">
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${status === 'connected' ? 'bg-lirox-success' : status === 'connecting' ? 'bg-lirox-warning animate-pulse' : 'bg-lirox-error'}`} />
              <span className="text-[10px] text-lirox-text-secondary uppercase tracking-widest font-mono">
                {status}
              </span>
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto relative z-10 scroll-smooth">
            {messages.length === 0 ? (
              <WelcomeScreen onSuggestion={handleSuggestion} />
            ) : (
              <div className="w-full max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-2">
                {messages.map((msg: ChatMessage) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))}
                {isProcessing && pendingEvents.length > 0 && (
                  <ThinkingIndicator events={pendingEvents} />
                )}
                {isProcessing && pendingEvents.length === 0 && (
                  <div className="flex justify-start animate-fade-in my-4">
                    <div className="flex items-center gap-2 px-2 py-3">
                      <span className="typing-dot"></span>
                      <span className="typing-dot"></span>
                      <span className="typing-dot"></span>
                    </div>
                  </div>
                )}
                <div className="h-6" /> {/* Bottom padding */}
              </div>
            )}
          </div>

          {/* Input */}
          <div className="relative z-10 bg-[#0F0F0F]">
            <div className="w-full max-w-4xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
              <ChatInput onSend={handleSend} disabled={status !== 'connected'} />
            </div>
          </div>
        </div>

        {/* Right Pane: Workspace */}
        {hasWorkspace && (
          <div className="flex-1 min-w-[300px] border-l border-lirox-border">
            <Workspace />
          </div>
        )}
      </div>
    </div>
  );
}
