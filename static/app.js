"use strict";

(() => {
  const input = document.getElementById("password");
  const toggle = document.getElementById("toggle-password");
  const clear = document.getElementById("clear-password");
  const count = document.getElementById("character-count");
  const status = document.getElementById("request-status");
  const block = document.getElementById("strength-block");
  const label = document.getElementById("strength-label");
  const meter = document.getElementById("strength-meter");
  const description = document.getElementById("strength-description");
  const criteriaCount = document.getElementById("criteria-count");
  const criteria = [...document.querySelectorAll("[data-criterion]")];
  const recommendations = document.getElementById("recommendations");
  const intro = document.getElementById("tips-intro");
  const initialTips = [...recommendations.children].map((item) => item.textContent);
  const initialIntro = intro.textContent;
  const limit = Number(input.dataset.limit);
  let timer;
  let controller;
  let revision = 0;

  function showTips(tips) {
    recommendations.replaceChildren(...tips.map((tip) => {
      const item = document.createElement("li");
      item.textContent = tip;
      return item;
    }));
  }

  function resetResult() {
    block.dataset.level = "empty";
    label.textContent = "Aguardando sua senha";
    meter.setAttribute("aria-valuenow", "0");
    meter.setAttribute("aria-valuetext", "Aguardando sua senha");
    [...meter.children].forEach((segment) => segment.classList.remove("active"));
    description.textContent = "Cada caractere pode fazer a diferença.";
    criteriaCount.textContent = "0 de 5 critérios";
    criteria.forEach((item) => {
      item.classList.remove("met");
      item.querySelector(".criterion-state").textContent = "Não atendido";
    });
    intro.textContent = initialIntro;
    showTips(initialTips);
  }

  function showStatus(message, error = false) {
    status.textContent = message;
    status.classList.toggle("error", error);
  }

  function render(data) {
    block.dataset.level = String(data.nivel);
    label.textContent = data.classificacao;
    meter.setAttribute("aria-valuenow", String(data.nivel + 1));
    meter.setAttribute("aria-valuetext", data.classificacao);
    [...meter.children].forEach((segment, index) => {
      segment.classList.toggle("active", index <= data.nivel);
    });
    const length = data.comprimento_avaliado;
    description.textContent = `${length} ${length === 1 ? "caractere avaliado" : "caracteres avaliados"} · espaços e invisíveis não somam pontos.`;
    let met = 0;
    criteria.forEach((item) => {
      const criterion = data.criterios.find((entry) => entry.id === item.dataset.criterion);
      const passed = Boolean(criterion && criterion.atendido);
      item.classList.toggle("met", passed);
      item.querySelector(".criterion-state").textContent = passed ? "Atendido" : "Não atendido";
      if (passed) met += 1;
    });
    criteriaCount.textContent = `${met} de 5 critérios`;
    intro.textContent = data.nivel >= 3
      ? "Um bom começo. Estes hábitos ajudam a manter sua proteção."
      : "Pequenos ajustes podem deixar sua senha mais resistente.";
    showTips(data.recomendacoes);
    showStatus(`Análise concluída: ${data.classificacao.toLocaleLowerCase("pt-BR")}.`);
  }

  function validResponse(data) {
    const labels = ["Muito fraca", "Fraca", "Média", "Forte", "Muito forte"];
    const ids = criteria.map((item) => item.dataset.criterion);
    return data && Number.isInteger(data.nivel)
      && data.nivel >= 0 && data.nivel < labels.length
      && data.classificacao === labels[data.nivel]
      && Number.isInteger(data.comprimento_avaliado) && data.comprimento_avaliado >= 0
      && Array.isArray(data.criterios) && data.criterios.length === ids.length
      && ids.every((id) => data.criterios.filter((item) => item
        && item.id === id && typeof item.atendido === "boolean").length === 1)
      && Array.isArray(data.recomendacoes)
      && data.recomendacoes.every((item) => typeof item === "string");
  }

  async function analyze(senha, currentRevision) {
    const requestController = new AbortController();
    controller = requestController;
    const timeout = setTimeout(() => requestController.abort(), 8000);
    try {
      const response = await fetch("/api/analisar", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ senha }),
        signal: requestController.signal,
        cache: "no-store",
        credentials: "omit",
        mode: "same-origin",
        redirect: "error",
      });
      if (currentRevision !== revision) return;
      const data = await response.json();
      if (currentRevision !== revision) return;
      if (response.status === 429) {
        const error = new Error("Limite de requisições");
        error.rateLimited = true;
        throw error;
      }
      if (!response.ok) throw new Error(data.erro || "Não foi possível analisar a senha.");
      if (!validResponse(data)) throw new Error("Resposta inválida do servidor.");
      render(data);
    } catch (error) {
      if (currentRevision !== revision) return;
      resetResult();
      let message = "Não foi possível analisar. Verifique se o servidor local está ativo e tente novamente.";
      if (error.name === "AbortError") {
        message = "A análise demorou demais. Digite novamente para tentar.";
      } else if (error.rateLimited) {
        message = "Muitas análises em pouco tempo. Aguarde um minuto e tente novamente.";
      }
      showStatus(message, true);
      label.textContent = "Análise indisponível";
    } finally {
      clearTimeout(timeout);
      if (currentRevision === revision) {
        input.setAttribute("aria-busy", "false");
        controller = undefined;
      }
    }
  }

  function onInput() {
    revision += 1;
    const currentRevision = revision;
    clearTimeout(timer);
    if (controller) controller.abort();
    resetResult();
    input.setAttribute("aria-busy", "false");
    showStatus("");
    const senha = input.value;
    const length = Array.from(senha).length;
    count.textContent = `${length} ${length === 1 ? "caractere" : "caracteres"}`;
    clear.disabled = length === 0;
    if (length === 0) return;
    if (length > limit) {
      label.textContent = "Limite excedido";
      showStatus(`Use no máximo ${limit} caracteres.`, true);
      return;
    }
    input.setAttribute("aria-busy", "true");
    label.textContent = "Analisando…";
    showStatus("Atualizando sua análise…");
    timer = setTimeout(() => analyze(senha, currentRevision), 300);
  }

  function clearInput() {
    input.value = "";
    input.type = "password";
    toggle.setAttribute("aria-pressed", "false");
    toggle.setAttribute("aria-label", "Mostrar senha");
    toggle.title = "Mostrar senha";
    onInput();
  }

  input.addEventListener("input", onInput);
  toggle.addEventListener("click", () => {
    const showing = input.type === "password";
    input.type = showing ? "text" : "password";
    toggle.setAttribute("aria-pressed", String(showing));
    toggle.setAttribute("aria-label", showing ? "Ocultar senha" : "Mostrar senha");
    toggle.title = showing ? "Ocultar senha" : "Mostrar senha";
    input.focus();
  });
  clear.addEventListener("click", () => { clearInput(); input.focus(); });
  window.addEventListener("pagehide", clearInput);
  window.addEventListener("pageshow", (event) => { if (event.persisted) clearInput(); });
  clearInput();
})();
