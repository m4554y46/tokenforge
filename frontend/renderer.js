const API_BASE = "http://127.0.0.1:8765";

let models = {};
let optimizerModels = {};
let currentVersions = [];
let currentVersionIndex = 0;
let currentPrompt = "";
let currentTargetModel = "gpt-4o";

// ===== INIT =====
document.addEventListener("DOMContentLoaded", async () => {
  await loadModels();
  await loadKeys();
  await loadHistory();
  await loadTemplates();
  loadDocFormats();
  setupNavigation();
  setupLiveTokenCounting();
  checkBackendStatus();
  setInterval(checkBackendStatus, 10000);
});

async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const config = { headers, ...options };
  const resp = await fetch(url, config);
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(err || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ===== BACKEND STATUS =====
async function checkBackendStatus() {
  try {
    await api("/api/health");
    document.getElementById("statusDot").className = "status-dot ready";
    document.getElementById("statusText").textContent = "Backend prêt";
    checkLlmStatus();
  } catch {
    document.getElementById("statusDot").className = "status-dot error";
    document.getElementById("statusText").textContent = "Backend indisponible";
  }
}

async function checkLlmStatus() {
  try {
    const data = await api("/api/llm/status");
    const hint = document.getElementById("llmStatusHint");
    if (data.available) {
      hint.textContent = "\u2705 LLM disponible";
      hint.style.color = "var(--accent-green)";
    } else {
      hint.textContent = "\u26A0\uFE0F Aucun LLM local (optionnel)";
      hint.style.color = "var(--text-muted)";
    }
  } catch {
    // ignore
  }
}

// ===== NAVIGATION =====
function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      item.classList.add("active");
      const view = item.dataset.view;
      document.getElementById(`view-${view}`).classList.add("active");
      const titles = {
        optimizer: ["Optimizer", "Optimisez vos prompts et réduisez vos coûts"],
        documents: ["Documents", "Analysez et compressez vos documents"],
        history: ["Historique", "Retrouvez toutes vos optimisations"],
        keys: ["API Keys", "Gérez vos clés d'API pour l'optimisation"],
        templates: ["Templates", "Templates prêts à l'emploi"],
        admin: ["Admin", "Administration du service"],
      };
      const [title, subtitle] = titles[view] || ["", ""];
      document.getElementById("viewTitle").textContent = title;
      document.getElementById("viewSubtitle").textContent = subtitle;
    });
  });
}

// ===== MODELS =====
async function loadModels() {
  try {
    const data = await api("/api/models");
    models = data.models;
    optimizerModels = data.optimizer_models;
    populateModelSelect("targetModel", data.models);
    document.getElementById("optimizerProvider").value = "";
  } catch (err) {
    console.error("Failed to load models:", err);
  }
}

function populateModelSelect(id, modelData) {
  const select = document.getElementById(id);
  select.innerHTML = "";
  const families = {};
  for (const [key, val] of Object.entries(modelData)) {
    if (!families[val.family]) families[val.family] = [];
    families[val.family].push({ id: key, ...val });
  }
  for (const [family, items] of Object.entries(families)) {
    const group = document.createElement("optgroup");
    group.label = family;
    items.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = `${item.id} — $${item.input_price_per_1k}/1K in`;
      group.appendChild(opt);
    });
    select.appendChild(group);
  }
  select.value = "gpt-4o";
}

function onOptimizerChange() {
  const provider = document.getElementById("optimizerProvider").value;
  const modelGroup = document.getElementById("optimizerModelGroup");
  const keySection = document.getElementById("keySection");
  const modelSelect = document.getElementById("optimizerModel");

  if (!provider) {
    modelGroup.style.display = "none";
    keySection.style.display = "none";
    return;
  }

  modelGroup.style.display = "block";
  keySection.style.display = "flex";

  modelSelect.innerHTML = "";
  const providerModels = optimizerModels[provider]?.models || [];
  providerModels.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    modelSelect.appendChild(opt);
  });
  if (providerModels.length > 0) modelSelect.value = providerModels[0];

  updateKeyStatus(provider);
}

function updateKeyStatus(provider) {
  const icon = document.getElementById("keyStatusIcon");
  const text = document.getElementById("keyStatusText");
  const display = document.getElementById(`keyDisplay-${provider}`);
  if (display && display.textContent.trim() !== `${provider === "google" ? "AIza" : provider === "anthropic" ? "sk-ant-" : "sk-"}****`) {
    icon.textContent = "\u2705";
    text.textContent = `Clé ${provider} configurée`;
  } else {
    icon.textContent = "\u{1F512}";
    text.textContent = `Clé ${provider} non configurée`;
  }
}

let keyModalCallback = null;

function showKeyModal() {
  const provider = document.getElementById("optimizerProvider").value;
  if (!provider) return;
  document.getElementById("keyModalProvider").textContent = `Fournisseur: ${provider}`;
  document.getElementById("keyModalInput").value = "";
  document.getElementById("keyModal").classList.add("active");
  document.getElementById("keyModalInput").focus();
  keyModalCallback = async (key) => {
    await saveKey(provider, key);
  };
}

