import { NextRequest, NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase';
import { callLLM, LLMMessage, LLMConfig } from '@/lib/llm';

export async function POST(req: NextRequest) {
  try {
    const { message } = await req.json();
    const userId = 'default_user';

    // 1. Get user profile and preferences (model/provider)
    const { data: profileData } = await supabaseAdmin
      .from('user_profile')
      .select('profile_data, preferences')
      .eq('user_id', userId)
      .single();

    const profile = profileData?.profile_data || {};
    const preferences = profileData?.preferences || {};

    // 2. Determine LLM Config (defaulting to Anthropic if not set)
    const config: LLMConfig = {
      provider: (preferences.provider as any) || 'anthropic',
      model: preferences.model || 'claude-3-5-sonnet-20241022',
      apiKey: '',
    };

    // Set API Key from env based on provider
    switch (config.provider) {
      case 'openai': config.apiKey = process.env.OPENAI_API_KEY!; break;
      case 'anthropic': config.apiKey = process.env.ANTHROPIC_API_KEY!; break;
      case 'google': config.apiKey = process.env.GOOGLE_GENERATIVE_AI_API_KEY!; break;
      case 'openrouter': config.apiKey = process.env.OPENROUTER_API_KEY!; break;
    }

    // 3. Get recent conversations for context
    const { data: recentConvs } = await supabaseAdmin
      .from('conversations')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(5);

    const history: LLMMessage[] = (recentConvs || []).reverse().flatMap((c) => [
      { role: 'user', content: c.user_message },
      { role: 'assistant', content: c.assistant_response },
    ]);

    // 4. System Prompt
    const systemPrompt = `You are Lirox, a personal AI for ${userId}.
About User:
- Roles: ${(profile.roles || []).join(', ')}
- Interests: ${(profile.interests || []).join(', ')}
- Goals: ${(profile.goals || []).join(', ')}
- Challenges: ${(profile.pain_points || []).join(', ')}

Your Voice: Helpful, warm, and deeply personal. Reference past context when possible.`;

    const messages: LLMMessage[] = [
      { role: 'system', content: systemPrompt },
      ...history,
      { role: 'user', content: message },
    ];

    // 5. Call LLM
    const assistantMessage = await callLLM(config, messages);

    // 6. Save Conversation
    await supabaseAdmin.from('conversations').insert({
      user_id: userId,
      user_message: message,
      assistant_response: assistantMessage,
    });

    // 7. Extract Profile (Async)
    extractProfileAsync(userId, message, assistantMessage);

    return NextResponse.json({ response: assistantMessage, profile });
  } catch (error: any) {
    console.error('Chat API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

async function extractProfileAsync(userId: string, userMsg: string, assistantResponse: string) {
  try {
    const config: LLMConfig = {
      provider: 'anthropic',
      model: 'claude-3-5-sonnet-20241022',
      apiKey: process.env.ANTHROPIC_API_KEY!,
    };

    const extractionPrompt = `Extract user facts from this snippet:
User: "${userMsg}"
Assistant: "${assistantResponse}"

Return ONLY valid JSON:
{
  "roles": ["role1"],
  "interests": ["interest1"],
  "goals": ["goal1"],
  "pain_points": ["pain1"],
  "preferences": {}
}`;

    const text = await callLLM(config, [{ role: 'user', content: extractionPrompt }]);
    const facts = JSON.parse(text.replace(/```json|```/g, ''));

    const { data: profileData } = await supabaseAdmin.from('user_profile').select('profile_data').eq('user_id', userId).single();
    const existing = profileData?.profile_data || {};

    const updated = {
      roles: Array.from(new Set([...(existing.roles || []), ...(facts.roles || [])])),
      interests: Array.from(new Set([...(existing.interests || []), ...(facts.interests || [])])),
      goals: Array.from(new Set([...(existing.goals || []), ...(facts.goals || [])])),
      pain_points: Array.from(new Set([...(existing.pain_points || []), ...(facts.pain_points || [])])),
      preferences: { ...existing.preferences, ...facts.preferences },
    };

    await supabaseAdmin.from('user_profile').upsert({ user_id: userId, profile_data: updated, updated_at: new Date().toISOString() });
  } catch (error) {
    console.error('Profile extraction error:', error);
  }
}
