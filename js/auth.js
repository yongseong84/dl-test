// Google 로그인 / 로그아웃 처리 (Supabase Auth)
const googleLoginBtn = document.getElementById("googleLoginBtn");
const userMenu = document.getElementById("userMenu");
const userAvatar = document.getElementById("userAvatar");
const userName = document.getElementById("userName");
const logoutBtn = document.getElementById("logoutBtn");

function renderAuthUI(session) {
  const isLoggedIn = Boolean(session && session.user);
  googleLoginBtn.hidden = isLoggedIn;
  userMenu.hidden = !isLoggedIn;

  if (isLoggedIn) {
    const meta = session.user.user_metadata || {};
    userAvatar.src = meta.avatar_url || meta.picture || "";
    userAvatar.alt = meta.full_name || meta.name || "";
    userName.textContent = meta.full_name || meta.name || session.user.email;
  }
}

googleLoginBtn.addEventListener("click", async () => {
  if (!isSupabaseConfigured) {
    alert(
      "Supabase 설정이 아직 완료되지 않았습니다.\njs/supabase-config.js 파일에 프로젝트 URL과 anon key를 입력한 뒤 다시 시도해주세요."
    );
    return;
  }
  const { error } = await supabaseClient.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: window.location.origin + window.location.pathname },
  });
  if (error) {
    console.error("[Supabase] 로그인 오류:", error.message);
    alert("로그인 중 오류가 발생했습니다: " + error.message);
  }
});

logoutBtn.addEventListener("click", async () => {
  const { error } = await supabaseClient.auth.signOut();
  if (error) console.error("[Supabase] 로그아웃 오류:", error.message);
});

if (isSupabaseConfigured) {
  supabaseClient.auth.getSession().then(({ data }) => renderAuthUI(data.session));
  supabaseClient.auth.onAuthStateChange((_event, session) => renderAuthUI(session));
}