function closeKeyModal() {
  document.getElementById("keyModal").classList.remove("active");
  keyModalCallback = null;
  document.getElementById("keyModalInput").blur();
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const keyModal = document.getElementById("keyModal");
    const templateModal = document.getElementById("templateModal");
    if (keyModal.classList.contains("active")) closeKeyModal();
    if (templateModal.classList.contains("active")) closeTemplateModal();
  }
});

async function saveKeyFromModal() {
  const key = document.getElementById("keyModalInput").value.trim();
  if (!key || !keyModalCallback) return;
  await keyModalCallback(key);
  closeKeyModal();
}

// ===== PROMPT INPUT =====
function onPromptChange() {
  updateTokenCount();
}

function clearPrompt() {
  document.getElementById("promptInput").value = "";
  updateTokenCount();
  document.getElementById("resultsPlaceholder").style.display = "flex";
  document.getElementById("resultsContent").style.display = "none";
}

async function updateTokenCount() {
  const text = document.getElementById("promptInput").value;
  const model = document.getElementById("targetModel").value;
  currentPrompt = text;
  currentTargetModel = model;

  try {
    const data = await api("/api/count-tokens", {
      method: "POST",
      body: JSON.stringify({ text, model }),
    });
    document.getElementById("liveTokens").textContent = data.tokens.toLocaleString();
    document.getElementById("tokenBadge").textContent = `${data.tokens} tokens`;

    const modelInfo = models[model];
    if (modelInfo) {
      const cost = ((data.tokens / 1000) * modelInfo.input_price_per_1k);
      document.getElementById("liveCost").textContent = `$${cost.toFixed(6)}`;
      document.getElementById("liveContext").textContent = `${(modelInfo.context_window / 1000).toFixed(0)}K`;
    }
  } catch {}
}

function setupLiveTokenCounting() {
  let debounceTimer;
  document.getElementById("promptInput").addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(updateTokenCount, 300);
  });
  document.getElementById("targetModel").addEventListener("change", updateTokenCount);
}

