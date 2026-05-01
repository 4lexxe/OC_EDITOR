function byId(id) {
  return document.getElementById(id);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return response.json();
}

const state = {
  registers: { PC: "000000000000", ACC: "000000000000", GPR: "000000000000", F: "0", M: "000000000000" },
  memory: Array.from({ length: 256 }, () => "000000000000"),
  code: "",
  pc_counter: 0,
};

const INSTRUCCIONES = [
  ["ACC+1 -> ACC", "Incrementa ACC en 1"],
  ["GPR+1 -> GPR", "Incrementa GPR en 1"],
  ["ACC+GPR -> ACC", "Suma ACC + GPR en ACC"],
  ["GPR+ACC -> ACC", "Suma GPR + ACC en ACC"],
  ["ACC -> GPR", "Copia ACC a GPR"],
  ["GPR -> ACC", "Copia GPR a ACC"],
  ["GPR -> M", "Copia GPR al registro M"],
  ["M -> GPR", "Copia M a GPR"],
  ["M -> ACC", "Copia M a ACC"],
  ["ACC! -> ACC", "NOT de ACC"],
  ["! ACC", "NOT de ACC (alias)"],
  ["! F", "NOT del flag F"],
  ["0 -> ACC", "Pone ACC en cero"],
  ["0 -> F", "Pone F en cero"],
  ["ROL F, ACC", "Rotación izquierda F y ACC"],
  ["ROR F, ACC", "Rotación derecha F y ACC"],
  ["GPR(AD) -> MAR", "Carga MAR con campo AD"],
  ["PC -> MAR", "Carga MAR con PC"],
  ["PC+1 -> PC", "Incrementa PC"],
  ["GPR(OP) -> OPR", "Carga OPR desde GPR(OP)"],
];

const autocompleteState = {
  items: [],
  activeIndex: 0,
};

const FONT_SIZE_KEY = "editor_web_font_size";

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function splitComment(line) {
  const markers = [";", "//", "#"];
  let idx = -1;
  let marker = "";
  markers.forEach((m) => {
    const i = line.indexOf(m);
    if (i !== -1 && (idx === -1 || i < idx)) {
      idx = i;
      marker = m;
    }
  });
  if (idx === -1) {
    return { code: line, comment: "" };
  }
  return { code: line.slice(0, idx), comment: line.slice(idx) };
}

function instructionClass(rawCode) {
  const code = rawCode.trim().toUpperCase();
  if (!code) {
    return "";
  }
  if (code.startsWith("ROL ") || code.startsWith("ROR ")) {
    return "tok-rotate";
  }
  if (code.includes("PC")) {
    return "tok-control";
  }
  if (code.includes("MAR") || code.includes("(AD)") || code.includes("OPR") || code.includes(" M ")) {
    return "tok-memory";
  }
  if (code.startsWith("ACC ->") || code.startsWith("GPR ->") || code.startsWith("M ->")) {
    return "tok-transfer";
  }
  if (code.includes("!") || code.includes("NOT")) {
    return "tok-logic";
  }
  if (code.includes("+") || code.includes("0 ->")) {
    return "tok-alu";
  }
  return "tok-transfer";
}

function renderHighlightedCode() {
  const code = byId("code").value || "";
  const lines = code.split("\n");
  const html = lines.map((line) => {
    const { code: baseCode, comment } = splitComment(line);
    const cls = instructionClass(baseCode);
    const codeHtml = baseCode
      ? `<span class="${cls}">${escapeHtml(baseCode)}</span>`
      : "";
    const commentHtml = comment
      ? `<span class="tok-comment">${escapeHtml(comment)}</span>`
      : "";
    const merged = `${codeHtml}${commentHtml}`;
    // Mantiene altura visual en líneas vacías para que caret y resaltado queden alineados.
    return merged || `<span class="tok-empty">&#8203;</span>`;
  }).join("\n");
  // Si termina en salto de línea, preservamos la línea visual final.
  const withTrailing = code.endsWith("\n") ? `${html}\n<span class="tok-empty">&#8203;</span>` : html;
  byId("code-highlight").innerHTML = withTrailing || `<span class="tok-empty">&#8203;</span>`;
}

