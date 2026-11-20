const CHAVE_MEMBRO = "quemfaz:membroId";
const CHAVE_SESSAO = "quemfaz:sessao";
const CHAVE_PKCE = "quemfaz:pkce";

let cognito = null;

function ler(chave, area = localStorage) {
  try {
    return JSON.parse(area.getItem(chave));
  } catch {
    return null;
  }
}

function gravar(chave, valor, area = localStorage) {
  try {
    if (valor == null) area.removeItem(chave);
    else area.setItem(chave, JSON.stringify(valor));
  } catch {
  }
}

export function membroSalvo() {
  return ler(CHAVE_MEMBRO);
}

export function salvarMembro(id) {
  gravar(CHAVE_MEMBRO, id || null);
}

export function modoGoogle() {
  return cognito !== null;
}

export function logado() {
  return modoGoogle() ? Boolean(ler(CHAVE_SESSAO)) : Boolean(membroSalvo());
}

export async function iniciar() {
  try {
    const res = await fetch("/config.json", { cache: "no-store" });
    cognito = (await res.json())?.cognito || null;
  } catch {
    cognito = null;
  }
  if (!cognito) return;

  const params = new URLSearchParams(location.search);
  if (!params.has("code") && !params.has("error")) return;

  history.replaceState(null, "", location.pathname);
  const pkce = ler(CHAVE_PKCE, sessionStorage);
  gravar(CHAVE_PKCE, null, sessionStorage);

  if (params.has("error")) return;

  if (!pkce || pkce.state !== params.get("state")) {
    throw new Error("Não foi possível concluir o login. Tente de novo.");
  }
  await pedirTokens({
    grant_type: "authorization_code",
    code: params.get("code"),
    redirect_uri: voltarPara(),
    code_verifier: pkce.verifier,
  });
}

export async function entrarComGoogle() {
  const verifier = aleatorio(32);
  const state = aleatorio(16);
  gravar(CHAVE_PKCE, { verifier, state }, sessionStorage);

  const url = new URL(`${cognito.url}/oauth2/authorize`);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: cognito.clientId,
    redirect_uri: voltarPara(),
    identity_provider: "Google",
    scope: "openid email profile",
    state,
    code_challenge: await sha256(verifier),
    code_challenge_method: "S256",
  });
  location.assign(url);
}

export function esquecerSessao() {
  gravar(CHAVE_SESSAO, null);
  salvarMembro(null);
}

export function sair() {
  esquecerSessao();
  if (!modoGoogle()) return;
  const url = new URL(`${cognito.url}/logout`);
  url.search = new URLSearchParams({ client_id: cognito.clientId, logout_uri: voltarPara() });
  location.assign(url);
}

export async function tokenAtual() {
  if (!modoGoogle()) return null;
  const sessao = ler(CHAVE_SESSAO);
  if (!sessao) return null;
  if (Date.now() < sessao.expira - 60_000) return sessao.idToken;
  try {
    await pedirTokens({ grant_type: "refresh_token", refresh_token: sessao.refreshToken });
    return ler(CHAVE_SESSAO)?.idToken ?? null;
  } catch {
    esquecerSessao();
    return null;
  }
}

export function perfil() {
  const token = ler(CHAVE_SESSAO)?.idToken;
  if (!token) return {};
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = new TextDecoder().decode(Uint8Array.from(atob(base64), (c) => c.charCodeAt(0)));
    const dados = JSON.parse(json);
    return { nome: dados.given_name || dados.name || "", email: dados.email || "" };
  } catch {
    return {};
  }
}

function voltarPara() {
  return `${location.origin}/`;
}

async function pedirTokens(parametros) {
  let res;
  try {
    res = await fetch(`${cognito.url}/oauth2/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: cognito.clientId, ...parametros }),
    });
  } catch {
    throw new Error("Sem conexão com o serviço de login.");
  }
  if (!res.ok) throw new Error("O login expirou. Entre de novo.");
  const t = await res.json();
  const anterior = ler(CHAVE_SESSAO);
  gravar(CHAVE_SESSAO, {
    idToken: t.id_token,
    refreshToken: t.refresh_token || anterior?.refreshToken,
    expira: Date.now() + t.expires_in * 1000,
  });
}

function base64url(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function aleatorio(n) {
  return base64url(crypto.getRandomValues(new Uint8Array(n)));
}

async function sha256(texto) {
  return base64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto)));
}