// ===== TEMPLATES =====
async function loadTemplates() {
  try {
    const data = await api("/api/templates");
    const grid = document.getElementById("templatesGrid");
    const select = document.getElementById("templateSelect");

    select.innerHTML = '<option value="">-- Charger un template --</option>';

    if (data.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">&#128203;</div>
          <h3>Aucun template</h3>
          <p>Créez des templates pour réutiliser vos prompts.</p>
        </div>`;
      return;
    }

    grid.innerHTML = "";
    data.forEach((t) => {
      const div = document.createElement("div");
      div.className = "template-card";
      div.dataset.id = t.id;
      div.innerHTML = `
        <h4>${escapeHtml(t.name)}</h4>
        <div class="template-preview">${escapeHtml(t.content.substring(0, 120))}</div>
        <div class="template-category">${escapeHtml(t.category)}</div>
        <div style="margin-top:8px;">
          <button class="btn btn-secondary btn-sm use-template-btn" data-tooltip="Charge ce template dans l'éditeur de l'Optimizer">Utiliser</button>
          <button class="btn btn-danger btn-sm del-template-btn" data-id="${t.id}" data-tooltip="Supprime ce template définitivement">X</button>
        </div>`;
      grid.appendChild(div);

      div.querySelector(".use-template-btn").addEventListener("click", async () => {
        try {
          const dataAll = await api("/api/templates");
          const found = dataAll.find((x) => String(x.id) === String(t.id));
          if (found) {
            document.getElementById("promptInput").value = found.content;
            updateTokenCount();
            document.querySelector('[data-view="optimizer"]').click();
            showToast("Template chargé", "info");
          }
        } catch {}
      });

      div.querySelector(".del-template-btn").addEventListener("click", async () => {
        await deleteTemplate(t.id);
      });

      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      select.appendChild(opt);
    });
  } catch {}
}

function loadTemplate() {
  const select = document.getElementById("templateSelect");
  const val = select.value;
  if (!val) return;
  fetchAndUseTemplate(val);
}

async function fetchAndUseTemplate(id) {
  try {
    const data = await api("/api/templates");
    const tmpl = data.find((t) => String(t.id) === String(id));
    if (tmpl) {
      document.getElementById("promptInput").value = tmpl.content;
      document.getElementById("templateSelect").value = id;
      updateTokenCount();
      document.querySelector('[data-view="optimizer"]').click();
    }
  } catch {}
}

function showAddTemplateModal() {
  document.getElementById("templateNameInput").value = "";
  document.getElementById("templateContentInput").value = "";
  document.getElementById("templateCategoryInput").value = "general";
  document.getElementById("templateModal").classList.add("active");
  document.getElementById("templateNameInput").focus();
}

function closeTemplateModal() {
  document.getElementById("templateModal").classList.remove("active");
}

async function saveTemplate() {
  const name = document.getElementById("templateNameInput").value.trim();
  const content = document.getElementById("templateContentInput").value.trim();
  const category = document.getElementById("templateCategoryInput").value;
  if (!name || !content) {
    showToast("Veuillez remplir tous les champs", "error");
    return;
  }
  try {
    await api("/api/templates", {
      method: "POST",
      body: JSON.stringify({ name, category, content }),
    });
    closeTemplateModal();
    showToast("Template créé", "success");
    await loadTemplates();
  } catch (err) {
    showToast("Erreur: " + err.message, "error");
  }
}

async function deleteTemplate(id) {
  try {
    await api(`/api/templates/${id}`, { method: "DELETE" });
    showToast("Template supprimé", "info");
    await loadTemplates();
  } catch {}
}

// ===== OPTIMIZER =====
const _PHASE_LABELS = {
  "queued": "En attente",
  "counting": "Analyse du prompt",
  "sanctuary": "Extraction des blocs protégés",
  "language": "Détection de langue",
  "parsing": "Découpage et filtrage",
  "classification": "Classification des phrases",
  "category": "Détection de catégorie",
  "light": "Compression Light",
  "balanced": "Compression Balanced",
  "spc_base": "Protection sémantique SPC",
  "aggressive": "Compression Aggressive",
  "max_industrial": "Compression Max & Industrial",
  "saving": "Enregistrement",
  "complete": "Terminé",
};

async function optimize() {
  const prompt = document.getElementById("promptInput").value.trim();
  if (!prompt) {
    showToast("Veuillez entrer un prompt", "error");
    return;
  }

  const targetModel = document.getElementById("targetModel").value;
  const provider = document.getElementById("optimizerProvider").value;
  const optimizerModel = document.getElementById("optimizerModel").value;
  const category = document.getElementById("categorySelect").value;

  const btn = document.getElementById("optimizeBtn");
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Optimisation...';
  document.getElementById("loadingOverlay").classList.add("active");
  document.getElementById("resultsPlaceholder").style.display = "none";

  // Reset progress bar
  document.getElementById("progressFill").style.width = "0%";
  document.getElementById("progressPct").textContent = "0%";
  document.getElementById("progressPhase").textContent = "Démarrage...";
  document.getElementById("progressEta").textContent = "";

  try {
    // Start async optimization
    const { session_id } = await api("/api/optimize", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        target_model: targetModel,
        optimizer_provider: provider || null,
        optimizer_model: optimizerModel || null,
        category: category || null,
        refine_with_llm: document.getElementById("refineLlmToggle")?.checked || false,
      }),
    });

    // Poll progress
    let done = false;
    let startTime = Date.now();
    while (!done) {
      await new Promise(r => setTimeout(r, 400));
      const prog = await api(`/api/progress/${session_id}`);

      const pct = prog.progress || 0;
      const phase = prog.phase || "";
      document.getElementById("progressFill").style.width = Math.min(pct, 100) + "%";
      document.getElementById("progressPct").textContent = pct + "%";
      document.getElementById("progressPhase").textContent =
        _PHASE_LABELS[phase] || phase || "Optimisation...";

      // ETA
      if (pct > 0 && pct < 100) {
        const elapsed = (Date.now() - startTime) / 1000;
        const eta = Math.round((elapsed / pct) * (100 - pct));
        document.getElementById("progressEta").textContent =
          eta > 0 ? `~${eta}s restantes` : "";
      }

      if (pct >= 100) {
        done = true;
        const data = prog.result;
        if (!data) throw new Error("Aucun résultat retourné");

        currentVersions = data.versions || [];
        currentVersionIndex = 0;
        renderVersions();
        renderVersionDetail(0);

        const src = data.source || "fallback";
        const srcLabel = src === "api" ? "API" : "Local";
        const srcColor = src === "api" ? "var(--accent-green)" : "var(--text-muted)";
        const catLabel = data.category
          ? data.category.charAt(0).toUpperCase() + data.category.slice(1)
          : "";
        document.getElementById("resultBadge").innerHTML =
          `${data.original_tokens} tokens · <span style="color:${srcColor}">${srcLabel}</span>` +
          (catLabel ? ` · <span style="color:var(--accent-blue)">${escapeHtml(catLabel)}</span>` : "");

        document.getElementById("resultsContent").style.display = "block";

        showToast(
          `Optimisation terminée! Économie jusqu'à ${currentVersions[0]?.savings_percent || 0}%`,
          "success"
        );

        await loadHistory();
      } else if (pct < 0) {
        throw new Error(prog.error || "Erreur lors de l'optimisation");
      }
    }
  } catch (err) {
    showToast("Erreur: " + err.message, "error");
    document.getElementById("resultsPlaceholder").style.display = "flex";
    document.getElementById("resultsContent").style.display = "none";
  }

  btn.disabled = false;
  btn.innerHTML = "\u26A1 Optimiser";
  document.getElementById("loadingOverlay").classList.remove("active");
}

