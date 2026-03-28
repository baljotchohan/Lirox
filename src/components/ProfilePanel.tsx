'use client';

import { useState, useEffect } from 'react';
import { User, Target, Zap, AlertTriangle, ChevronRight } from 'lucide-react';

export default function ProfilePanel() {
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    fetch('/api/profile')
      .then((r) => r.json())
      .then(setProfile)
      .catch(console.error);
  }, []);

  if (!profile) return <div className="p-8 text-gray-400 font-medium">Lirox is loading your profile...</div>;

  const sections = [
    { title: 'Roles', icon: User, color: 'bg-blue-50 text-blue-700 border-blue-100', data: profile.roles || [] },
    { title: 'Interests', icon: Zap, color: 'bg-purple-50 text-purple-700 border-purple-100', data: profile.interests || [] },
    { title: 'Goals', icon: Target, color: 'bg-green-50 text-green-700 border-green-100', data: profile.goals || [] },
    { title: 'Challenges', icon: AlertTriangle, color: 'bg-orange-50 text-orange-700 border-orange-100', data: profile.pain_points || [] },
  ];

  return (
    <div className="bg-white rounded-3xl border border-gray-100 shadow-xl shadow-gray-200/40 p-8 space-y-10 max-h-[700px] overflow-y-auto border-t-4 border-t-blue-500">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Your AI Brain Profile</h2>
          <p className="text-xs text-gray-500 mt-1">Real-time learning memory from LIROX</p>
        </div>
      </div>

      <div className="space-y-8">
        {sections.map((section, idx) => (
          <div key={idx} className="group">
            <div className="flex items-center gap-2 mb-4">
              <div className={`p-2 rounded-xl ${section.color} border shadow-sm`}>
                <section.icon size={16} />
              </div>
              <h3 className="text-sm font-bold text-gray-800 uppercase tracking-widest">{section.title}</h3>
            </div>

            {section.data.length > 0 ? (
              <div className="flex flex-wrap gap-2.5">
                {section.data.map((item: string, i: number) => (
                  <span
                    key={i}
                    className="px-4 py-2 bg-white border border-gray-100 text-gray-700 rounded-xl text-xs font-semibold shadow-sm hover:border-blue-300 hover:text-blue-600 transition-all cursor-default"
                  >
                    {item}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic flex items-center gap-1">
                <ChevronRight size={12} /> No {section.title.toLowerCase()} identified yet.
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="pt-6 border-t border-gray-50">
        <button className="w-full py-4 bg-gray-50 text-gray-600 text-xs font-bold rounded-2xl border border-gray-100 hover:bg-white hover:border-blue-200 hover:text-blue-600 transition-all shadow-sm">
          VIEW DETAILED PROFILE
        </button>
      </div>
    </div>
  );
}
