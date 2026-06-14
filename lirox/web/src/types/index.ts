// [WEB-6] TypeScript types matching Python OrchestratorEvent

export interface OrchestratorEvent {
  type: 'thinking_phase' | 'agent_progress' | 'tool_call' | 'tool_result' |
        'warning' | 'streaming' | 'done' | 'error' | 'connected' | 'ping' | 'command_result';
  message: string;
  agent: string;
  data: Record<string, any>;
  timestamp: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  events: OrchestratorEvent[];
  isStreaming?: boolean;
  fileResult?: FileResult;
}

export interface FileResult {
  path: string;
  filename: string;
  size: number;
  type: 'pdf' | 'docx' | 'xlsx' | 'pptx';
  downloadUrl: string;
}

export interface ProfileData {
  agent_name: string;
  user_name: string;
  niche: string;
  profession: string;
  current_project: string;
  goals: string[];
  tone: string;
  llm_provider?: string;
}

export interface MemoryStats {
  facts: number;
  topics: number;
  projects: number;
  preferences: number;
}

export interface ProviderStatus {
  name: string;
  available: boolean;
  model?: string;
  type?: 'local' | 'cloud';
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface CommandInfo {
  command: string;
  description: string;
}
