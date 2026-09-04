/**
 * WorldQuant BRAIN Local Alpha Simulator - Frontend Logic
 */

// Application State
const state = {
  settings: {
    alphaId: "Alpha_01",
    delay: 1,
    neutralization: "SUBINDUSTRY",
    decay: 0,
    truncation: 0.08,
    checkCorr: true,
  },
  currentResults: null,
  activeView: "code",
  curatedTemplates: [],
};

// DOM Elements
const elements = {
  // Views & Tabs
  navCode: document.getElementById("nav-code"),
  navResults: document.getElementById("nav-results"),
  viewCode: document.getElementById("view-code"),
  viewResults: document.getElementById("view-results"),
  resultsBadge: document.getElementById("results-badge"),
  tabAlphaName: document.getElementById("tab-alpha-name"),
  settingsSummaryTag: document.getElementById("settings-summary-tag"),

  // Code Editor
  codeEditor: document.getElementById("code-editor"),
  lineNumbers: document.getElementById("line-numbers"),
  btnToggleFields: document.getElementById("btn-toggle-fields"),
  fieldsDrawer: document.getElementById("fields-drawer"),
  btnCloseFields: document.getElementById("btn-close-fields"),
  btnOpenExamples: document.getElementById("btn-open-examples"),
  btnSimulate: document.getElementById("btn-simulate"),

  // Settings Modal
  settingsDialog: document.getElementById("settings-dialog"),
  btnOpenSettings: document.getElementById("btn-open-settings"),
  btnCloseModal: document.getElementById("btn-close-modal"),
  btnResetSettings: document.getElementById("btn-reset-settings"),
  btnApplySettings: document.getElementById("btn-apply-settings"),
  cfgAlphaId: document.getElementById("cfg-alpha-id"),
  cfgDelay: document.getElementById("cfg-delay"),
  cfgNeutralization: document.getElementById("cfg-neutralization"),
  cfgDecay: document.getElementById("cfg-decay"),
  cfgTruncation: document.getElementById("cfg-truncation"),
  cfgCheckCorr: document.getElementById("cfg-check-corr"),

  // Examples Modal
  examplesDialog: document.getElementById("examples-dialog"),
  btnCloseExamples: document.getElementById("btn-close-examples"),
  templateList: document.getElementById("template-list"),

  // Results View
  resultAlphaId: document.getElementById("result-alpha-id"),
  resultExpression: document.getElementById("result-expression"),
  btnBackToCode: document.getElementById("btn-back-to-code"),
  btnCommitAlpha: document.getElementById("btn-commit-alpha"),
  btnCopyExpr: document.getElementById("btn-copy-expr"),
  resRuntime: document.getElementById("res-runtime"),
  resVerdictBadge: document.getElementById("res-verdict-badge"),
  resSharpe: document.getElementById("res-sharpe"),
  resFitness: document.getElementById("res-fitness"),
  resTurnover: document.getElementById("res-turnover"),
  resReturns: document.getElementById("res-returns"),
  resDrawdown: document.getElementById("res-drawdown"),
  resMargin: document.getElementById("res-margin"),
  resSubSharpe: document.getElementById("res-sub-sharpe"),
  qcGrid: document.getElementById("qc-grid"),
  pnlSvg: document.getElementById("pnl-svg"),
  chartContainer: document.getElementById("chart-container"),
  chartTooltip: document.getElementById("chart-tooltip"),

  // Toast
  toast: document.getElementById("toast"),
};

// ==============================================================================
// 1. INITIALIZATION & EVENT LISTENERS
// ==============================================================================
document.addEventListener("DOMContentLoaded", () => {
  setupViewNavigation();
  setupEditorEvents();
  setupSettingsModal();
  setupExamplesModal();
  setupFieldsDrawer();
  setupSimulation();
  fetchInitialData();
  updateLineNumbers();
  updateSettingsSummary();
});

