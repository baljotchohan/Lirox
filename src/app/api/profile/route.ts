import { NextRequest, NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    const userId = 'default_user';

    const { data, error } = await supabaseAdmin
      .from('user_profile')
      .select('profile_data, preferences')
      .eq('user_id', userId)
      .single();

    if (error && error.code !== 'PGRST116') {
      throw error;
    }

    const profile = data?.profile_data || {
      roles: [],
      interests: [],
      goals: [],
      pain_points: [],
      preferences: {}
    };

    return NextResponse.json(profile);
  } catch (error: any) {
    console.error('Profile API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
