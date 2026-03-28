'use client';

import { useState } from 'react';
import Header from '@/components/Header';
import { Settings, Shield, HardDrive, Key, Check } from 'lucide-react';

export default function SettingsPage() {
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleSave = () => {
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  }

  const sections = [
    { title: 'Identity & Data', icon: Shield, desc: 'Manage your AI identity and data privacy' },
    { title: 'AI Model Preferences', icon: Settings, desc: 'Select and configure your preferred AI provider' },
    { title: 'Advanced Storage', icon: HardDrive, desc: 'Manage local and cloud memory configurations' },
    { title: 'API Configuration', icon: Key, desc: 'Enter your custom API keys for providers' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="mb-12">
          <h1 className="text-4xl font-black text-gray-900 tracking-tight">App Settings</h1>
          <p className="text-gray-500 mt-2 font-medium">Fine-tune your Lirox experience and AI preferences.</p>
        </div>

        <div className="space-y-8">
          <div className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-xl shadow-gray-200/40">
            <h2 className="text-xl font-bold text-gray-900 mb-8 flex items-center gap-2">
              <div className="p-2 bg-blue-600 rounded-xl text-white shadow-lg shadow-blue-200">
                <Settings size={20} />
              </div>
              Model Configuration
            </h2>
            
            <div className="space-y-10">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">AI Provider</label>
                  <select className="w-full px-5 py-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm font-bold text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all">
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="openai">OpenAI (GPT-4o)</option>
                    <option value="google">Google (Gemini Pro)</option>
                    <option value="openrouter">OpenRouter (Any Model)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Model Name</label>
                  <input
                    type="text"
                    placeholder="claude-3-5-sonnet-20241022"
                    className="w-full px-5 py-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm font-bold text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder-gray-300"
                  />
                </div>
              </div>

              <div className="space-y-10 pt-10 border-t border-gray-50">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div>
                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Claude API Key</label>
                    <input
                      type="password"
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full px-5 py-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm font-bold text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">OpenRouter API Key</label>
                    <input
                      type="password"
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full px-5 py-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm font-bold text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-8 flex justify-end">
                <button
                  onClick={handleSave}
                  className="px-10 py-4 bg-blue-600 text-white rounded-2xl text-sm font-bold hover:bg-blue-700 shadow-xl shadow-blue-200 transition-all active:scale-95 flex items-center gap-2"
                >
                  {saveSuccess ? <><Check size={18} /> SETTINGS SAVED</> : 'SAVE PREFERENCES'}
                </button>
              </div>
            </div>
          </div>

          <div className="bg-red-50 rounded-[2rem] border border-red-100 p-8 shadow-xl shadow-red-200/20">
            <h2 className="text-xl font-bold text-red-900 mb-2">Danger Zone</h2>
            <p className="text-sm text-red-700 font-medium mb-8">Once you delete your AI memory, it cannot be recovered. Choose wisely.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button className="px-6 py-4 bg-white border border-red-200 text-red-600 rounded-2xl text-xs font-bold hover:bg-red-600 hover:text-white transition-all shadow-sm uppercase tracking-widest">
                CLEAR ALL MESSAGES
              </button>
              <button className="px-6 py-4 bg-white border border-red-200 text-red-600 rounded-2xl text-xs font-bold hover:bg-red-600 hover:text-white transition-all shadow-sm uppercase tracking-widest">
                DELETE AI IDENTITY
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