function syncEditorMetrics() {
  const code = byId("code");
  const highlight = byId("code-highlight");
  if (!code || !highlight) {
    return;
  }
  const style = window.getComputedStyle(code);
  highlight.style.fontFamily = style.fontFamily;
  highlight.style.fontSize = style.fontSize;
  highlight.style.lineHeight = style.lineHeight;
  highlight.style.letterSpacing = style.letterSpacing;
  highlight.style.paddingTop = style.paddingTop;
  highlight.style.paddingRight = style.paddingRight;
  highlight.style.paddingBottom = style.paddingBottom;
  highlight.style.paddingLeft = style.paddingLeft;
}

function setStatus(text, isError = false) {
  const bar = byId("statusbar");
  bar.textContent = text || "";
  bar.classList.toggle("error", Boolean(isError));
}

function applyEditorFontSize(size) {
  const value = Math.max(12, Math.min(26, Number(size) || 16));
  document.documentElement.style.setProperty("--editor-font-size", `${value}px`);
  document.documentElement.style.setProperty("--editor-line-height", value >= 20 ? "1.5" : "1.45");
  const range = byId("font-size-range");
  const label = byId("font-size-value");
  if (range) {
    range.value = String(value);
  }
  if (label) {
    label.textContent = `${value} px`;
  }
  localStorage.setItem(FONT_SIZE_KEY, String(value));
  updateLineNumbers();
  renderAutocomplete();
}

function getCurrentLineInfo() {
  const code = byId("code");
  const full = code.value;
  const cursor = code.selectionStart;
  const before = full.slice(0, cursor);
  const lineStart = before.lastIndexOf("\n") + 1;
  const lineEndIdx = full.indexOf("\n", cursor);
  const lineEnd = lineEndIdx === -1 ? full.length : lineEndIdx;
  const lineText = full.slice(lineStart, lineEnd);
  return { lineStart, lineEnd, lineText, cursor };
}

function replaceCurrentLine(newText) {
  const code = byId("code");
  const { lineStart, lineEnd } = getCurrentLineInfo();
  code.setRangeText(newText, lineStart, lineEnd, "end");
  updateLineNumbers();
  scheduleLiveUpdate();
  code.focus();
}

function insertLineBelow(text) {
  const code = byId("code");
  const { lineEnd } = getCurrentLineInfo();
  const prefix = code.value.length === 0 ? "" : "\n";
  code.setRangeText(`${prefix}${text}`, lineEnd, lineEnd, "end");
  updateLineNumbers();
  scheduleLiveUpdate();
  code.focus();
}

function registerPayload() {
  return {
    code: byId("code").value,
    registers: {
      PC: byId("reg-PC-bin").value,
      ACC: byId("reg-ACC-bin").value,
      GPR: byId("reg-GPR-bin").value,
      F: byId("reg-F-bin").value,
      M: byId("reg-M-bin").value,
    },
    memory: Array.from({ length: 256 }, (_, i) => byId(`mem-edit-${i}`).value),
    pc_counter: state.pc_counter,
  };
}

function renderRegisters(registers, registersHex) {
  const container = byId("registers");
  if (!container.dataset.ready) {
    container.innerHTML = `
      <div></div><div class="head">Binario</div><div class="head">Hex</div>
      ${["PC", "ACC", "GPR", "F", "M"].map((name) => `
        <label>${name}</label>
        <input id="reg-${name}-bin" />
        <input id="reg-${name}-hex" />
      `).join("")}
    `;
    container.dataset.ready = "1";
    ["PC", "ACC", "GPR", "F", "M"].forEach((name) => {
      byId(`reg-${name}-bin`).addEventListener("input", () => {
        const bits = name === "F" ? 1 : 12;
        const clean = byId(`reg-${name}-bin`).value.replace(/[^01]/g, "");
        byId(`reg-${name}-bin`).value = clean.slice(-bits).padStart(bits, "0");
      });
      byId(`reg-${name}-hex`).addEventListener("input", () => {
        const bits = name === "F" ? 1 : 12;
        const maxLen = bits === 1 ? 1 : 3;
        const hex = byId(`reg-${name}-hex`).value.toUpperCase().replace(/[^0-9A-F]/g, "").slice(-maxLen);
        byId(`reg-${name}-hex`).value = hex;
        if (!hex) {
          byId(`reg-${name}-bin`).value = bits === 1 ? "0" : "000000000000";
          return;
        }
        const asBin = parseInt(hex, 16).toString(2).padStart(bits, "0").slice(-bits);
        byId(`reg-${name}-bin`).value = asBin;
      });
    });
  }
  ["PC", "ACC", "GPR", "F", "M"].forEach((name) => {
    byId(`reg-${name}-bin`).value = registers[name];
    byId(`reg-${name}-hex`).value = registersHex[name];
  });
}

