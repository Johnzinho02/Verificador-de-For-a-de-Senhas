"use strict";

// Testes do comportamento JavaScript com DOM e rede simulados, sem navegador.
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync(join(__dirname, "../static/app.js"), "utf8");
const flush = () => new Promise(setImmediate);

function element() {
  const classes = new Set();
  const attributes = {};
  const listeners = {};
  return {
    value: "", type: "password", textContent: "", dataset: {}, children: [],
    disabled: false, attributes,
    classList: {
      contains: (name) => classes.has(name),
      remove: (name) => classes.delete(name),
      toggle: (name, active) => active ? classes.add(name) : classes.delete(name),
    },
    setAttribute: (name, value) => { attributes[name] = value; },
    addEventListener: (name, listener) => { listeners[name] = listener; },
    emit: (name, event = {}) => listeners[name]?.(event),
    replaceChildren(...children) { this.children = children; },
    querySelector() { return this.state; },
    focus() {},
  };
}

function harness(handler) {
  const ids = [
    "password", "toggle-password", "clear-password", "character-count",
    "request-status", "strength-block", "strength-label", "strength-meter",
    "strength-description", "criteria-count", "recommendations", "tips-intro",
  ];
  const nodes = Object.fromEntries(ids.map((id) => [id, element()]));
  nodes.password.dataset.limit = "4096";
  nodes["strength-meter"].children = Array.from({ length: 5 }, element);
  nodes.recommendations.children = [Object.assign(element(), {
    textContent: "Recomendação inicial fictícia",
  })];
  nodes["tips-intro"].textContent = "Digite uma senha de exemplo.";
  const criteria = ["comprimento", "maiusculas", "minusculas", "numeros", "especiais"]
    .map((id) => Object.assign(element(), { dataset: { criterion: id }, state: element() }));
  const calls = [];
  const events = {};
  const timers = new Map();
  let timerId = 0;
  runInNewContext(source, {
    document: {
      getElementById: (id) => nodes[id],
      querySelectorAll: () => criteria,
      createElement: element,
    },
    window: { addEventListener: (name, callback) => { events[name] = callback; } },
    AbortController,
    setTimeout: (callback, delay) => {
      const id = ++timerId;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    fetch: (url, options) => {
      calls.push({ url, options });
      return handler ? handler(url, options) : Promise.resolve(response());
    },
  });
  return {
    nodes, calls, criteria, events,
    type(value) { nodes.password.value = value; nodes.password.emit("input"); },
    tick(delay) {
      for (const [id, timer] of [...timers]) {
        if (timer.delay === delay) { timers.delete(id); timer.callback(); }
      }
    },
  };
}

function response(level = 4, ok = true) {
  return {
    ok,
    json: async () => ({
      nivel: level,
      classificacao: level === 4 ? "Muito forte" : "Fraca",
      comprimento_avaliado: 16,
      criterios: ["comprimento", "maiusculas", "minusculas", "numeros", "especiais"]
        .map((id) => ({ id, atendido: true })),
      recomendacoes: ["Use uma senha exclusiva."],
    }),
  };
}

test("inicia vazio, com senha oculta e sem requisições", () => {
  const app = harness();
  assert.equal(app.nodes.password.type, "password");
  assert.equal(app.nodes["clear-password"].disabled, true);
  assert.equal(app.nodes["strength-meter"].attributes["aria-valuenow"], "0");
  assert.equal(app.calls.length, 0);
});

test("aguarda a digitação e envia apenas a entrada mais recente em JSON", async () => {
  const app = harness();
  app.type("ExemploFicticio1!");
  app.type("OutroExemploFicticio2!");
  assert.equal(app.calls.length, 0);
  app.tick(300);
  await flush();
  assert.equal(app.calls.length, 1);
  const { url, options } = app.calls[0];
  assert.equal(url, "/api/analisar");
  assert.equal(options.method, "POST");
  assert.equal(JSON.parse(options.body).senha, "OutroExemploFicticio2!");
  assert.equal(options.cache, "no-store");
  assert.equal(options.credentials, "omit");
});

test("atualiza barra, critérios e recomendações após a análise", async () => {
  const app = harness();
  app.type("ExemploFicticio1!");
  app.tick(300);
  await flush();
  assert.equal(app.nodes["strength-label"].textContent, "Muito forte");
  assert.equal(app.nodes["strength-meter"].attributes["aria-valuenow"], "5");
  assert.equal(app.nodes["criteria-count"].textContent, "5 de 5 critérios");
  assert.ok(app.criteria.every((item) => item.classList.contains("met")));
  assert.equal(app.nodes.recommendations.children[0].textContent, "Use uma senha exclusiva.");
});

test("resposta antiga não substitui o resultado da entrada atual", async () => {
  const pending = [];
  const app = harness(() => new Promise((resolve) => pending.push(resolve)));
  app.type("ExemploAnterior1!");
  app.tick(300);
  app.type("ExemploAtual2!");
  app.tick(300);
  assert.equal(app.calls[0].options.signal.aborted, true);
  pending[1](response(4));
  await flush();
  pending[0](response(1));
  await flush();
  assert.equal(app.nodes["strength-label"].textContent, "Muito forte");
});

test("limpar apaga a senha, oculta o campo e cancela a análise pendente", async () => {
  let finish;
  const app = harness(() => new Promise((resolve) => { finish = resolve; }));
  app.type("ExemploFicticio1!");
  app.nodes["toggle-password"].emit("click");
  assert.equal(app.nodes.password.type, "text");
  app.tick(300);
  app.nodes["clear-password"].emit("click");
  assert.equal(app.calls[0].options.signal.aborted, true);
  finish(response());
  await flush();
  assert.equal(app.nodes.password.value, "");
  assert.equal(app.nodes.password.type, "password");
  assert.equal(app.nodes["toggle-password"].attributes["aria-pressed"], "false");
  assert.equal(app.nodes["strength-label"].textContent, "Aguardando sua senha");
  assert.equal(app.nodes["strength-meter"].attributes["aria-valuenow"], "0");
});

test("limite conta caracteres Unicode, não unidades UTF-16", async () => {
  const app = harness();
  app.type("🔑".repeat(4096));
  app.tick(300);
  await flush();
  assert.equal(app.calls.length, 1);
  app.type("🔑".repeat(4097));
  app.tick(300);
  assert.equal(app.calls.length, 1);
  assert.equal(app.nodes["strength-label"].textContent, "Limite excedido");
});

test("falha de rede mostra erro e não deixa nota antiga na tela", async () => {
  const app = harness(() => Promise.reject(new Error("Rede indisponível")));
  app.type("ExemploFicticio1!");
  app.tick(300);
  await flush();
  assert.equal(app.nodes["strength-label"].textContent, "Análise indisponível");
  assert.ok(app.nodes["request-status"].classList.contains("error"));
  assert.equal(app.nodes["strength-meter"].attributes["aria-valuenow"], "0");
});

test("rejeição HTTP é exibida como erro, sem renderizar classificação", async () => {
  const app = harness(() => Promise.resolve(response(4, false)));
  app.type("ExemploFicticio1!");
  app.tick(300);
  await flush();
  assert.equal(app.nodes["strength-label"].textContent, "Análise indisponível");
  assert.equal(app.nodes["criteria-count"].textContent, "0 de 5 critérios");
});

test("sair da página limpa a entrada sem iniciar outra análise", () => {
  const app = harness();
  app.type("ExemploFicticio1!");
  app.events.pagehide();
  app.tick(300);
  assert.equal(app.nodes.password.value, "");
  assert.equal(app.calls.length, 0);
});

test("mostrar e ocultar preserva o valor e informa o estado acessível", () => {
  const app = harness();
  app.type("ExemploFicticio1!");
  const toggle = app.nodes["toggle-password"];
  toggle.emit("click");
  assert.equal(app.nodes.password.type, "text");
  assert.equal(toggle.attributes["aria-label"], "Ocultar senha");
  assert.equal(toggle.attributes["aria-pressed"], "true");
  toggle.emit("click");
  assert.equal(app.nodes.password.type, "password");
  assert.equal(toggle.attributes["aria-label"], "Mostrar senha");
  assert.equal(toggle.attributes["aria-pressed"], "false");
  assert.equal(app.nodes.password.value, "ExemploFicticio1!");
});

test("tempo limite interrompe a requisição e informa como tentar novamente", async () => {
  const app = harness((_, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener("abort", () => {
      reject(Object.assign(new Error("Tempo excedido"), { name: "AbortError" }));
    });
  }));
  app.type("ExemploFicticio1!");
  app.tick(300);
  app.tick(8000);
  await flush();
  assert.equal(app.calls[0].options.signal.aborted, true);
  assert.equal(app.nodes["strength-label"].textContent, "Análise indisponível");
  assert.match(app.nodes["request-status"].textContent, /demorou demais/);
  assert.equal(app.nodes.password.attributes["aria-busy"], "false");
});

