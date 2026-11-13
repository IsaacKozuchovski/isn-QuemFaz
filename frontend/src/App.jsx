import { useCallback, useEffect, useState } from "react";
import { api, membroSalvo, salvarMembro } from "./api.js";

const STATUS = {
  disponivel: "Disponível",
  em_execucao: "Em execução",
  aguardando_aprovacao: "Aguardando aprovação",
  concluida: "Concluída",
};

export default function App() {
  const [membro, setMembro] = useState(null);
  const [carregando, setCarregando] = useState(Boolean(membroSalvo()));
  const [erro, setErro] = useState("");

  // POST /login devolve o membro já cadastrado, então serve para recarregar
  // os dados (pontos, núcleo) de quem já entrou antes.
  const recarregar = useCallback(async () => {
    const id = membroSalvo();
    if (!id) return;
    try {
      setMembro(await api(id).login({}));
    } catch (e) {
      salvarMembro(null);
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  function sair() {
    salvarMembro(null);
    setMembro(null);
  }

  let conteudo;
  if (carregando) conteudo = <p className="vazio">Carregando…</p>;
  else if (!membro) conteudo = <Login onEntrar={setMembro} erroInicial={erro} />;
  else if (!membro.nucleoId) conteudo = <SemNucleo membro={membro} onPronto={recarregar} />;
  else conteudo = <Painel membro={membro} onMudou={recarregar} />;

  return (
    <>
      <header className="topo">
        <h1 className="logo">
          Quem<span>Faz</span>
        </h1>
        {membro && (
          <div className="usuario">
            <span className="avatar" aria-hidden="true">
              {membro.nome.trim().charAt(0).toUpperCase()}
            </span>
            <span className="usuario-nome">{membro.nome}</span>
            <span className="placa-pontos" title="Seus pontos">
              <strong>{membro.pontos ?? 0}</strong> pts
            </span>
            <button className="sair" onClick={sair}>
              Sair
            </button>
          </div>
        )}
      </header>
      <main>{conteudo}</main>
    </>
  );
}

// ---- UC01 · Autenticar-se ------------------------------------------------
// Etapa 1: só o email. Se o membro já existe, POST /login devolve o cadastro
// e a pessoa entra direto. Se não existe, a API responde 400 pedindo nome e
// idade, e aí aparece a etapa 2 (primeiro acesso).
function Login({ onEntrar, erroInicial }) {
  const [erro, setErro] = useState(erroInicial);
  const [enviando, setEnviando] = useState(false);
  const [email, setEmail] = useState("");
  const [novo, setNovo] = useState(false);

  async function enviar(ev) {
    ev.preventDefault();
    const f = new FormData(ev.target);
    const id = email.trim().toLowerCase();
    const dados = novo
      ? { email: id, nome: f.get("nome").trim(), idade: Number(f.get("idade")) }
      : {};

    setEnviando(true);
    setErro("");
    try {
      const membro = await api(id).login(dados);
      salvarMembro(id);
      onEntrar(membro);
    } catch (e) {
      if (!novo && e.status === 400) setNovo(true);
      else setErro(e.message);
    } finally {
      setEnviando(false);
    }
  }

  function trocarEmail() {
    setNovo(false);
    setErro("");
  }

  return (
    <form className="cartao" onSubmit={enviar}>
      <h2>{novo ? "Primeiro acesso" : "Entrar"}</h2>
      <p className="dica">
        {novo
          ? "Não encontramos esse email. Conte um pouco sobre você para criar seu cadastro."
          : "O login com Google (Cognito) chega na próxima etapa. Por enquanto, o email identifica você."}
      </p>
      <label>
        Email
        <input
          name="email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          readOnly={novo}
        />
      </label>
      {novo && (
        <>
          <div className="linha">
            <label>
              Nome
              <input name="nome" required autoFocus autoComplete="given-name" />
            </label>
            <label className="curto">
              Idade
              <input name="idade" type="number" min="0" required />
            </label>
          </div>
          <button type="button" className="link" onClick={trocarEmail}>
            Usar outro email
          </button>
        </>
      )}
      <button disabled={enviando}>
        {enviando ? "Entrando…" : novo ? "Criar cadastro" : "Continuar"}
      </button>
      <Erro texto={erro} />
    </form>
  );
}

// ---- UC02 / UC03 · Criar ou entrar num núcleo ----------------------------
function SemNucleo({ membro, onPronto }) {
  const [erro, setErro] = useState("");
  const cliente = api(membro.membroId);

  async function executar(ev, acao) {
    ev.preventDefault();
    const valor = new FormData(ev.target).get("valor").trim();
    setErro("");
    try {
      await acao(valor);
      await onPronto();
    } catch (e) {
      setErro(e.message);
    }
  }

  return (
    <div className="cartao">
      <h2>Olá, {membro.nome}!</h2>
      <p>Você ainda não faz parte de um núcleo familiar.</p>

      <form onSubmit={(ev) => executar(ev, cliente.criarNucleo)}>
        <h3>Criar um núcleo</h3>
        <div className="linha">
          <input name="valor" placeholder="Ex.: Família Silva" required />
          <button>Criar</button>
        </div>
      </form>

      <form onSubmit={(ev) => executar(ev, cliente.entrarNucleo)}>
        <h3>Entrar com um código de convite</h3>
        <div className="linha">
          <input name="valor" placeholder="Código do núcleo" required />
          <button>Entrar</button>
        </div>
      </form>
      <Erro texto={erro} />
    </div>
  );
}

// ---- Painel do núcleo ----------------------------------------------------
function Painel({ membro, onMudou }) {
  const [aba, setAba] = useState("tarefas");
  const [tarefas, setTarefas] = useState([]);
  const [placar, setPlacar] = useState([]);
  const [erro, setErro] = useState("");
  const cliente = api(membro.membroId);

  const carregar = useCallback(async () => {
    try {
      const c = api(membro.membroId);
      const [t, p] = await Promise.all([c.tarefas(), c.placar()]);
      setTarefas(t);
      setPlacar(p);
      setErro("");
    } catch (e) {
      setErro(e.message);
    }
  }, [membro.membroId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  // O nome do núcleo não muda, então basta buscar uma vez
  const [nucleo, setNucleo] = useState(null);
  useEffect(() => {
    api(membro.membroId)
      .nucleo(membro.nucleoId)
      .then(setNucleo)
      .catch(() => setNucleo(null));
  }, [membro.membroId, membro.nucleoId]);

  const [ocupado, setOcupado] = useState(false);

  // Executa uma ação e já mostra a tarefa devolvida pela API; o resto
  // (lista completa, placar, pontos do topo) é recarregado em segundo plano.
  async function agir(acao) {
    setOcupado(true);
    let ok = false;
    try {
      const tarefa = await acao();
      ok = true;
      setErro("");
      if (tarefa?.tarefaId) {
        setTarefas((lista) => {
          const outras = lista.filter((t) => t.tarefaId !== tarefa.tarefaId);
          return [...outras, tarefa];
        });
      }
    } catch (e) {
      setErro(e.message);
    } finally {
      setOcupado(false);
    }
    carregar();
    onMudou();
    return ok;
  }

  const nomes = Object.fromEntries(placar.map((m) => [m.membroId, m.nome]));
  const pendentes = tarefas.filter(
    (t) => t.status === "aguardando_aprovacao" && t.responsavel !== membro.membroId,
  );

  return (
    <>
      <Convite nucleoId={membro.nucleoId} />
      <nav className="abas">
        <Aba id="tarefas" atual={aba} onClick={setAba}>
          Tarefas
        </Aba>
        <Aba id="aprovacoes" atual={aba} onClick={setAba}>
          Aprovações{pendentes.length > 0 && <span className="selo">{pendentes.length}</span>}
        </Aba>
        <Aba id="placar" atual={aba} onClick={setAba}>
          Placar
        </Aba>
      </nav>
      <Erro texto={erro} />

      {/* disabled num fieldset desativa todos os botões de dentro */}
      <fieldset className="conteudo" disabled={ocupado}>
      {aba === "tarefas" && (
        <>
          <NovaTarefa onCriar={(t) => agir(() => cliente.criarTarefa(t))} />
          <ListaTarefas
            tarefas={tarefas}
            membro={membro}
            nomes={nomes}
            onEscolher={(id) => agir(() => cliente.escolher(id))}
            onConcluir={(id) => agir(() => cliente.concluir(id))}
          />
        </>
      )}
      {aba === "aprovacoes" && (
        <Aprovacoes
          tarefas={pendentes}
          nomes={nomes}
          onDecidir={(id, ok) => agir(() => cliente.aprovar(id, ok))}
        />
      )}
      {aba === "placar" && (
        <Placar
          familia={nucleo?.nome}
          placar={placar}
          membro={membro}
          tarefas={tarefas}
          nomes={nomes}
        />
      )}
      </fieldset>
    </>
  );
}

function Convite({ nucleoId }) {
  const [estado, setEstado] = useState("pronto"); // pronto | copiado | falhou

  async function copiar() {
    const ok = await copiarTexto(nucleoId);
    setEstado(ok ? "copiado" : "falhou");
    setTimeout(() => setEstado("pronto"), 2000);
  }

  return (
    <section className="convite">
      <div className="convite-texto">
        <strong>Convide sua família</strong>
        <span className="dica">Quem receber o código entra pelo “Entrar com um código de convite”.</span>
      </div>
      <div className="convite-codigo">
        {/* clicar no código seleciona tudo, para copiar à mão se precisar */}
        <code onClick={(e) => window.getSelection()?.selectAllChildren(e.currentTarget)}>
          {nucleoId}
        </code>
        <button className={`copiar ${estado}`} onClick={copiar}>
          {estado === "copiado" ? "✓ Copiado!" : estado === "falhou" ? "Selecione e copie" : "Copiar"}
        </button>
      </div>
    </section>
  );
}

// navigator.clipboard só existe em HTTPS ou localhost. No acesso pela rede
// (http://192.168…) usa o jeito antigo, com um textarea temporário.
async function copiarTexto(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = texto;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

function Aba({ id, atual, onClick, children }) {
  return (
    <button className={id === atual ? "aba ativa" : "aba"} onClick={() => onClick(id)}>
      {children}
    </button>
  );
}

// ---- UC04 · Cadastrar tarefa ---------------------------------------------
function NovaTarefa({ onCriar }) {
  const [aberto, setAberto] = useState(false);

  async function enviar(ev) {
    ev.preventDefault();
    const form = ev.target;
    const f = new FormData(form);
    const ok = await onCriar({
      nome: f.get("nome").trim(),
      descricao: f.get("descricao").trim(),
      pontos: Number(f.get("pontos")),
      idadeMinima: Number(f.get("idadeMinima") || 0),
      // datetime-local vem no fuso do navegador; toISOString converte para UTC (…Z)
      horarioLimite: new Date(f.get("horarioLimite")).toISOString(),
    });
    if (ok) {
      form.reset();
      setAberto(false);
    }
  }

  if (!aberto) {
    return (
      <button className="nova" onClick={() => setAberto(true)}>
        + Nova tarefa
      </button>
    );
  }
  return (
    <form className="cartao" onSubmit={enviar}>
      <h3>Nova tarefa</h3>
      <label>
        Nome
        <input name="nome" required maxLength={80} placeholder="Ex.: Lavar a louça" />
      </label>
      <label>
        Descrição <span className="opcional">(opcional)</span>
        <textarea
          name="descricao"
          rows={3}
          maxLength={500}
          placeholder="Ex.: Inclui secar e guardar as panelas."
        />
      </label>
      <div className="linha">
        <label>
          Pontos
          <input name="pontos" type="number" min="1" required />
        </label>
        <label>
          Idade mínima
          <input name="idadeMinima" type="number" min="0" defaultValue="0" />
        </label>
      </div>
      <label>
        Horário-limite
        <input name="horarioLimite" type="datetime-local" required />
      </label>
      <div className="linha">
        <button>Cadastrar</button>
        <button type="button" className="secundario" onClick={() => setAberto(false)}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

// ---- UC05 / UC07 · Escolher e concluir -----------------------------------
function ListaTarefas({ tarefas, membro, nomes, onEscolher, onConcluir }) {
  if (tarefas.length === 0) {
    return <p className="vazio">Nenhuma tarefa cadastrada ainda.</p>;
  }
  const agora = new Date();
  const quem = (id) => (id === membro.membroId ? "Você" : nomes[id] || "?");

  function acao(t) {
    const vencida = new Date(t.horarioLimite) <= agora;
    if (t.status === "disponivel") {
      if (vencida) return <span className="aviso">Prazo encerrado</span>;
      if (membro.idade < t.idadeMinima) {
        // RN01
        return <span className="aviso">Só a partir de {t.idadeMinima} anos</span>;
      }
      return <button onClick={() => onEscolher(t.tarefaId)}>Escolher</button>;
    }
    if (t.status === "em_execucao" && t.responsavel === membro.membroId) {
      return <button onClick={() => onConcluir(t.tarefaId)}>Concluí</button>;
    }
    return null;
  }

  return Object.entries(STATUS).map(([status, titulo]) => {
    const grupo = tarefas
      .filter((t) => t.status === status)
      .sort((a, b) => a.horarioLimite.localeCompare(b.horarioLimite));
    if (grupo.length === 0) return null;

    const cartoes = (
      <ul className="lista">
        {grupo.map((t) => (
          <TarefaCard key={t.tarefaId} tarefa={t} quem={t.responsavel && quem(t.responsavel)}>
            {acao(t)}
          </TarefaCard>
        ))}
      </ul>
    );
    const cabecalho = (
      <>
        {titulo} <span className="contador">{grupo.length}</span>
      </>
    );

    // Concluídas ficam recolhidas para não poluir a lista
    if (status === "concluida") {
      return (
        <details key={status} className="grupo">
          <summary>{cabecalho}</summary>
          {cartoes}
        </details>
      );
    }
    return (
      <section key={status} className="grupo">
        <h3>{cabecalho}</h3>
        {cartoes}
      </section>
    );
  });
}

// ---- UC08 · Aprovar ou rejeitar ------------------------------------------
function Aprovacoes({ tarefas, nomes, onDecidir }) {
  if (tarefas.length === 0) {
    return <p className="vazio">Nada aguardando sua aprovação.</p>;
  }
  return (
    <ul className="lista">
      {tarefas.map((t) => (
        <TarefaCard key={t.tarefaId} tarefa={t} quem={nomes[t.responsavel] || "?"}>
          <button onClick={() => onDecidir(t.tarefaId, true)}>Aprovar</button>
          <button className="secundario" onClick={() => onDecidir(t.tarefaId, false)}>
            Rejeitar
          </button>
        </TarefaCard>
      ))}
    </ul>
  );
}

function TarefaCard({ tarefa: t, quem, children }) {
  const temAcao = [].concat(children).some(Boolean);
  return (
    <li className={`tarefa ${t.status}`}>
      <div className="tarefa-topo">
        <strong className="tarefa-nome">{t.nome}</strong>
        <span className="pontos">{t.pontos} pts</span>
      </div>
      {t.descricao && <p className="descricao">{t.descricao}</p>}
      <dl className="meta">
        <div>
          <dt>Prazo</dt>
          <dd>{formatar(t.horarioLimite)}</dd>
        </div>
        {t.idadeMinima > 0 && (
          <div>
            <dt>Idade mínima</dt>
            <dd>{t.idadeMinima} anos</dd>
          </div>
        )}
        {quem && (
          <div>
            <dt>Responsável</dt>
            <dd>{quem}</dd>
          </div>
        )}
      </dl>
      {temAcao && <div className="tarefa-acoes">{children}</div>}
    </li>
  );
}

// ---- UC09 · Placar -------------------------------------------------------
// Clicar numa pessoa mostra as tarefas concluídas (aprovadas) que somaram
// os pontos dela — as tarefas do núcleo já estão carregadas no Painel.
function Placar({ familia, placar, membro, tarefas, nomes }) {
  const total = placar.reduce((soma, m) => soma + m.pontos, 0);
  return (
    <>
    <div className="placar-titulo">
      <h2>{familia || "Placar"}</h2>
      <span className="dica">
        {placar.length} {placar.length === 1 ? "membro" : "membros"} · {total} pts no total
      </span>
    </div>
    <ol className="lista placar">
      {placar.map((m, i) => {
        const feitas = tarefas
          .filter((t) => t.status === "concluida" && t.responsavel === m.membroId)
          .sort((a, b) => b.horarioLimite.localeCompare(a.horarioLimite));
        return (
          <li key={m.membroId} className={m.membroId === membro.membroId ? "eu" : ""}>
            <details>
              <summary>
                <span className="posicao">{i + 1}º</span>
                <span className="nome">
                  {m.nome}
                  {m.membroId === membro.membroId && <span className="dica"> (você)</span>}
                </span>
                <strong>{m.pontos} pts</strong>
              </summary>
              {feitas.length === 0 ? (
                <p className="dica feitas-vazio">Nenhuma tarefa aprovada ainda.</p>
              ) : (
                <ul className="feitas">
                  {feitas.map((t) => (
                    <li key={t.tarefaId}>
                      <div>
                        <span>{t.nome}</span>
                        <small>
                          aprovada por {nomes[t.aprovadaPor] || "?"} · prazo{" "}
                          {formatar(t.horarioLimite)}
                        </small>
                      </div>
                      <span className="pontos">+{t.pontos}</span>
                    </li>
                  ))}
                </ul>
              )}
            </details>
          </li>
        );
      })}
    </ol>
    </>
  );
}

function Erro({ texto }) {
  return texto ? (
    <p className="erro" role="alert">
      {texto}
    </p>
  ) : null;
}

// "13/11 às 21:07"
function formatar(iso) {
  const d = new Date(iso);
  const dia = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${dia} às ${hora}`;
}