function renderVersions() {
  const pills = document.getElementById("versionPills");
  pills.innerHTML = "";
  currentVersions.forEach((v, i) => {
    const pill = document.createElement("button");
    pill.className = `pill ${i === currentVersionIndex ? "active" : ""}`;
    const badgeClass = v.label?.toLowerCase() || "";
    pill.innerHTML = `${escapeHtml(v.label || "")} (-${v.savings_percent || 0}%)`;
    pill.setAttribute("data-tooltip", `Version ${v.label || ""} — économie de ${v.savings_percent || 0}%. Cliquez pour voir les détails.`);
    pill.onclick = () => {
      currentVersionIndex = i;
      document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      renderVersionDetail(i);
    };
    if (i === 1) {
      // Mark balanced as "popular"
      pill.style.borderColor = "var(--accent-green)";
    }
    pills.appendChild(pill);
  });
}

function renderVersionDetail(index) {
  const v = currentVersions[index];
  if (!v) return;

  const detail = document.getElementById("versionDetail");
  const badgeClass = (v.label || "").toLowerCase();
  const changes = v.changes_made || [];

  detail.innerHTML = `
    <div class="version-card ${index === 1 ? "popular" : ""}">
      <div class="version-header">
        <span class="version-badge ${badgeClass}">${v.label}</span>
        ${index === 1 ? '<span class="version-badge popular-tag">POPULAIRE</span>' : ""}
        ${document.getElementById("refineLlmToggle")?.checked ? '<span class="version-badge llm-tag">LLM</span>' : ""}
      </div>
      <div class="version-description">${escapeHtml(v.description || "")}</div>
      <div class="version-prompt">${escapeHtml(v.prompt || "")}</div>
      <div class="version-stats">
        <div class="stat-item">
          <span class="stat-label">Tokens</span>
          <span class="stat-value tokens">${(v.optimized_tokens || 0).toLocaleString()}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Économie</span>
          <span class="stat-value savings">-${v.savings_percent || 0}% (${v.savings_tokens || 0} tokens)</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Coût estimé</span>
          <span class="stat-value cost">$${(v.optimized_cost || 0).toFixed(6)}</span>
        </div>
      </div>
      <div class="version-changes">
        ${changes.map((c) => `<span class="change-tag">${escapeHtml(c.description || c)}</span>`).join("")}
      </div>
      <div class="version-actions">
        <button class="btn btn-primary btn-sm" onclick="copyVersion(${index})" data-tooltip="Copie le texte optimisé dans le presse-papier">Copier</button>
        <button class="btn btn-secondary btn-sm" onclick="useVersion(${index})" data-tooltip="Remplace le prompt de l'éditeur par cette version">Utiliser cette version</button>
      </div>
    </div>
  `;

  // Auto-show cost comparison for this version
  const origText = currentPrompt || v.prompt || "";
  const optText = v.prompt || "";
  const costEl = document.getElementById("costComparison");
  if (costEl) renderCostComparison(origText, optText, costEl);
}

function copyVersion(index) {
  const text = currentVersions[index]?.prompt || "";
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copié dans le presse-papier!", "success");
  });
}

function useVersion(index) {
  const text = currentVersions[index]?.prompt || "";
  document.getElementById("promptInput").value = text;
  updateTokenCount();
  showToast("Version chargée dans l'éditeur", "info");
}

// ===== KEYS =====
async function loadKeys() {
  try {
    const data = await api("/api/keys");
    data.forEach((k) => {
      const display = document.getElementById(`keyDisplay-${k.provider}`);
      const status = document.getElementById(`keyStatus-${k.provider}`);
      if (display) display.textContent = k.key_masked;
      if (status) {
        status.textContent = k.key_masked !== "****" ? "Configuré" : "Non configuré";
        status.className = `key-status ${k.key_masked !== "****" ? "configured" : "missing"}`;
      }
    });
  } catch (err) { console.warn("Failed to load keys:", err); }
}

async function saveKey(provider, keyValue) {
  const key = keyValue || document.getElementById(`keyInput-${provider}`)?.value?.trim();
  if (!key) {
    showToast("Veuillez entrer une clé", "error");
    return;
  }
  try {
    await api("/api/keys", {
      method: "POST",
      body: JSON.stringify({ provider, key }),
    });
    document.getElementById(`keyInput-${provider}`).value = "";
    showToast(`Clé ${provider} sauvegardée`, "success");
    await loadKeys();
    updateKeyStatus(provider);
  } catch (err) {
    showToast("Erreur: " + err.message, "error");
  }
}

async function deleteKey(provider) {
  try {
    await api(`/api/keys/${provider}`, { method: "DELETE" });
    showToast(`Clé ${provider} supprimée`, "info");
    await loadKeys();
    updateKeyStatus(provider);
  } catch (err) { console.warn("Failed to delete key:", err); }
}