function renderMemory(memory, memoryHex, editableId, readonly = false) {
  const container = byId(editableId);
  if (!container.dataset.ready) {
    container.innerHTML = Array.from({ length: 256 }, (_, i) => `
      <div class="mem-row">
        <span class="addr">${i.toString(16).toUpperCase().padStart(4, "0")}</span>
        ${readonly ? `<span id="${editableId}-bin-${i}">000000000000</span>` : `<input id="mem-edit-${i}" />`}
        <span class="hex" id="${editableId}-hex-${i}">000</span>
      </div>
    `).join("");
    container.dataset.ready = "1";
    if (!readonly) {
      Array.from({ length: 256 }, (_, i) => i).forEach((i) => {
        byId(`mem-edit-${i}`).addEventListener("input", () => {
          const clean = byId(`mem-edit-${i}`).value.replace(/[^01]/g, "");
          byId(`mem-edit-${i}`).value = clean.slice(-12).padStart(12, "0");
        });
      });
    }
  }
  Array.from({ length: 256 }, (_, i) => i).forEach((i) => {
    if (readonly) {
      byId(`${editableId}-bin-${i}`).textContent = memory[i];
    } else {
      byId(`mem-edit-${i}`).value = memory[i];
    }
    byId(`${editableId}-hex-${i}`).textContent = memoryHex[i];
  });
}

function renderResults(registers) {
  const results = byId("results");
  if (results) {
    results.innerHTML = `
      <span>PC: ${registers.PC}</span>
      <span>ACC: ${registers.ACC}</span>
      <span>GPR: ${registers.GPR}</span>
      <span>M: ${registers.M}</span>
      <span>F: ${registers.F}</span>
    `;
  }
  byId("pc-line").textContent = `Línea actual (PC interno): ${Number(state.pc_counter) + 1}`;
}

function renderTrace(rows) {
  const tbody = byId("trace-body");
  tbody.innerHTML = rows.map((r) => `
    <tr>
      <td>${r.ciclo || ""}</td>
      <td>${r.micro || ""}</td>
      <td>${r.PC || ""}</td>
      <td>${r.MAR || ""}</td>
      <td>${r.GPR || ""}</td>
      <td>${r.GPR_OP || ""}</td>
      <td>${r.GPR_AD || ""}</td>
      <td>${r.OPR || ""}</td>
      <td>${r.ACC || ""}</td>
      <td>${r.F || ""}</td>
      <td>${r.M || ""}</td>
    </tr>
  `).join("");
}

function updateLineNumbers() {
  const code = byId("code").value || "";
  const lines = code.split("\n").length;
  byId("line-numbers").value = Array.from({ length: lines }, (_, i) => `${i + 1}`).join("\n");
  syncEditorMetrics();
  renderHighlightedCode();
}

function closeAutocomplete() {
  byId("autocomplete-popup").classList.add("hidden");
  autocompleteState.items = [];
  autocompleteState.activeIndex = 0;
}

function getCaretCoordinates(textarea, position) {
  const div = document.createElement("div");
  const style = window.getComputedStyle(textarea);
  const properties = [
    "boxSizing", "width", "height", "overflowX", "overflowY",
    "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "fontStyle", "fontVariant", "fontWeight", "fontStretch", "fontSize", "fontFamily",
    "lineHeight", "textAlign", "textTransform", "textIndent", "letterSpacing", "wordSpacing",
  ];
  properties.forEach((prop) => {
    div.style[prop] = style[prop];
  });
  div.style.position = "absolute";
  div.style.visibility = "hidden";
  div.style.whiteSpace = "pre-wrap";
  div.style.wordWrap = "break-word";
  div.style.left = "-9999px";
  div.style.top = "0";

  const before = textarea.value.substring(0, position);
  const after = textarea.value.substring(position) || ".";
  div.textContent = before;
  const span = document.createElement("span");
  span.textContent = after[0];
  div.appendChild(span);
  document.body.appendChild(div);
  const rect = span.getBoundingClientRect();
  const textareaRect = textarea.getBoundingClientRect();
  const coords = {
    left: textareaRect.left + (rect.left - div.getBoundingClientRect().left) - textarea.scrollLeft,
    top: textareaRect.top + (rect.top - div.getBoundingClientRect().top) - textarea.scrollTop,
    bottom: textareaRect.top + (rect.bottom - div.getBoundingClientRect().top) - textarea.scrollTop,
  };
  document.body.removeChild(div);
  return coords;
}