// Toast notification helper
function showToast(message, duration = 3000) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  elements.toast.style.opacity = "1";
  elements.toast.style.transform = "translateX(-50%) translateY(0)";

  setTimeout(() => {
    elements.toast.style.opacity = "0";
    elements.toast.style.transform = "translateX(-50%) translateY(10px)";
    setTimeout(() => elements.toast.classList.add("hidden"), 200);
  }, duration);
}

// Light-dismiss click outside fallback helper
function setupLightDismiss(dialog) {
  if (!("closedBy" in HTMLDialogElement.prototype)) {
    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      const isInside = (
        rect.top <= event.clientY &&
        event.clientY <= rect.top + rect.height &&
        rect.left <= event.clientX &&
        event.clientX <= rect.left + rect.width
      );
      if (!isInside) {
        dialog.close();
      }
    });
  }
}

// ==============================================================================
// 2. VIEW NAVIGATION (CODE / RESULTS)
// ==============================================================================
function setupViewNavigation() {
  function switchView(viewName) {
    state.activeView = viewName;
    if (viewName === "code") {
      elements.navCode.classList.add("active");
      elements.navResults.classList.remove("active");
      elements.viewCode.classList.add("active");
      elements.viewResults.classList.remove("active");
      elements.codeEditor.focus();
    } else {
      elements.navResults.classList.add("active");
      elements.navCode.classList.remove("active");
      elements.viewResults.classList.add("active");
      elements.viewCode.classList.remove("active");
      elements.resultsBadge.classList.add("hidden");
    }
  }

  elements.navCode.addEventListener("click", () => switchView("code"));
  elements.navResults.addEventListener("click", () => switchView("results"));
  elements.btnBackToCode.addEventListener("click", () => switchView("code"));

  elements.btnCopyExpr.addEventListener("click", () => {
    const expr = elements.resultExpression.textContent;
    navigator.clipboard.writeText(expr).then(() => {
      showToast("✔ 因子表达式已复制到剪贴板");
    });
  });
}

// ==============================================================================
// 3. CODE EDITOR & LINE NUMBERS
// ==============================================================================
function updateLineNumbers() {
  const lines = elements.codeEditor.value.split("\n").length;
  let numbersHtml = "";
  for (let i = 1; i <= Math.max(lines, 1); i++) {
    numbersHtml += `${i}<br>`;
  }
  elements.lineNumbers.innerHTML = numbersHtml;
}

function setupEditorEvents() {
  elements.codeEditor.addEventListener("input", updateLineNumbers);
  elements.codeEditor.addEventListener("scroll", () => {
    elements.lineNumbers.scrollTop = elements.codeEditor.scrollTop;
  });

  // Hotkey: Ctrl + Enter to run simulation
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      runSimulation();
    }
  });
}

// ==============================================================================
// 4. FIELDS & OPERATORS DRAWER
// ==============================================================================
function setupFieldsDrawer() {
  elements.btnToggleFields.addEventListener("click", () => {
    elements.fieldsDrawer.classList.toggle("collapsed");
  });

  elements.btnCloseFields.addEventListener("click", () => {
    elements.fieldsDrawer.classList.add("collapsed");
  });

  // Clicking a field/operator tag inserts it into the editor
  document.querySelectorAll(".field-tags .tag").forEach((tag) => {
    tag.addEventListener("click", () => {
      const textToInsert = tag.getAttribute("data-insert");
      insertAtCursor(elements.codeEditor, textToInsert);
      updateLineNumbers();
      elements.codeEditor.focus();
    });
  });
}

function insertAtCursor(textarea, text) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const val = textarea.value;
  textarea.value = val.substring(0, start) + text + val.substring(end);
  textarea.selectionStart = textarea.selectionEnd = start + text.length;
}

// ==============================================================================
// 5. SIMULATION SETTINGS MODAL
// ==============================================================================
function updateSettingsSummary() {
  const s = state.settings;
  elements.settingsSummaryTag.textContent = `USA / D${s.delay} / ${s.neutralization} / T${s.truncation}${s.decay > 0 ? ` / DEC${s.decay}` : ""}`;
  elements.tabAlphaName.textContent = s.alphaId || "Simulation 1";
  const modalTitle = document.getElementById("modal-settings-title");
  if (modalTitle) {
    modalTitle.textContent = `${s.alphaId || "Simulation 1"} Settings`;
  }
}

