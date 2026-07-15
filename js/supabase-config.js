// Supabase 프로젝트 설정
// 1) https://supabase.com 에서 프로젝트 생성 후 Project Settings > API 메뉴에서 값 확인
// 2) 아래 두 값을 실제 프로젝트 값으로 교체하세요. (anon/public key는 클라이언트에 노출되어도 안전한 키입니다)
const SUPABASE_URL = "https://gfivrlbkxtwjkkktyduh.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaXZybGJreHR3amtra3R5ZHVoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQwODgzMjMsImV4cCI6MjA5OTY2NDMyM30.3TnDlNzcevXY3GtLz48rO993vvmRrboApfuBOb1e8GI";

const isSupabaseConfigured =
  SUPABASE_URL !== "YOUR_SUPABASE_URL" && SUPABASE_ANON_KEY !== "YOUR_SUPABASE_ANON_KEY";

const supabaseClient = isSupabaseConfigured
  ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null;

if (!isSupabaseConfigured) {
  console.warn(
    "[Supabase] 설정이 필요합니다. js/supabase-config.js 파일에 프로젝트 URL과 anon key를 입력하세요."
  );
}