function showAutocomplete() {
  const popup = byId("autocomplete-popup");
  popup.classList.remove("hidden");
  const code = byId("code");
  const caret = getCaretCoordinates(code, code.selectionStart);
  const editorBoxRect = document.querySelector(".editor-box").getBoundingClientRect();
  const left = Math.max(58, caret.left - editorBoxRect.left + 8);
  const top = Math.max(80, caret.bottom - editorBoxRect.top + 6);
  popup.style.left = `${left}px`;
  popup.style.top = `${top}px`;
}

function renderAutocomplete() {
  const list = byId("autocomplete-list");
  const tip = byId("autocomplete-tip");
  if (!autocompleteState.items.length) {
    closeAutocomplete();
    return;
  }
  list.innerHTML = autocompleteState.items.map(([text], idx) => `
    <li data-idx="${idx}" class="${idx === autocompleteState.activeIndex ? "active" : ""}">${text}</li>
  `).join("");
  tip.textContent = autocompleteState.items[autocompleteState.activeIndex][1];
  list.querySelectorAll("li").forEach((li) => {
    li.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const idx = Number(li.dataset.idx);
      autocompleteState.activeIndex = idx;
      applyAutocompleteSelection();
    });
  });
}

function applyAutocompleteSelection() {
  if (!autocompleteState.items.length) {
    return;
  }
  const [text] = autocompleteState.items[autocompleteState.activeIndex];
  replaceCurrentLine(text);
  closeAutocomplete();
}

function updateAutocompleteFromEditor() {
  const { lineText } = getCurrentLineInfo();
  const query = lineText.trim().toLowerCase();
  if (!query) {
    closeAutocomplete();
    return;
  }
  autocompleteState.items = INSTRUCCIONES.filter(([instr]) => instr.toLowerCase().startsWith(query)).slice(0, 8);
  autocompleteState.activeIndex = 0;
  if (!autocompleteState.items.length) {
    closeAutocomplete();
    return;
  }
  showAutocomplete();
  renderAutocomplete();
}

async function refreshTrace() {
  const payload = registerPayload();
  const data = await postJson("/api/trace", {
    code: payload.code,
    registers: payload.registers,
    memory: payload.memory,
    trace_mode: byId("trace-mode").value,
    mar_pc_decimal: byId("trace-decimal").checked,
    compact: byId("trace-compact").checked,
  });
  if (!data.ok) {
    byId("trace-status").textContent = "No se pudo actualizar la traza.";
    return;
  }
  renderTrace(data.rows || []);
  byId("trace-status").textContent = data.error || `${(data.rows || []).length} μops simuladas`;
  byId("trace-memory").textContent = data.memory_info || "";
  byId("trace-explanation").textContent = data.explanation || "";
}

async function refreshInference() {
  const data = await postJson("/api/infer", { code: byId("code").value });
  if (!data.ok) {
    byId("infer-text").textContent = "Sin inferencia.";
    return;
  }
  const text = data.mode ? `Instrucción: ${data.inference}  |  Modo: ${data.mode}` : data.inference;
  byId("infer-text").textContent = text;
}

function applyState(remote) {
  state.code = remote.code;
  state.pc_counter = remote.pc_counter;
  state.registers = remote.registers;
  state.memory = remote.memory;
  byId("code").value = remote.code;
  updateLineNumbers();
  renderRegisters(remote.registers, remote.registers_hex);
  renderMemory(remote.memory, remote.memory_hex, "memory-edit", false);
  renderMemory(remote.memory, remote.memory_hex, "memory-view", true);
  renderResults(remote.registers);
  setStatus(remote.status, remote.is_error);
  const ln = byId("line-numbers");
  ln.classList.toggle("current-step", true);
  syncEditorMetrics();
  renderHighlightedCode();
}

async function loadInitialState() {
  const data = await fetch("/api/state").then((r) => r.json());
  if (data.ok) {
    applyState(data.state);
  }
  await refreshInference();
  await refreshTrace();
}

let updateTimer = null;
function scheduleLiveUpdate() {
  if (updateTimer) {
    clearTimeout(updateTimer);
  }
  updateTimer = setTimeout(async () => {
    updateTimer = null;
    await refreshInference();
    await refreshTrace();
  }, 180);
}

