'use client';

import Header from '@/components/Header';
import ChatPanel from '@/components/ChatPanel';
import ProfilePanel from '@/components/ProfilePanel';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chat Panel - Takes 2 columns on large screens */}
          <div className="lg:col-span-2">
            <ChatPanel />
          </div>

          {/* Profile Panel - Takes 1 column */}
          <div>
            <ProfilePanel />
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-8 border-t border-gray-200 text-center text-sm text-gray-600">
          <p>Lirox learns from every conversation. The more you chat, the smarter I become.</p>
          <p className="mt-2 text-xs">Your data stays private and is never shared.</p>
        </div>
      </main>
    </div>
  );
}
