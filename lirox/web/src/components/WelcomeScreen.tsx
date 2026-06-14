import React from 'react';
import { Zap, Brain, FileText, Terminal, Sparkles } from 'lucide-react';

interface Props {
  onSuggestion: (text: string) => void;
}

const SUGGESTIONS = [
  { icon: <Zap className="w-4 h-4" />, text: 'Create a Python web scraper', color: 'text-lirox-gold' },
  { icon: <Brain className="w-4 h-4" />, text: 'Explain how transformers work', color: 'text-lirox-thinking' },
  { icon: <FileText className="w-4 h-4" />, text: 'Generate a business plan PDF', color: 'text-lirox-success' },
  { icon: <Terminal className="w-4 h-4" />, text: 'Set up a FastAPI project', color: 'text-blue-400' },
];

export function WelcomeScreen({ onSuggestion }: Props) {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 animate-fade-in w-full max-w-3xl mx-auto mt-16">
      {/* Hero */}
      <div className="mb-12 text-center flex flex-col items-center">
        <div className="w-12 h-12 mb-6 rounded-lg bg-[#2D2D2D] flex items-center justify-center border border-[#3A3A3A]">
          <Sparkles className="w-6 h-6 text-[#EBEBEB]" />
        </div>
        <h2 className="text-3xl font-serif font-medium text-[#EBEBEB] mb-3">
          {greeting}, Operator
        </h2>
        <p className="text-[15px] text-[#A0A0A0] max-w-md mx-auto">
          How can I help you today?
        </p>
      </div>

      {/* Suggestion chips */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => onSuggestion(s.text)}
            className="flex items-center gap-3.5 px-4 py-3.5 bg-transparent border border-[#3A3A3A] rounded-xl text-left hover:bg-[#2D2D2D] transition-colors duration-200 group"
          >
            <div className={`text-[#A0A0A0]`}>
              {s.icon}
            </div>
            <span className="text-[14px] text-[#EBEBEB]">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