function initEvents() {
  const savedFontSize = localStorage.getItem(FONT_SIZE_KEY);
  applyEditorFontSize(savedFontSize ? Number(savedFontSize) : 16);

  byId("code").addEventListener("input", () => {
    updateLineNumbers();
    updateAutocompleteFromEditor();
    scheduleLiveUpdate();
  });
  byId("code").addEventListener("scroll", () => {
    byId("line-numbers").scrollTop = byId("code").scrollTop;
    byId("code-highlight").scrollTop = byId("code").scrollTop;
    byId("code-highlight").scrollLeft = byId("code").scrollLeft;
  });
  byId("code").addEventListener("input", syncEditorMetrics);
  byId("trace-mode").addEventListener("change", refreshTrace);
  byId("trace-decimal").addEventListener("change", refreshTrace);
  byId("trace-compact").addEventListener("change", refreshTrace);

  byId("code").addEventListener("keydown", (event) => {
    if (event.key === "Tab" && !byId("autocomplete-popup").classList.contains("hidden")) {
      event.preventDefault();
      applyAutocompleteSelection();
      return;
    }
    if (event.key === "ArrowDown" && !byId("autocomplete-popup").classList.contains("hidden")) {
      event.preventDefault();
      autocompleteState.activeIndex = Math.min(autocompleteState.activeIndex + 1, autocompleteState.items.length - 1);
      renderAutocomplete();
      return;
    }
    if (event.key === "ArrowUp" && !byId("autocomplete-popup").classList.contains("hidden")) {
      event.preventDefault();
      autocompleteState.activeIndex = Math.max(autocompleteState.activeIndex - 1, 0);
      renderAutocomplete();
      return;
    }
    if (event.key === "Escape") {
      closeAutocomplete();
    }
  });

  byId("code").addEventListener("click", updateAutocompleteFromEditor);

  byId("code").addEventListener("blur", () => {
    setTimeout(closeAutocomplete, 120);
  });

  byId("btn-run-step").addEventListener("click", async () => {
    const data = await postJson("/api/execute-step", registerPayload());
    if (data.ok) {
      applyState(data.state);
      await refreshInference();
      await refreshTrace();
    }
  });

  byId("btn-reset").addEventListener("click", async () => {
    const data = await postJson("/api/reset", {});
    if (data.ok) {
      applyState(data.state);
      await refreshInference();
      await refreshTrace();
    }
  });

  byId("btn-infer").addEventListener("click", refreshInference);
  byId("btn-copy-infer").addEventListener("click", async () => {
    const text = byId("infer-text").textContent.trim();
    if (!text) {
      setStatus("No hay instrucción inferida para copiar.", true);
      return;
    }
    const only = text.replace(/^Instrucción:\s*/i, "").split("  |  Modo:")[0].trim();
    try {
      await navigator.clipboard.writeText(only);
      setStatus("Instrucción copiada al portapapeles.");
    } catch {
      setStatus("No se pudo copiar al portapapeles.", true);
    }
  });

  byId("btn-generate").addEventListener("click", async () => {
    const expression = byId("gen-expression").value.trim();
    const mode = byId("gen-mode").value;
    const data = await postJson("/api/generate", { expression, mode });
    if (!data.ok) {
      byId("gen-result").textContent = `Error: ${data.error || "No se pudo generar."}`;
      setStatus("Error al generar.", true);
      return;
    }
    byId("code").value = data.ops.join("\n");
    updateLineNumbers();
    byId("gen-result").textContent = data.message;
    setStatus(data.message);
    await refreshInference();
    await refreshTrace();
  });

  byId("btn-config").addEventListener("click", () => {
    byId("config-modal").showModal();
  });

  byId("btn-config-close").addEventListener("click", () => {
    byId("config-modal").close();
  });

  byId("font-size-range").addEventListener("input", () => {
    applyEditorFontSize(byId("font-size-range").value);
    syncEditorMetrics();
  });

  window.addEventListener("resize", () => {
    syncEditorMetrics();
    renderHighlightedCode();
  });

  const KEEPALIVE_MS = 8 * 60 * 1000;
  const pingKeepalive = () => {
    fetch("/api/keepalive", { method: "GET", credentials: "same-origin" }).catch(() => {});
  };
  pingKeepalive();
  setInterval(pingKeepalive, KEEPALIVE_MS);
}

initEvents();
loadInitialState();