// ===== COST COMPARISON (merged from Simulator) =====
async function renderCostComparison(originalText, optimizedText, targetEl) {
  if (!originalText && !optimizedText) return;
  const allModelIds = Object.keys(models);

  async function getCosts(text) {
    if (!text) return null;
    const data = await api("/api/simulate-cost", {
      method: "POST",
      body: JSON.stringify({ prompt: text, models: allModelIds }),
    });
    return data.results || [];
  }

  try {
    const [origResults, optResults] = await Promise.all([
      getCosts(originalText),
      getCosts(optimizedText),
    ]);

    const modelIds = origResults ? origResults.map((r) => r.model) : optResults ? optResults.map((r) => r.model) : [];

    let html = `<div class="card" data-tooltip="Comparaison des coûts entre le prompt original et l'optimisé, pour tous les modèles disponibles."><h3 style="margin-bottom:16px;">&#36; Comparaison des coûts sur tous les modèles</h3>
      <table class="model-cost-table">
        <thead><tr>
          <th>Modèle</th>
          <th>Original</th>
          ${optResults ? "<th>Optimisé</th>" : ""}
          ${optResults ? "<th>Économie</th>" : ""}
        </tr></thead>
        <tbody>`;

    modelIds.forEach((modelId) => {
      const orig = origResults ? origResults.find((r) => r.model === modelId) : null;
      const opt = optResults ? optResults.find((r) => r.model === modelId) : null;
      const origCost = orig ? orig.cost : 0;
      const optCost = opt ? opt.cost : 0;
      const savings = origCost - optCost;
      const savingsPct = origCost > 0 ? ((savings / origCost) * 100).toFixed(1) : "-";
      const costClass = (c) => (c < 0.001 ? "low" : c < 0.01 ? "medium" : "high");

      html += `<tr>
        <td>${escapeHtml(modelId)}</td>
        <td class="cost-value ${costClass(origCost)}">${orig ? "$" + orig.cost.toFixed(6) : "-"}</td>
        ${opt ? `<td class="cost-value ${costClass(optCost)}">$${opt.cost.toFixed(6)}</td>` : ""}
        ${opt ? `<td class="cost-value" style="color:${savings >= 0 ? "var(--accent-green)" : "var(--accent-red)"}">${savings >= 0 ? "-" : "+"}$${Math.abs(savings).toFixed(6)} (${savingsPct}%)</td>` : ""}
      </tr>`;
    });

    const origTokens = origResults ? origResults[0]?.input_tokens || 0 : 0;
    const optTokens = optResults ? optResults[0]?.input_tokens || 0 : 0;
    if (origTokens || optTokens) {
      html += `<tr style="border-top:2px solid var(--border-light);font-weight:600;">
        <td>Tokens</td>
        <td>${origTokens.toLocaleString()}</td>
        ${optResults ? `<td>${optTokens.toLocaleString()}</td>` : ""}
        ${optResults ? `<td style="color:${optTokens < origTokens ? "var(--accent-green)" : "var(--accent-red)"}">${origTokens - optTokens > 0 ? "-" : "+"}${Math.abs(origTokens - optTokens).toLocaleString()} (${origTokens > 0 ? ((origTokens - optTokens) / origTokens * 100).toFixed(1) : 0}%)</td>` : ""}
      </tr>`;
    }

    html += "</tbody></table></div>";
    targetEl.innerHTML = html;
  } catch (err) {
    targetEl.innerHTML = `<div class="card" style="color:var(--text-muted);text-align:center;">Comparaison des coûts indisponible</div>`;
    console.warn("Cost comparison failed:", err);
  }
}

