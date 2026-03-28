'use client';

import Link from 'next/link';

export default function Header() {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-xl shadow-lg shadow-blue-200">
            🧠
          </div>
          <div className="flex flex-col">
            <h1 className="text-xl font-bold text-gray-900 leading-tight">Lirox</h1>
            <p className="text-[10px] uppercase tracking-wider text-blue-600 font-bold">Personal AI</p>
          </div>
        </div>
        <nav className="flex gap-8 items-center">
          <Link href="/" className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors">Chat</Link>
          <Link href="/profile" className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors">Profile</Link>
          <Link href="/settings" className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors">Settings</Link>
          <div className="h-4 w-[1px] bg-gray-200 mx-2"></div>
          <button className="px-5 py-2 rounded-full bg-gray-900 text-white text-sm font-semibold hover:bg-gray-800 transition-all active:scale-95">
            Sign Out
          </button>
        </nav>
      </div>
    </header>
  );
}
