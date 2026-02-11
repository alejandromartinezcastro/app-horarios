import { createClient } from '@supabase/supabase-js';

import { getSupabaseEnv } from './env';

export function createServerSupabaseClient() {
  const { url, anonKey } = getSupabaseEnv();
  return createClient(url, anonKey);
}