// ===== HISTORY =====
async function loadHistory() {
  try {
    const data = await api("/api/history?limit=50");
    const list = document.getElementById("historyList");
    if (data.length === 0) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">&#128337;</div>
          <h3>Aucun historique</h3>
          <p>Les prompts optimisés apparaîtront ici automatiquement.</p>
        </div>`;
      return;
    }

    list.innerHTML = data.map((h) => `
      <div class="history-item" data-id="${h.id}" data-optimized="${escapeHtml(h.optimized_prompt)}">
        <div class="history-item-content">
          <div class="history-item-header">
            <strong>${escapeHtml(h.version)}</strong>
            <span class="h-version">${escapeHtml(h.target_model)}</span>
            <span class="history-savings">-${h.savings_percent}%</span>
          </div>
          <div class="history-preview">${escapeHtml(h.original_prompt.substring(0, 100))}</div>
          <div class="history-meta">
            <span>${new Date(h.created_at).toLocaleDateString()}</span>
            <span>${h.original_tokens} → ${h.optimized_tokens} tokens</span>
            <span>Optimisé par: ${escapeHtml(h.optimizer_model)}</span>
          </div>
        </div>
        <div class="history-item-actions">
          <button class="btn btn-secondary btn-sm history-load-btn" data-optimized="${escapeHtml(h.optimized_prompt)}" data-tooltip="Charge le résultat optimisé dans l'éditeur">Charger</button>
          <button class="btn btn-danger btn-sm history-del-btn" data-id="${h.id}" data-tooltip="Supprime cette entrée de l'historique">X</button>
        </div>
      </div>
    `).join("");

    list.querySelectorAll(".history-load-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.getElementById("promptInput").value = btn.dataset.optimized;
        updateTokenCount();
        document.querySelector('[data-view="optimizer"]').click();
        showToast("Prompt chargé depuis l'historique", "info");
      });
    });

    list.querySelectorAll(".history-del-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await deleteHistoryEntry(parseInt(btn.dataset.id));
      });
    });

  } catch {}
}

async function deleteHistoryEntry(id) {
  try {
    await api(`/api/history/${id}`, { method: "DELETE" });
    showToast("Entrée supprimée", "info");
    await loadHistory();
  } catch {}
}

async function clearHistory() {
  try {
    const data = await api("/api/history?limit=1000");
    for (const h of data) {
      await api(`/api/history/${h.id}`, { method: "DELETE" });
    }
    showToast("Historique effacé", "info");
    await loadHistory();
  } catch {}
}

function saveCurrentPromptAsTemplate() {
  const prompt = document.getElementById("promptInput").value.trim();
  if (!prompt) {
    showToast("Le champ prompt est vide", "error");
    return;
  }
  document.getElementById("templateNameInput").value = "";
  document.getElementById("templateContentInput").value = prompt;
  document.getElementById("templateCategoryInput").value = "general";
  document.getElementById("templateModal").classList.add("active");
}

// ===== TOASTS =====
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ===== UTILS =====
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ===== ADMIN =====
async function restartBackend() {
  const btn = document.getElementById("btnRestart");
  const status = document.getElementById("restartStatus");
  const msg = document.getElementById("restartMsg");
  btn.disabled = true;
  btn.textContent = "\u23F3 Red\u00E9marrage...";
  status.style.display = "block";
  msg.textContent = "Red\u00E9marrage du service...";
  adminLog("info", "Red\u00E9marrage initi\u00E9...");

  try {
    await api("/api/restart", { method: "POST" });
    adminLog("info", "API a r\u00E9pondu, attente du retour...");
  } catch {
    adminLog("info", "API d\u00E9connect\u00E9e, attente du retour...");
  }

  msg.textContent = "Attente du red\u00E9marrage...";
  let attempts = 0;
  const poll = setInterval(async () => {
    attempts++;
    try {
      const r = await fetch(`${API_BASE}/api/health`);
      if (r.ok) {
        clearInterval(poll);
        adminLog("success", "Service red\u00E9marr\u00E9 !");
        msg.textContent = "\u2705 Red\u00E9marrage r\u00E9ussi";
        btn.textContent = "\u21BA RESTART \u2014 Red\u00E9marrer le service";
        btn.disabled = false;
        setTimeout(() => { status.style.display = "none"; }, 3000);
      }
    } catch {
      if (attempts > 30) {
        clearInterval(poll);
        adminLog("error", "Le service n\u2019a pas red\u00E9marr\u00E9");
        msg.textContent = "\u274C \u00C9chec du red\u00E9marrage";
        btn.textContent = "\u21BA RESTART \u2014 Red\u00E9marrer le service";
        btn.disabled = false;
      }
    }
  }, 1000);
}

function adminLog(level, text) {
  const area = document.getElementById("adminLog");
  if (!area) return;
  const line = document.createElement("div");
  const ts = new Date().toLocaleTimeString();
  const colors = { info: "#88ccff", success: "#66ff88", error: "#ff6666" };
  line.innerHTML = `<span style="color:${colors[level] || '#888'}">[${ts}] ${text}</span>`;
  area.appendChild(line);
  area.scrollTop = area.scrollHeight;
}

// ===== DASHBOARD =====
async function loadDashboard() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) throw new Error("Stats unavailable");
    const stats = await res.json();

    document.getElementById("kpiTotal").textContent = stats.total_optimizations || 0;
    document.getElementById("kpiTokens").textContent = (stats.total_tokens_saved || 0).toLocaleString();
    document.getElementById("kpiAvg").textContent = (stats.avg_savings_percent || 0) + "%";

    // Today count
    const today = new Date().toISOString().slice(0, 10);
    const todayCount = (stats.last_7_days || []).filter(d => d.day === today).reduce((s, d) => s + d.count, 0);
    document.getElementById("kpiToday").textContent = todayCount || 0;

    // 7-day chart
    renderChart(stats.last_7_days || []);

    // Mode breakdown
    renderModeBreakdown(stats.by_mode || []);

    // Recent list
    renderRecent(stats.recent || []);
  } catch (e) {
    console.warn("Dashboard load failed:", e);
  }
}

function renderChart(days) {
  const container = document.getElementById("chart7d");
  if (!days.length) {
    container.innerHTML = '<div style="color:var(--text-muted);font-size:13px;width:100%;text-align:center;">Aucune donnée</div>';
    return;
  }
  const max = Math.max(...days.map(d => d.count), 1);
  container.innerHTML = days.map(d => {
    const h = Math.max((d.count / max) * 140, 4);
    const pct = d.avg_savings || 0;
    const label = d.day.slice(5);
    return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;">
      <div class="bar" style="height:${h}px;background:rgba(0,230,118,${0.4 + (d.count/max)*0.6});" title="${d.count} opt. (${pct}% moy.)" data-tooltip="${d.count} optimisations le ${d.day} (moy. ${pct}% d'économie)"></div>
      <div class="bar-label">${label}</div>
    </div>`;
  }).join("");
}