function setupSettingsModal() {
  setupLightDismiss(elements.settingsDialog);

  elements.btnOpenSettings.addEventListener("click", () => {
    elements.cfgAlphaId.value = state.settings.alphaId;
    elements.cfgDelay.value = String(state.settings.delay);
    elements.cfgNeutralization.value = state.settings.neutralization;
    elements.cfgDecay.value = state.settings.decay;
    elements.cfgTruncation.value = state.settings.truncation;
    elements.cfgCheckCorr.checked = state.settings.checkCorr;
    const modalTitle = document.getElementById("modal-settings-title");
    if (modalTitle) {
      modalTitle.textContent = `${state.settings.alphaId || "Simulation 1"} Settings`;
    }
    elements.settingsDialog.showModal();
  });

  elements.btnCloseModal.addEventListener("click", () => {
    elements.settingsDialog.close();
  });

  elements.btnResetSettings.addEventListener("click", () => {
    elements.cfgAlphaId.value = "Alpha_01";
    elements.cfgDelay.value = "1";
    elements.cfgNeutralization.value = "SUBINDUSTRY";
    elements.cfgDecay.value = "0";
    elements.cfgTruncation.value = "0.08";
    elements.cfgCheckCorr.checked = true;
  });

  elements.btnApplySettings.addEventListener("click", () => {
    state.settings.alphaId = elements.cfgAlphaId.value.trim() || "Alpha_01";
    const dVal = parseInt(elements.cfgDelay.value, 10);
    state.settings.delay = isNaN(dVal) ? 1 : dVal;
    state.settings.neutralization = elements.cfgNeutralization.value;
    state.settings.decay = parseInt(elements.cfgDecay.value, 10) || 0;
    state.settings.truncation = parseFloat(elements.cfgTruncation.value) || 0.08;
    state.settings.checkCorr = elements.cfgCheckCorr.checked;

    updateSettingsSummary();
    elements.settingsDialog.close();
    showToast("✔ 仿真参数已更新");
  });
}

// ==============================================================================
// 6. EXAMPLES & CURATED TEMPLATES MODAL
// ==============================================================================
function setupExamplesModal() {
  setupLightDismiss(elements.examplesDialog);

  elements.btnOpenExamples.addEventListener("click", () => {
    renderTemplatesList();
    elements.examplesDialog.showModal();
  });

  elements.btnCloseExamples.addEventListener("click", () => {
    elements.examplesDialog.close();
  });
}

function renderTemplatesList() {
  if (!state.curatedTemplates.length) {
    elements.templateList.innerHTML = `<div style="color:var(--text-dim);padding:20px;text-align:center">正在从本地引擎加载经典因子模板...</div>`;
    return;
  }

  elements.templateList.innerHTML = state.curatedTemplates
    .map(
      (item, idx) => `
    <div class="template-card" data-index="${idx}">
      <div class="template-top">
        <span class="template-cat">${escapeHtml(item.category)}</span>
      </div>
      <div class="template-name">${escapeHtml(item.name)}</div>
      <div class="template-expr">${escapeHtml(item.expr)}</div>
      <div class="template-desc">${escapeHtml(item.expected || "")}</div>
    </div>
  `
    )
    .join("");

  elements.templateList.querySelectorAll(".template-card").forEach((card) => {
    card.addEventListener("click", () => {
      const idx = parseInt(card.getAttribute("data-index"), 10);
      const chosen = state.curatedTemplates[idx];
      elements.codeEditor.value = chosen.expr;
      state.settings.alphaId = `Alpha_${chosen.name.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 20)}`;
      updateLineNumbers();
      updateSettingsSummary();
      elements.examplesDialog.close();
      showToast(`✔ 已载入经典因子: ${chosen.name}`);
    });
  });
}

