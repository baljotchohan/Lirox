// Zustand store for chat messages and sessions
import { create } from 'zustand';
import type { ChatMessage, OrchestratorEvent, ProfileData } from '../types';

export interface FileData {
  name: string;
  language: string;
  content: string;
}

interface ChatState {
  messages: ChatMessage[];
  pendingEvents: OrchestratorEvent[];
  isProcessing: boolean;
  profile: ProfileData | null;
  setupRequired: boolean;

  // New UI states
  isSidebarOpen: boolean;
  activeFile: FileData | null;
  terminalOutput: string[];

  addUserMessage: (content: string) => string;
  handleEvent: (event: OrchestratorEvent) => void;
  setProfile: (profile: ProfileData) => void;
  setSetupRequired: (v: boolean) => void;
  clearMessages: () => void;
  
  // New Setters
  toggleSidebar: () => void;
  setActiveFile: (file: FileData | null) => void;
  addTerminalLine: (line: string) => void;
  clearTerminal: () => void;
}

let msgCounter = 0;
const genId = () => `msg-${Date.now()}-${++msgCounter}`;

export const useChatStore = create<ChatState>((set: (fn: ((s: ChatState) => Partial<ChatState>) | Partial<ChatState>) => void, get: () => ChatState) => ({
  messages: [],
  pendingEvents: [],
  isProcessing: false,
  profile: null,
  setupRequired: false,

  isSidebarOpen: true,
  activeFile: null,
  terminalOutput: [],

  toggleSidebar: () => set((s: ChatState) => ({ isSidebarOpen: !s.isSidebarOpen })),
  setActiveFile: (file: FileData | null) => set({ activeFile: file }),
  addTerminalLine: (line: string) => set((s: ChatState) => ({ terminalOutput: [...s.terminalOutput, line] })),
  clearTerminal: () => set({ terminalOutput: [] }),

  addUserMessage: (content: string) => {
    const id = genId();
    set((s: ChatState) => ({
      messages: [...s.messages, {
        id, role: 'user', content, timestamp: Date.now() / 1000, events: [],
      }],
      pendingEvents: [],
      isProcessing: true,
    }));
    return id;
  },

  handleEvent: (event: OrchestratorEvent) => {
    const { type } = event;

    if (type === 'connected') {
      if (event.data?.profile) set({ profile: event.data.profile });
      if (event.data?.setup_required) set({ setupRequired: true });
      return;
    }

    if (type === 'command_result') {
      // Show command results as system messages
      set((s: ChatState) => ({
        messages: [...s.messages, {
          id: genId(),
          role: 'assistant',
          content: event.message || JSON.stringify(event.data, null, 2),
          timestamp: event.timestamp,
          events: [event],
        }],
        isProcessing: false,
      }));
      return;
    }

    if (type === 'done') {
      set((s: ChatState) => ({
        messages: [...s.messages, {
          id: genId(),
          role: 'assistant',
          content: event.message || '',
          timestamp: event.timestamp,
          events: [...s.pendingEvents, event],
        }],
        pendingEvents: [],
        isProcessing: false,
      }));
      
      // Simulate file creation if the message mentions it (Demo feature)
      if (event.message?.includes('```') && event.message?.toLowerCase().includes('file')) {
        const match = event.message.match(/```(\w+)?\n([\s\S]*?)```/);
        if (match) {
          set({ 
            activeFile: {
              name: 'generated_file.' + (match[1] || 'txt'),
              language: match[1] || 'plaintext',
              content: match[2].trim()
            }
          });
        }
      }

      return;
    }

    if (type === 'error') {
      set((s: ChatState) => ({
        messages: [...s.messages, {
          id: genId(),
          role: 'assistant',
          content: `❌ ${event.message}`,
          timestamp: event.timestamp,
          events: [...s.pendingEvents, event],
        }],
        pendingEvents: [],
        isProcessing: false,
      }));
      return;
    }

    // Capture shell/terminal outputs into our mock terminal window
    if (type === 'agent_progress' && event.message?.startsWith('$')) {
      set((s: ChatState) => ({
        terminalOutput: [...s.terminalOutput, event.message!]
      }));
    }

    // Progress events — accumulate
    set((s: ChatState) => ({
      pendingEvents: [...s.pendingEvents, event],
    }));
  },

  setProfile: (profile: ProfileData) => set({ profile }),
  setSetupRequired: (v: boolean) => set({ setupRequired: v }),
  clearMessages: () => set({ messages: [], pendingEvents: [], isProcessing: false }),
}));