function renderModeBreakdown(modes) {
  const container = document.getElementById("modeBreakdown");
  if (!modes.length) {
    container.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:8px;">Aucune donnée</div>';
    return;
  }
  const total = modes.reduce((s, m) => s + m.count, 0);
  const colors = { Light: "#818cf8", Balanced: "#fbbf24", Agressive: "#ef4444" };
  container.innerHTML = modes.map(m => {
    const pct = total > 0 ? Math.round((m.count / total) * 100) : 0;
    return `<div class="mode-item" data-tooltip="Mode ${m.version} : ${m.count} utilisations, économie moyenne ${m.avg_savings || 0}%">
      <div><span class="mode-dot" style="background:${colors[m.version] || '#888'}"></span><span class="mode-name">${m.version}</span></div>
      <div><span class="mode-pct">${m.avg_savings || 0}%</span> <span class="mode-count">(${m.count} / ${pct}%)</span></div>
    </div>`;
  }).join("");
}

function renderRecent(items) {
  const container = document.getElementById("recentList");
  if (!items.length) {
    container.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:8px;">Aucune optimisation</div>';
    return;
  }
  container.innerHTML = items.map(i => {
    const modeClass = (i.version || "").toLowerCase();
    const preview = (i.original_preview || "").slice(0, 50);
    return `<div class="recent-item" onclick="document.getElementById('view-optimizer').click();">
      <span class="recent-mode ${modeClass}">${i.version || "?"}</span>
      <span class="recent-text">${preview}...</span>
      <span class="recent-savings">${i.savings_percent || 0}%</span>
    </div>`;
  }).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      setTimeout(() => {
        if (item.dataset.view === "admin") loadDashboard();
        if (item.dataset.view === "history") loadHistory();
      }, 100);
    });
  });
});

// ===== DOCUMENTS =====
let _currentDocData = null;

async function loadDocFormats() {
  try {
    const data = await api("/api/document/formats");
    const badge = document.getElementById("docFormatsBadge");
    if (badge) badge.textContent = (data.formats || []).length + " formats";
  } catch (_) { console.warn("Failed to load document formats", _); }
}

function onDocDrop(e) {
  e.preventDefault();
  document.getElementById("docDropzone").classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) uploadDoc(file);
}

function onDocFileSelect() {
  const file = document.getElementById("docFileInput").files[0];
  if (file) uploadDoc(file);
}

async function uploadDoc(file) {
  const MAX_MB = 50;
  if (file.size > MAX_MB * 1024 * 1024) {
    showToast("Fichier trop volumineux (max " + MAX_MB + "MB)", "error");
    return;
  }

  document.getElementById("docUploadProgress").style.display = "block";
  document.getElementById("docDropzone").style.display = "none";
  document.getElementById("docResults").style.display = "none";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const data = await api("/api/document/compress", {
      method: "POST",
      body: formData,
    });

    _currentDocData = data;

    document.getElementById("docFormat").textContent = (data.format || "?").toUpperCase();
    document.getElementById("docRegister").textContent = data.category || data.register || "?";
    document.getElementById("docSize").textContent = formatFileSize(file.size);
    document.getElementById("docTokens").textContent = (data.original_tokens || 0).toLocaleString();
    document.getElementById("docSections").textContent = data.sections || "?";
    document.getElementById("docTables").textContent = data.tables || "0";

    document.getElementById("docOrigTokens").textContent = (data.original_tokens || 0).toLocaleString();
    document.getElementById("docCompTokens").textContent = (data.compressed_tokens || 0).toLocaleString();
    document.getElementById("docSavingsPct").textContent = "-" + (data.savings_percent || 0) + "%";

    document.getElementById("docOriginalPreview").textContent = data.original_text || data.preview_original || "";
    document.getElementById("docCompressedPreview").textContent = data.compressed_text || data.preview_compressed || "";

    document.getElementById("docResults").style.display = "block";
    document.getElementById("docCompressResults").style.display = "block";
    showToast("Document analysé et compressé avec succès", "success");
  } catch (err) {
    showToast("Erreur: " + err.message, "error");
    document.getElementById("docDropzone").style.display = "block";
  }

  document.getElementById("docUploadProgress").style.display = "none";
}