// ==============================================================================
// 7. SIMULATION EXECUTION & RESULTS RENDERING
// ==============================================================================
function setupSimulation() {
  elements.btnSimulate.addEventListener("click", runSimulation);

  // Commit Alpha to local database
  elements.btnCommitAlpha.addEventListener("click", async () => {
    if (!state.currentResults) {
      showToast("暂无可提交的因子回测数据");
      return;
    }

    elements.btnCommitAlpha.disabled = true;
    try {
      const resp = await fetch("/api/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alpha_id: state.settings.alphaId,
          expression: elements.codeEditor.value.trim(),
        }),
      });
      const data = await resp.json();
      if (data.status === "ok") {
        showToast(`✔ 因子 '${state.settings.alphaId}' 已成功入库`);
      } else {
        showToast(`❌ 入库失败: ${data.message || "未知错误"}`);
      }
    } catch (err) {
      showToast(`❌ 网络请求失败: ${err.message}`);
    } finally {
      elements.btnCommitAlpha.disabled = false;
    }
  });
}

async function runSimulation() {
  const expr = elements.codeEditor.value.trim();
  if (!expr) {
    showToast("请输入有效因子表达式");
    return;
  }

  // Set loading state
  const btn = elements.btnSimulate;
  btn.classList.add("loading");
  btn.querySelector(".sim-spinner").classList.remove("hidden");
  btn.querySelector(".btn-text").textContent = "Simulating...";
  btn.disabled = true;

  const payload = {
    expression: expr,
    delay: state.settings.delay,
    decay: state.settings.decay,
    neutralization: state.settings.neutralization,
    truncation: state.settings.truncation,
    alpha_id: state.settings.alphaId,
    check_corr: state.settings.checkCorr,
  };

  try {
    const t0 = performance.now();
    const resp = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await resp.json();

    if (!resp.ok || result.error) {
      throw new Error(result.error || "回测发生未知错误");
    }

    state.currentResults = result;

    // Render results
    renderResults(result, expr);

    // Switch to results view
    elements.navResults.click();
    showToast(`⚡ 回测完成！耗时: ${result.runtime_ms} ms`);
  } catch (err) {
    console.error("Simulation error:", err);
    showToast(`❌ 回测失败: ${err.message}`, 5000);
  } finally {
    btn.classList.remove("loading");
    btn.querySelector(".sim-spinner").classList.add("hidden");
    btn.querySelector(".btn-text").textContent = "Simulate";
    btn.disabled = false;
  }
}

function renderResults(res, expr) {
  elements.resultAlphaId.textContent = res.alpha_id || state.settings.alphaId;
  elements.resultExpression.textContent = expr;
  elements.resRuntime.textContent = `${res.runtime_ms} ms`;

  // Verdict status badge
  const isPassed = res.is_all_passed;
  elements.resVerdictBadge.textContent = isPassed ? "PASS ALL IS CHECKS" : "MARGINAL / FAILED";
  elements.resVerdictBadge.className = `status-badge ${isPassed ? "pass" : "warn"}`;

  // Sharpe
  elements.resSharpe.textContent = res.sharpe.toFixed(3);
  elements.resSharpe.className = `metric-value ${res.sharpe >= 1.25 ? "good" : res.sharpe >= 1.0 ? "warn" : "bad"}`;

  // Fitness
  elements.resFitness.textContent = res.fitness.toFixed(3);
  elements.resFitness.className = `metric-value ${res.fitness >= 1.0 ? "good" : "bad"}`;

  // Turnover
  const toPct = (res.turnover * 100).toFixed(2);
  elements.resTurnover.textContent = `${toPct}%`;
  elements.resTurnover.className = `metric-value ${res.turnover >= 0.01 && res.turnover <= 0.7 ? "good" : "bad"}`;

  // Annual Returns
  const retPct = (res.returns * 100).toFixed(2);
  elements.resReturns.textContent = `${res.returns >= 0 ? "+" : ""}${retPct}%`;
  elements.resReturns.className = `metric-value ${res.returns > 0.05 ? "good" : "bad"}`;

  // Max Drawdown
  const ddPct = (res.max_drawdown * 100).toFixed(2);
  elements.resDrawdown.textContent = `${ddPct}%`;
  elements.resDrawdown.className = `metric-value ${res.max_drawdown < 0.25 ? "good" : "bad"}`;

  // Margin (bps)
  elements.resMargin.textContent = `${res.margin_bps.toFixed(1)} bps`;
  elements.resMargin.className = `metric-value ${res.margin_bps >= 10 ? "good" : "warn"}`;

  // Sub-Universe Sharpe
  elements.resSubSharpe.textContent = res.sub_universe_sharpe.toFixed(3);
  elements.resSubSharpe.className = `metric-value ${res.sub_universe_sharpe >= 1.0 ? "good" : "bad"}`;

  // Render IS 6-point red line checks
  renderQCChecks(res.is_checks);

  // Render SVG Cumulative PnL chart
  if (res.daily_pnl && res.daily_pnl.length) {
    drawEquityCurve(res.daily_dates, res.daily_pnl);
  }
}

