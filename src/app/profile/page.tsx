'use client';

import { useState, useEffect } from 'react';
import Header from '@/components/Header';
import { User, Zap, Target, AlertTriangle, Settings, Plus } from 'lucide-react';

export default function ProfilePage() {
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    fetch('/api/profile')
      .then((r) => r.json())
      .then(setProfile)
      .catch(console.error);
  }, []);

  if (!profile) return <div className="p-8 text-gray-500">Lirox is loading your complete AI memory...</div>;

  const sections = [
    { title: 'Roles', icon: User, data: profile.roles || [], color: 'bg-blue-600', sub: 'Your professional and personal identities' },
    { title: 'Interests', icon: Zap, data: profile.interests || [], color: 'bg-purple-600', sub: 'What makes you creative and curious' },
    { title: 'Goals', icon: Target, data: profile.goals || [], color: 'bg-green-600', sub: 'The milestones you are aiming for' },
    { title: 'Challenges', icon: AlertTriangle, data: profile.pain_points || [], color: 'bg-orange-600', sub: 'Problems Lirox helps you solve' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-5xl mx-auto px-6 py-12">
        <div className="flex justify-between items-end mb-12">
          <div>
            <h1 className="text-4xl font-black text-gray-900 tracking-tight">AI Identity</h1>
            <p className="text-gray-500 mt-2 font-medium">This is the context Lirox uses to personalize every response.</p>
          </div>
          <button className="flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 rounded-2xl text-sm font-bold text-gray-700 hover:shadow-lg transition-all shadow-sm">
            <Plus size={16} /> ADD MANUAL FACT
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {sections.map((section, idx) => (
            <div key={idx} className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-xl shadow-gray-200/30 group hover:border-blue-200 transition-all">
              <div className="flex items-center gap-4 mb-6">
                <div className={`w-14 h-14 rounded-2xl ${section.color} flex items-center justify-center text-white shadow-lg shadow-${section.color.split('-')[1]}-200`}>
                  <section.icon size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{section.title}</h2>
                  <p className="text-xs text-gray-400 font-medium">{section.sub}</p>
                </div>
              </div>

              {section.data.length > 0 ? (
                <div className="flex flex-wrap gap-3">
                  {section.data.map((item: string, i: number) => (
                    <div
                      key={i}
                      className="px-5 py-3 bg-gray-50 border border-gray-100 text-gray-800 rounded-2xl text-sm font-semibold hover:bg-white hover:border-blue-500 hover:text-blue-600 transition-all cursor-default shadow-sm"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-10 text-center border-2 border-dashed border-gray-100 rounded-3xl">
                  <p className="text-sm text-gray-400 font-medium italic">No {section.title.toLowerCase()} extracted yet.</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