test("retornar pelo histórico limpa entradas restauradas", () => {
  const app = harness();
  app.type("ExemploFicticio1!");
  app.events.pageshow({ persisted: true });
  app.tick(300);
  assert.equal(app.nodes.password.value, "");
  assert.equal(app.nodes.password.type, "password");
  assert.equal(app.calls.length, 0);
});

test("JSON inválido não preserva classificação anterior", async () => {
  const app = harness(() => Promise.resolve({
    ok: true, json: async () => { throw new SyntaxError("JSON inválido"); },
  }));
  app.type("ExemploFicticio1!");
  app.tick(300);
  await flush();
  assert.equal(app.nodes["strength-label"].textContent, "Análise indisponível");
  assert.equal(app.nodes["strength-meter"].attributes["aria-valuenow"], "0");
});

test("esquema inesperado não produz barra ou critérios incorretos", async () => {
  const cases = [
    null, {}, { nivel: 99 },
    { ...await response().json(), nivel: 99 },
    { ...await response().json(), criterios: [{ id: "comprimento", atendido: true }] },
    { ...await response().json(), recomendacoes: [123] },
  ];
  for (const data of cases) {
    const app = harness(() => Promise.resolve({ ok: true, json: async () => data }));
    app.type("ExemploFicticio1!");
    app.tick(300);
    await flush();
    assert.equal(app.nodes["strength-label"].textContent, "Análise indisponível");
    assert.equal(app.nodes["criteria-count"].textContent, "0 de 5 critérios");
  }
});

test("limite HTTP 429 orienta aguardar antes de tentar novamente", async () => {
  const app = harness(() => Promise.resolve({
    status: 429, ok: false, json: async () => ({ erro: "Muitas análises" }),
  }));
  app.type("ExemploFicticio1!");
  app.tick(300);
  await flush();
  assert.match(app.nodes["request-status"].textContent, /Aguarde um minuto/);
  assert.equal(app.nodes["strength-meter"].attributes["aria-valuenow"], "0");
});