function renderQCChecks(isChecks) {
  const checkNames = {
    LOW_SHARPE: "IS 01: Sharpe 门槛 (≥ 1.25)",
    LOW_FITNESS: "IS 02: Fitness 门槛 (≥ 1.0)",
    TURNOVER: "IS 03: 换手率健康区间 (1% ~ 70%)",
    DRAWDOWN: "IS 04: 最大回撤控制 (< 25%)",
    SUB_UNIVERSE_TOP1000: "IS 05: TOP1000 股票池穿透 (≥ 1.0)",
    SELF_CORRELATION: "IS 06: 因子库自相关性熔断 (< 0.65)",
  };

  const gridHtml = Object.entries(isChecks)
    .map(([key, val]) => {
      const displayName = checkNames[key] || key;
      const isPass = val === "PASS" || val.startsWith("PASS");
      const isWarn = val.startsWith("WARN");
      const statusClass = isPass ? "pass" : isWarn ? "warn" : "fail";
      const icon = isPass ? "✔" : isWarn ? "⚠" : "✖";

      return `
      <div class="qc-item">
        <div class="qc-item-left">
          <span class="qc-icon ${statusClass}">${icon}</span>
          <span>${escapeHtml(displayName)}</span>
        </div>
        <div class="qc-status ${statusClass}">${escapeHtml(val)}</div>
      </div>
    `;
    })
    .join("");

  elements.qcGrid.innerHTML = gridHtml;
}

