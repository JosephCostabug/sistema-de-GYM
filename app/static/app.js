const metodos = [
  { id: "biometria", label: "Biometria" },
  { id: "face", label: "Face" },
  { id: "cartao", label: "Cartão" },
  { id: "pin", label: "PIN" },
  { id: "qr", label: "QR" },
];

const demos = [
  { nome: "João — Básico", plano: "3x/semana, 08:00-18:00, só Centro", creds: [
    ["cartao", "CARD-JOAO-001"], ["pin", "1234"], ["biometria", "BIO-JOAO-001"],
  ]},
    { nome: "Maria — Premium", plano: "Ilimitado, qualquer hora, os dois ginásios", creds: [
    ["face", "FACE-MARIA-001"], ["cartao", "CARD-MARIA-001"], ["qr", "QR-MARIA-001"],
  ]},
  { nome: "Pedro — Night", plano: "4x/semana, 18:00-23:00", creds: [
    ["biometria", "BIO-PEDRO-001"], ["cartao", "CARD-PEDRO-001"],
  ]},
];

let metodoAtual = "cartao";

function $(id) { return document.getElementById(id); }

function renderMetodos() {
  $("metodos").innerHTML = metodos.map((m) =>
    `<button type="button" data-id="${m.id}" class="${m.id === metodoAtual ? "active" : ""}">${m.label}</button>`
  ).join("");
  $("metodos").onclick = (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    metodoAtual = btn.dataset.id;
    renderMetodos();
  };
}

async function carregarGinasios() {
  const lista = await fetch("/ginasios").then((r) => r.json());
  $("ginasio").innerHTML = lista.map((g) => `<option value="${g.id}">${g.nome}</option>`).join("");
}

function renderDemos() {
  $("demos").innerHTML = demos.map((d, i) => `
    <article class="demo">
      <strong>${d.nome}</strong>
      <p class="muted">${d.plano}</p>
      ${d.creds.map(([m, c]) => `<button type="button" data-demo="${i}" data-metodo="${m}" data-codigo="${c}">${m}: ${c}</button>`).join("")}
    </article>
  `).join("");
  $("demos").onclick = (e) => {
    const btn = e.target.closest("button[data-codigo]");
    if (!btn) return;
    metodoAtual = btn.dataset.metodo;
    $("credencial").value = btn.dataset.codigo;
    renderMetodos();
  };
}

function htmlUso(uso) {
  if (!uso) return "";
  const sem = uso.max_visitas_semana == null ? "ilimitado" : `${uso.visitas_semana}/${uso.max_visitas_semana}`;
  const mes = uso.max_visitas_mes == null ? "ilimitado" : `${uso.visitas_mes}/${uso.max_visitas_mes}`;
  return `<p class="muted">Uso do plano — semana: ${sem} · mês: ${mes}</p>`;
}

async function marcar(tipo) {
  const resultado = $("resultado");
  resultado.hidden = false;
  const body = {
    ginasio_id: $("ginasio").value,
    metodo: metodoAtual,
    credencial: $("credencial").value.trim(),
  };
  if (tipo) body.tipo = tipo;
  const resposta = await fetch("/presencas/marcar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    resultado.className = "resultado fail";
    resultado.innerHTML = `<h3>Acesso recusado</h3><p>${dados.detail || "Não foi possível marcar."}</p>`;
    return;
  }
  resultado.className = "resultado ok";
  resultado.innerHTML = `
    <h3>${dados.tipo === "entrada" ? "Entrada" : "Saída"} autorizada</h3>
    <p>${dados.mensagem}</p>
    <p class="muted">${dados.cliente} · ${dados.plano} · ${dados.ginasio} · ${dados.metodo}</p>
    ${dados.duracao_minutos != null ? `<p class="muted">Duração: ${dados.duracao_minutos} min</p>` : ""}
    ${dados.aviso ? `<p>${dados.aviso}</p>` : ""}
    ${htmlUso(dados.uso_plano)}
  `;
  await carregarHistorico();
}

async function carregarHistorico() {
  const lista = await fetch("/presencas").then((r) => r.json());
  $("historico").innerHTML = lista.slice(0, 8).map((p) => `
    <article class="item">
      <strong>${p.cliente || p.cliente_id}</strong>
      <p class="muted">${p.ginasio} · ${p.metodo} · ${p.aberta ? "dentro" : "saiu"}</p>
      <p class="muted">In: ${p.entrada_em}${p.saida_em ? ` · Out: ${p.saida_em}` : ""}</p>
    </article>
  `).join("") || `<p class="muted">Ainda sem marcações.</p>`;
}

$("auto").onclick = () => marcar(null);
$("entrada").onclick = () => marcar("entrada");
$("saida").onclick = () => marcar("saida");

renderMetodos();
renderDemos();
carregarGinasios();
carregarHistorico();
