// Cliente da API do QuemFaz. Todas as rotas ficam sob /api no mesmo domínio
// do site (CloudFront), então não há CORS.
//
// Com o login do Google ativo, cada requisição leva o token do Cognito
// (Authorization: Bearer ...). No modo de teste, leva o email digitado no
// header x-membro-id. Ver auth.js.

import { tokenAtual } from "./auth.js";

async function cabecalhoAuth(membroId) {
  const token = await tokenAtual();
  if (token) return { Authorization: `Bearer ${token}` };
  return membroId ? { "x-membro-id": membroId } : {};
}

async function req(membroId, metodo, rota, corpo) {
  let res;
  try {
    res = await fetch(`/api${rota}`, {
      method: metodo,
      headers: { "Content-Type": "application/json", ...(await cabecalhoAuth(membroId)) },
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