// ==============================================================================
// 8. INTERACTIVE SVG EQUITY CURVE RENDERER
// ==============================================================================
function drawEquityCurve(dates, dailyPnls) {
  const svg = elements.pnlSvg;
  const container = elements.chartContainer;
  const tooltip = elements.chartTooltip;

  // Compute cumulative PnL series
  let cum = 0;
  const cumSeries = [];
  for (let i = 0; i < dailyPnls.length; i++) {
    cum += dailyPnls[i];
    cumSeries.push(cum);
  }

  const n = cumSeries.length;
  if (n < 2) return;

  const minVal = Math.min(0, ...cumSeries);
  const maxVal = Math.max(0.01, ...cumSeries);
  const range = maxVal - minVal || 1;

  const width = 1000;
  const height = 320;
  const padTop = 30;
  const padBottom = 40;
  const padLeft = 60;
  const padRight = 30;

  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  function getX(index) {
    return padLeft + (index / (n - 1)) * plotW;
  }

  function getY(val) {
    return padTop + (1 - (val - minVal) / range) * plotH;
  }

  // Construct points
  let pathD = `M ${getX(0)} ${getY(cumSeries[0])}`;
  for (let i = 1; i < n; i++) {
    pathD += ` L ${getX(i)} ${getY(cumSeries[i])}`;
  }

  // Area path closing at baseline
  const zeroY = getY(0);
  const areaD = `${pathD} L ${getX(n - 1)} ${zeroY} L ${getX(0)} ${zeroY} Z`;

  // Grid lines
  const gridCount = 5;
  let gridLines = "";
  for (let g = 0; g <= gridCount; g++) {
    const val = minVal + (g / gridCount) * range;
    const y = getY(val);
    gridLines += `
      <line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#1f293d" stroke-dasharray="3,3" />
      <text x="${padLeft - 8}" y="${y + 4}" fill="#5c6880" font-size="11" text-anchor="end" font-family="monospace">${(val * 100).toFixed(1)}%</text>
    `;
  }

  // Date labels
  const dateStep = Math.floor(n / 5);
  let dateLabels = "";
  for (let i = 0; i < n; i += dateStep) {
    const dStr = dates[i] ? String(dates[i]).slice(0, 10) : "";
    const x = getX(i);
    dateLabels += `
      <text x="${x}" y="${height - 12}" fill="#5c6880" font-size="11" text-anchor="middle" font-family="monospace">${dStr}</text>
    `;
  }

  svg.innerHTML = `
    <defs>
      <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#00e5ff" stop-opacity="0.35" />
        <stop offset="100%" stop-color="#2962ff" stop-opacity="0.0" />
      </linearGradient>
    </defs>
    <!-- Grid -->
    ${gridLines}
    ${dateLabels}
    <!-- Zero Baseline -->
    <line x1="${padLeft}" y1="${zeroY}" x2="${width - padRight}" y2="${zeroY}" stroke="#3b4661" stroke-width="1.2" />
    <!-- Area -->
    <path d="${areaD}" fill="url(#pnlGrad)" />
    <!-- Main Line -->
    <path d="${pathD}" fill="none" stroke="#00e5ff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    <!-- Interactive Tracker elements -->
    <line id="hover-line" x1="0" y1="${padTop}" x2="0" y2="${height - padBottom}" stroke="#ffffff" stroke-width="1" stroke-dasharray="2,2" style="display:none" />
    <circle id="hover-circle" r="4" fill="#00e5ff" stroke="#ffffff" stroke-width="2" style="display:none" />
  `;

  // Interactive mouse hover
  const hoverLine = svg.querySelector("#hover-line");
  const hoverCircle = svg.querySelector("#hover-circle");

  svg.onmousemove = (e) => {
    const rect = svg.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * width;

    if (mouseX < padLeft || mouseX > width - padRight) {
      hoverLine.style.display = "none";
      hoverCircle.style.display = "none";
      tooltip.classList.add("hidden");
      return;
    }

    const ratio = (mouseX - padLeft) / plotW;
    const idx = Math.min(n - 1, Math.max(0, Math.round(ratio * (n - 1))));
    const curVal = cumSeries[idx];
    const curDate = dates[idx] ? String(dates[idx]).slice(0, 10) : "";

    const x = getX(idx);
    const y = getY(curVal);

    hoverLine.setAttribute("x1", x);
    hoverLine.setAttribute("x2", x);
    hoverLine.style.display = "block";

    hoverCircle.setAttribute("cx", x);
    hoverCircle.setAttribute("cy", y);
    hoverCircle.style.display = "block";

    // Tooltip position relative to container
    const cRect = container.getBoundingClientRect();
    const ttX = (x / width) * cRect.width;
    const ttY = (y / height) * cRect.height;

    tooltip.style.left = `${ttX}px`;
    tooltip.style.top = `${ttY}px`;
    tooltip.innerHTML = `
      <div><strong>${curDate}</strong></div>
      <div style="color:#00e5ff">PnL: ${(curVal * 100).toFixed(2)}%</div>
    `;
    tooltip.classList.remove("hidden");
  };

  svg.onmouseleave = () => {
    hoverLine.style.display = "none";
    hoverCircle.style.display = "none";
    tooltip.classList.add("hidden");
  };
}

// ==============================================================================
// 9. API DATA FETCHING
// ==============================================================================
async function fetchInitialData() {
  try {
    // 1. Fetch templates
    const resp = await fetch("/api/templates");
    if (resp.ok) {
      const data = await resp.json();
      state.curatedTemplates = data.templates || [];
    }
  } catch (err) {
    console.warn("Could not fetch templates from backend:", err);
  }
}

// Helper: HTML Escaping
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
