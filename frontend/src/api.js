// Cliente da API do QuemFaz. Todas as rotas ficam sob /api no mesmo domínio
// do site (CloudFront), então não há CORS.
//
// Enquanto o Cognito (#40) não está pronto, o usuário é identificado pelo
// header x-membro-id, guardado no localStorage. Quando o Cognito entrar,
// basta trocar `cabecalhoAuth` para mandar o token (Authorization: Bearer ...).

const CHAVE = "quemfaz:membroId";

export function membroSalvo() {
  try {
    return localStorage.getItem(CHAVE);
  } catch {
    return null;
  }
}

export function salvarMembro(id) {
  try {
    if (id) localStorage.setItem(CHAVE, id);
    else localStorage.removeItem(CHAVE);
  } catch {
    // sem localStorage (aba anônima bloqueada): segue só em memória
  }
}

function cabecalhoAuth(membroId) {
  return membroId ? { "x-membro-id": membroId } : {};
}

async function req(membroId, metodo, rota, corpo) {
  let res;
  try {
    res = await fetch(`/api${rota}`, {
      method: metodo,
      headers: { "Content-Type": "application/json", ...cabecalhoAuth(membroId) },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new Error("Sem conexão com o servidor.");
  }
  const dados = await res.json().catch(() => null);
  if (!res.ok) {
    // Sem corpo JSON = a resposta não veio das Lambdas (ex.: proxy do Vite
    // sem o `sam local` rodando, ou falha no API Gateway).
    if (!dados?.message && res.status >= 500) {
      throw new Error(`Servidor indisponível (erro ${res.status}). O backend está rodando?`);
    }
    const erro = new Error(dados?.message || `Erro ${res.status}`);
    erro.status = res.status;
    throw erro;
  }
  return dados;
}

export const api = (membroId) => ({
  login: (dados) => req(membroId, "POST", "/login", dados),
  criarNucleo: (nome) => req(membroId, "POST", "/nucleos", { nome }),
  entrarNucleo: (nucleoId) =>
    req(membroId, "POST", `/nucleos/${encodeURIComponent(nucleoId)}/membros`),
  nucleo: (nucleoId) => req(membroId, "GET", `/nucleos/${encodeURIComponent(nucleoId)}`),
  tarefas: () => req(membroId, "GET", "/tarefas"),
  criarTarefa: (tarefa) => req(membroId, "POST", "/tarefas", tarefa),
  escolher: (id) => req(membroId, "POST", `/tarefas/${id}/escolher`),
  concluir: (id) => req(membroId, "POST", `/tarefas/${id}/concluir`),
  aprovar: (tarefaId, aprovado) =>
    req(membroId, "POST", "/aprovar", { tarefaId, aprovado }),
  placar: () => req(membroId, "GET", "/placar"),
});