async function compressDoc() {
  const fileInput = document.getElementById("docFileInput");
  if (!fileInput.files[0]) {
    showToast("Veuillez d'abord importer un document", "error");
    return;
  }

  const mode = document.getElementById("docCompressMode").value;
  const category = document.getElementById("docCategory").value;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("mode", mode);
  if (category) formData.append("category", category);

  // Show progress
  document.getElementById("loadingOverlay").classList.add("active");
  document.getElementById("progressFill").style.width = "0%";
  document.getElementById("progressPct").textContent = "0%";
  document.getElementById("progressPhase").textContent = "Compression du document...";
  document.getElementById("progressEta").textContent = "";

  try {
    const { session_id } = await api("/api/document/compress", {
      method: "POST",
      body: formData,
    });

    let done = false;
    const startTime = Date.now();
    while (!done) {
      await new Promise(r => setTimeout(r, 400));
      const prog = await api(`/api/document/progress/${session_id}`);

      const pct = prog.progress || 0;
      const phase = prog.phase || "";
      document.getElementById("progressFill").style.width = Math.min(pct, 100) + "%";
      document.getElementById("progressPct").textContent = pct + "%";
      const labels = { queued: "En attente", parsing: "Analyse du document", compressing: "Compression en cours", finalizing: "Finalisation", complete: "Terminé", error: "Erreur" };
      document.getElementById("progressPhase").textContent = labels[phase] || phase || "Compression...";

      if (pct > 0 && pct < 100) {
        const elapsed = (Date.now() - startTime) / 1000;
        const eta = Math.round((elapsed / pct) * (100 - pct));
        document.getElementById("progressEta").textContent = eta > 0 ? `~${eta}s restantes` : "";
      }

      if (pct >= 100) {
        done = true;
        const data = prog.result;
        if (!data) throw new Error("Aucun résultat");

        _currentDocData = data;
        document.getElementById("docOrigTokens").textContent = (data.original_tokens || 0).toLocaleString();
        document.getElementById("docCompTokens").textContent = (data.compressed_tokens || 0).toLocaleString();
        document.getElementById("docSavingsPct").textContent = "-" + (data.savings_percent || 0) + "%";
        document.getElementById("docCompressedPreview").textContent = data.compressed_text || data.preview_compressed || "";
        document.getElementById("docRegister").textContent = data.category || data.register || "?";
        document.getElementById("docTokens").textContent = (data.original_tokens || 0).toLocaleString();
        document.getElementById("docCompressResults").style.display = "block";
        showToast("Re-compression effectuée: -" + (data.savings_percent || 0) + "%", "success");
      } else if (pct < 0) {
        throw new Error(prog.error || "Erreur de compression");
      }
    }
  } catch (err) {
    showToast("Erreur: " + err.message, "error");
  }

  document.getElementById("loadingOverlay").classList.remove("active");
}

function copyDocCompressed() {
  const text = _currentDocData?.compressed_text || _currentDocData?.preview_compressed || "";
  if (!text) { showToast("Aucun texte compressé disponible", "error"); return; }
  navigator.clipboard.writeText(text).then(() => {
    showToast("Texte compressé copié !", "success");
  });
}

function sendDocToOptimizer() {
  const text = _currentDocData?.compressed_text || _currentDocData?.preview_compressed || "";
  if (!text) { showToast("Aucun texte compressé disponible", "error"); return; }
  document.getElementById("promptInput").value = text;
  document.querySelector('[data-view="optimizer"]').click();
  updateTokenCount();
  showToast("Texte chargé dans l'optimiseur", "info");
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " o";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " Ko";
  return (bytes / (1024 * 1024)).toFixed(1) + " Mo";
}

// ===== END DOCUMENTS =====

// Expose functions globally
window.optimize = optimize;
window.clearPrompt = clearPrompt;
window.onOptimizerChange = onOptimizerChange;
window.showKeyModal = showKeyModal;
window.closeKeyModal = closeKeyModal;
window.saveKeyFromModal = saveKeyFromModal;
window.saveKey = saveKey;
window.deleteKey = deleteKey;
window.copyVersion = copyVersion;
window.useVersion = useVersion;
window.onPromptChange = onPromptChange;
window.loadTemplate = loadTemplate;
window.showAddTemplateModal = showAddTemplateModal;
window.closeTemplateModal = closeTemplateModal;
window.saveTemplate = saveTemplate;
window.deleteTemplate = deleteTemplate;
window.saveCurrentPromptAsTemplate = saveCurrentPromptAsTemplate;
window.deleteHistoryEntry = deleteHistoryEntry;
window.clearHistory = clearHistory;
window.restartBackend = restartBackend;
window.adminLog = adminLog;
window.onDocDrop = onDocDrop;
window.onDocFileSelect = onDocFileSelect;
window.compressDoc = compressDoc;
window.copyDocCompressed = copyDocCompressed;
window.sendDocToOptimizer = sendDocToOptimizer;
