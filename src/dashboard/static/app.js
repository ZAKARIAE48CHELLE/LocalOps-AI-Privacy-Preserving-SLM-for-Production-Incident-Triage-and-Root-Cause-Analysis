/**
 * LocalOps AI — Mission Control Frontend Logic
 * Supports Phase 5 QLoRA Fine-Tuning & Phase 4 Baseline Benchmark.
 * Seamless mobile responsiveness and real-time canvas chart plotting.
 */

const POLL_INTERVAL_MS = 2500;
let currentTab = localStorage.getItem("localops_active_tab") || "phase5";

// Tab Switching
function switchTab(tabId) {
  currentTab = tabId;
  localStorage.setItem("localops_active_tab", tabId);

  document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
  document.querySelectorAll(".dashboard-view").forEach((view) => view.classList.remove("active"));

  const btnEl = document.getElementById(`tab-btn-${tabId}`);
  const viewEl = document.getElementById(`view-${tabId}`);
  if (btnEl) btnEl.classList.add("active");
  if (viewEl) viewEl.classList.add("active");

  const headerSubtitle = document.getElementById("header-subtitle");
  if (headerSubtitle) {
    if (tabId === "phase5") {
      headerSubtitle.textContent = "Phase 5 QLoRA Fine-Tuning · Qwen/Qwen2.5-1.5B-Instruct · 8 GB RTX 3070";
    } else {
      headerSubtitle.textContent = "Phase 4 Baseline Evaluation · 4,320 Predictions Completed & Locked";
    }
  }

  // Redraw chart if switching to Phase 5
  if (tabId === "phase5") {
    setTimeout(resizeAndRenderChart, 50);
  }
}

// Live Clock
function updateClock() {
  const clockEl = document.getElementById("live-clock");
  if (!clockEl) return;
  const now = new Date();
  clockEl.textContent = now.toTimeString().split(" ")[0];
}

setInterval(updateClock, 1000);
updateClock();

// Polling Loop
async function pollTelemetry() {
  const connIndicator = document.getElementById("connection-status");

  try {
    // Fetch Phase 5 status
    const p5Res = await fetch("/api/training_status");
    if (p5Res.ok) {
      const p5Data = await p5Res.json();
      renderPhase5(p5Data);
    }

    // Fetch Phase 4 baseline status
    const p4Res = await fetch("/api/status");
    if (p4Res.ok) {
      const p4Data = await p4Res.json();
      renderPhase4(p4Data);
    }

    // Fetch Agent Live Activity Stream
    try {
      const actRes = await fetch("/api/agent_activity");
      if (actRes.ok) {
        const actData = await actRes.json();
        renderAgentActivity(actData);
      }
    } catch (e) {}

    // Check for active action prompts (interactive notification)
    await checkActionPrompt();

    if (connIndicator) {
      connIndicator.innerHTML = `
        <span class="status-indicator live"></span>
        <span id="connection-text">Live (2.5s)</span>
      `;
    }
  } catch (err) {
    console.warn("Telemetry fetch error:", err);
    if (connIndicator) {
      connIndicator.innerHTML = `
        <span class="status-indicator" style="background: #f43f5e; box-shadow: 0 0 8px #f43f5e;"></span>
        <span id="connection-text" style="color: #fb7185;">Reconnecting...</span>
      `;
    }
  }
}

setInterval(pollTelemetry, POLL_INTERVAL_MS);
pollTelemetry();

// =========================================================================
// PHASE 5: QLoRA FINE-TUNING RENDERER
// =========================================================================
let cachedP5History = [];

function renderPhase5(data) {
  if (!data) return;

  const training = data.training || {};
  const gpu = data.gpu || {};
  const energy = data.energy || {};
  const status = training.status || "ready";

  // 1. Status Pill & Header Badge
  const statusPill = document.getElementById("p5-status-pill");
  const headerBadge = document.getElementById("status-badge-text");
  const tabBadge = document.getElementById("tab-badge-p5");

  if (status === "running") {
    if (statusPill) {
      statusPill.className = "p5-status-pill status-running";
      statusPill.textContent = "TRAINING IN PROGRESS";
    }
    if (headerBadge) headerBadge.textContent = "TRAINING ACTIVE · OPTIMIZER STEPPING";
    if (tabBadge) {
      tabBadge.textContent = "TRAINING";
      tabBadge.style.background = "rgba(16, 185, 129, 0.25)";
      tabBadge.style.color = "#34d399";
    }
  } else if (status === "evaluating") {
    if (statusPill) {
      statusPill.className = "p5-status-pill status-running";
      statusPill.textContent = "EVALUATING VALIDATION SLICE";
    }
    if (headerBadge) headerBadge.textContent = "EVALUATING CHECKPOINT";
  } else if (status === "completed") {
    if (statusPill) {
      statusPill.className = "p5-status-pill status-completed";
      statusPill.textContent = "TRAINING COMPLETED";
    }
    if (headerBadge) headerBadge.textContent = "PHASE 5 COMPLETED · ADAPTER SAVED";
    if (tabBadge) {
      tabBadge.textContent = "DONE";
      tabBadge.style.background = "rgba(6, 182, 212, 0.2)";
      tabBadge.style.color = "#38bdf8";
    }
  } else {
    if (statusPill) {
      statusPill.className = "p5-status-pill status-ready";
      statusPill.textContent = "READY TO TRAIN";
    }
    if (headerBadge) headerBadge.textContent = "PHASE 5: READY TO TRAIN";
    if (tabBadge) {
      tabBadge.textContent = "READY";
      tabBadge.style.background = "rgba(245, 158, 11, 0.2)";
      tabBadge.style.color = "#fbbf24";
    }
  }

  // 2. Step, Epoch, Loss, ETA
  const step = training.global_step || 0;
  const maxSteps = training.max_steps || 810;
  const pct = training.progress_pct || 0.0;
  const epoch = training.epoch || 0.0;
  const trainLoss = training.train_loss !== null ? training.train_loss : null;
  const evalLoss = training.eval_loss !== null ? training.eval_loss : null;
  const lr = training.learning_rate || 1.5e-4;
  const eta = training.eta_formatted || "Ready";
  const elapsed = training.elapsed_seconds || 0;

  setText("p5-step-val", `${step} / ${maxSteps}`);
  setText("p5-step-sub", `${pct.toFixed(1)}% Progress`);
  setText("p5-epoch-val", `${epoch.toFixed(2)} / 3.00`);
  setText("p5-loss-val", trainLoss !== null ? trainLoss.toFixed(4) : "--");
  setText("p5-eta-val", eta);
  setText("p5-elapsed-sub", `Elapsed: ${formatDuration(elapsed)}`);

  const fillEl = document.getElementById("p5-progress-fill");
  if (fillEl) fillEl.style.width = `${Math.min(100, pct)}%`;
  setText("p5-pct-label", `${pct.toFixed(1)}% Complete`);
  setText("p5-steps-remaining-label", `${Math.max(0, maxSteps - step)} Steps Remaining`);

  // 3. Four Metric Cards
  setText("mc-train-loss", trainLoss !== null ? trainLoss.toFixed(4) : "--");
  setText("mc-eval-loss", evalLoss !== null ? evalLoss.toFixed(4) : "--");
  setText("mc-learning-rate", lr ? lr.toExponential(2) : "1.50e-4");
  if (training.best_checkpoint) {
    const ckptName = training.best_checkpoint.split("/").pop().split("\\").pop();
    setText("mc-best-ckpt-sub", `Best: ${ckptName} (${evalLoss !== null ? evalLoss.toFixed(4) : ""})`);
  }

  // 4. Diagnostic Quality Targets
  const gen = training.latest_generation_metrics;
  if (gen) {
    setText("qc-schema-val", gen.schema_valid_rate !== undefined ? `${(gen.schema_valid_rate * 100).toFixed(1)}%` : "--%");
    setText("qc-sev-f1-val", gen.severity_macro_f1 !== undefined ? gen.severity_macro_f1.toFixed(4) : "--");
    setText("qc-p4-val", gen.p4_low_recall !== undefined ? `${(gen.p4_low_recall * 100).toFixed(1)}%` : "--%");
    setText("qc-type-f1-val", gen.incident_type_macro_f1 !== undefined ? gen.incident_type_macro_f1.toFixed(4) : "--");
    setText("qc-msg-val", gen.messaging_recall !== undefined ? `${(gen.messaging_recall * 100).toFixed(1)}%` : "--%");
  }

  // 5. Hardware Telemetry
  const vramUsed = gpu.memory_used_mb || 0;
  const vramTotal = gpu.memory_total_mb || 8192;
  const vramPct = (vramUsed / Math.max(1, vramTotal)) * 100;
  setText("p5-vram-text", `${(vramUsed / 1024).toFixed(2)} / ${(vramTotal / 1024).toFixed(1)} GB`);
  const vramBar = document.getElementById("p5-vram-bar");
  if (vramBar) vramBar.style.width = `${Math.min(100, vramPct)}%`;
  setText("p5-vram-sub", `Budget: ${vramTotal.toFixed(0)} MB · Used: ${vramUsed.toFixed(0)} MB (${vramPct.toFixed(1)}%)`);

  const powerW = gpu.power_w || 0;
  setText("p5-power-text", `${powerW.toFixed(1)} W`);
  const powerBar = document.getElementById("p5-power-bar");
  if (powerBar) powerBar.style.width = `${Math.min(100, (powerW / 85.0) * 100)}%`;
  setText("p5-power-sub", `Limit: 85.0 W · Avg: ${energy.average_power_w || "--"} W`);

  setText("p5-energy-text", `${(energy.energy_wh || 0).toFixed(2)} Wh`);
  setText("p5-energy-kwh", `${(energy.energy_kwh || 0).toFixed(4)} kWh`);
  setText("p5-energy-cost", `$${(energy.estimated_cost_usd || 0).toFixed(3)} USD`);
  setText("p5-energy-carbon", `${(energy.carbon_co2_g || 0).toFixed(1)} g CO₂ equivalent`);

  setText("p5-load-temp-text", `${(gpu.gpu_util_pct || 0).toFixed(0)}% · ${(gpu.temp_c || 0).toFixed(0)}°C`);
  const loadBar = document.getElementById("p5-load-bar");
  if (loadBar) loadBar.style.width = `${Math.min(100, gpu.gpu_util_pct || 0)}%`;

  if (gpu.name) setText("p5-gpu-name", gpu.name);

  // 6. Loss Curves (Canvas)
  cachedP5History = training.recent_history || [];
  drawLossChart(cachedP5History);

  // 7. Event Ticker
  renderEventList(training.generation_history || [], cachedP5History);

  // 8. Checkpoint Resolution & Overfitting Protection Table
  renderCheckpointTable();
}

// Chart Plotting Function
function drawLossChart(history) {
  const canvas = document.getElementById("p5-loss-canvas");
  const emptyOverlay = document.getElementById("p5-chart-empty");
  if (!canvas) return;

  const validEntries = history.filter((h) => h.loss !== undefined || h.eval_loss !== undefined);

  if (validEntries.length === 0) {
    if (emptyOverlay) emptyOverlay.style.display = "flex";
    return;
  }
  if (emptyOverlay) emptyOverlay.style.display = "none";

  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;
  ctx.clearRect(0, 0, w, h);

  const padding = { top: 20, right: 25, bottom: 25, left: 45 };
  const graphW = w - padding.left - padding.right;
  const graphH = h - padding.top - padding.bottom;

  // Find min/max steps and losses
  const losses = validEntries.map((e) => (e.loss !== undefined ? e.loss : e.eval_loss));
  const minLoss = Math.max(0, Math.min(...losses) * 0.9);
  const maxLoss = Math.max(...losses) * 1.1 || 2.0;

  const minStep = validEntries[0].step || 0;
  const maxStep = validEntries[validEntries.length - 1].step || 100;

  const getX = (step) => padding.left + ((step - minStep) / Math.max(1, maxStep - minStep)) * graphW;
  const getY = (loss) => padding.top + (1 - (loss - minLoss) / Math.max(0.001, maxLoss - minLoss)) * graphH;

  // Draw Subtle Grid
  ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= 3; i++) {
    const yVal = padding.top + (graphH / 3) * i;
    ctx.moveTo(padding.left, yVal);
    ctx.lineTo(w - padding.right, yVal);

    // Axis label
    const lossLabel = (maxLoss - ((maxLoss - minLoss) / 3) * i).toFixed(2);
    ctx.fillStyle = "#64748b";
    ctx.font = "10px JetBrains Mono";
    ctx.textAlign = "right";
    ctx.fillText(lossLabel, padding.left - 8, yVal + 3);
  }
  ctx.stroke();

  // Draw Train Loss Curve (Cyan)
  const trainPoints = validEntries.filter((e) => e.loss !== undefined);
  if (trainPoints.length > 1) {
    ctx.strokeStyle = "#06b6d4";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    trainPoints.forEach((pt, i) => {
      const x = getX(pt.step);
      const y = getY(pt.loss);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Area fill under curve
    ctx.lineTo(getX(trainPoints[trainPoints.length - 1].step), padding.top + graphH);
    ctx.lineTo(getX(trainPoints[0].step), padding.top + graphH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padding.top, 0, padding.top + graphH);
    grad.addColorStop(0, "rgba(6, 182, 212, 0.18)");
    grad.addColorStop(1, "rgba(6, 182, 212, 0.0)");
    ctx.fillStyle = grad;
    ctx.fill();
  }

  // Draw Validation Loss Points (Ruby / Rose)
  const evalPoints = validEntries.filter((e) => e.eval_loss !== undefined);
  evalPoints.forEach((pt) => {
    const x = getX(pt.step);
    const y = getY(pt.eval_loss);

    ctx.fillStyle = "#f43f5e";
    ctx.beginPath();
    ctx.arc(x, y, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });
}

function resizeAndRenderChart() {
  if (cachedP5History.length > 0) {
    drawLossChart(cachedP5History);
  }
}

window.addEventListener("resize", resizeAndRenderChart);

// Render Event List
function renderEventList(genHistory, history) {
  const container = document.getElementById("p5-events-list");
  const countEl = document.getElementById("p5-event-count");
  if (!container) return;

  const events = [];

  genHistory.forEach((g) => {
    events.push({
      type: "validation",
      step: g.step,
      text: `Validation Eval @ Step ${g.step}: Schema Valid=${((g.schema_valid_rate || 0) * 100).toFixed(1)}%, Sev F1=${(g.severity_macro_f1 || 0).toFixed(4)}, Type F1=${(g.incident_type_macro_f1 || 0).toFixed(4)}, P4 Recall=${((g.p4_low_recall || 0) * 100).toFixed(1)}%`,
    });
  });

  history.forEach((h) => {
    if (h.eval_loss !== undefined) {
      events.push({
        type: "eval",
        step: h.step,
        text: `Checkpoint Evaluated @ Step ${h.step} — Eval Loss: ${h.eval_loss.toFixed(4)}`,
      });
    }
  });

  events.sort((a, b) => (b.step || 0) - (a.step || 0));

  if (countEl) countEl.textContent = `${events.length} Events`;

  if (events.length === 0) {
    container.innerHTML = `<div class="p5-event-empty">No training events recorded yet. Ready to launch.</div>`;
    return;
  }

  container.innerHTML = events
    .slice(0, 8)
    .map(
      (ev) => `
      <div class="p5-event-item">
        <span class="text-cyan">[Step ${ev.step}]</span>
        <span style="flex: 1; margin-left: 0.75rem; color: #cbd5e1;">${ev.text}</span>
      </div>
    `
    )
    .join("");
}

// =========================================================================
// PHASE 4: BASELINE BENCHMARK RENDERER (LOCKED)
// =========================================================================
function renderPhase4(data) {
  if (!data) return;

  const exps = data.experiments || {};
  const e1 = exps.E1 || {};
  const e2 = exps.E2 || {};
  const e3 = exps.E3 || {};

  setText("e1-count-label", `${e1.completed || 1440} / 1440`);
  setText("e2-count-label", `${e2.completed || 1440} / 1440`);
  setText("e3-count-label", `${e3.completed || 1440} / 1440`);

  // Render recent predictions feed
  const streamEl = document.getElementById("predictions-stream");
  const recent = data.recent_predictions || [];
  if (streamEl && recent.length > 0) {
    streamEl.innerHTML = recent
      .map((r) => {
        const isValid = r.strict_json_valid || r.pydantic_valid;
        return `
        <article class="feed-item glass-panel">
          <div class="feed-item-header">
            <span class="feed-item-id font-mono">${r.incident_id || "--"}</span>
            <div class="feed-item-meta">
              <span class="badge-tag tag-exp">${r.experiment_id || "EXP"}</span>
              <span class="badge-tag ${isValid ? "tag-valid" : "tag-invalid"}">${isValid ? "SCHEMA VALID" : "INVALID"}</span>
              <span class="badge-tag font-mono">${r.latency_seconds || "--"}s</span>
            </div>
          </div>
          <div class="feed-item-body">
            <div class="feed-body-col"><span class="k">TYPE (PRED / GT)</span><span class="v font-mono">${r.incident_type_pred || "--"} / ${r.incident_type_gt || "--"}</span></div>
            <div class="feed-body-col"><span class="k" title="Severity is based on operational impact, blast radius, redundancy, security exposure, and data integrity.">SEV (PRED / GT) ℹ️</span><span class="v font-mono">${r.severity_pred || "--"} <span class="badge font-mono" style="font-size: 0.65rem; padding: 1px 4px; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 4px;" title="Severity Source: ${r.severity_source || 'POLICY_ENGINE'}">${r.severity_source === 'MODEL' ? 'SLM' : 'POLICY'}</span> / ${r.severity_gt || "--"}${r.severity_warning ? ' <span title="' + r.severity_warning + '">⚠️</span>' : ''}</span></div>
            <div class="feed-body-col"><span class="k">SERVICE (PRED / GT)</span><span class="v font-mono">${r.affected_service_pred || "--"} / ${r.affected_service_gt || "--"}</span></div>
            <div class="feed-body-col"><span class="k">TECHNOLOGY</span><span class="v font-mono">${r.technology || "--"}</span></div>
          </div>
          <pre class="feed-item-preview font-mono">${escapeHtml(r.raw_output_preview || "")}</pre>
        </article>
      `;
      })
      .join("");
  }
}

// Helpers
function setText(id, val) {
  const el = document.getElementById(id);
  if (el && val !== undefined) el.textContent = val;
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "0s";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// =========================================================================
// INTERACTIVE NOTIFICATION & ACTION PROMPT HANDLER (MOBILE & DESKTOP)
// =========================================================================
let currentPromptId = null;

async function checkActionPrompt() {
  try {
    const res = await fetch("/api/action_prompt");
    if (!res.ok) return;
    const data = await res.json();

    const backdrop = document.getElementById("action-modal-backdrop");
    if (!backdrop) return;

    if (data && data.active) {
      if (currentPromptId !== data.id) {
        currentPromptId = data.id;
        renderActionPrompt(data);
      }
      backdrop.style.display = "flex";
      // Vibrate mobile device if supported
      if (navigator.vibrate) {
        try {
          navigator.vibrate([200, 100, 200]);
        } catch (e) {}
      }
    } else {
      backdrop.style.display = "none";
      currentPromptId = null;
    }
  } catch (err) {
    console.warn("Action prompt check error:", err);
  }
}

function renderActionPrompt(data) {
  const badge = document.getElementById("action-modal-badge");
  const title = document.getElementById("action-modal-title");
  const desc = document.getElementById("action-modal-desc");
  const container = document.getElementById("action-options-container");
  const statusEl = document.getElementById("action-modal-status");

  if (badge && data.badge) badge.textContent = data.badge;
  if (title && data.title) title.textContent = data.title;
  if (desc && data.message) desc.textContent = data.message;
  if (statusEl) statusEl.style.display = "none";

  if (container && data.options) {
    container.innerHTML = data.options
      .map(
        (opt) => `
        <button class="action-option-btn ${opt.btnClass || "btn-primary"}" onclick="submitActionResponse('${escapeHtml(data.id)}', '${escapeHtml(opt.id)}')">
          <span>${opt.label}</span>
        </button>
      `
      )
      .join("");
  }
}

async function submitActionResponse(promptId, optionId) {
  const statusEl = document.getElementById("action-modal-status");
  const statusText = document.getElementById("action-status-text");
  const container = document.getElementById("action-options-container");

  if (statusEl) statusEl.style.display = "flex";
  if (statusText) statusText.textContent = `Selection '${optionId}' confirmed. Submitting to engine...`;
  if (container) {
    container.querySelectorAll("button").forEach((btn) => {
      btn.disabled = true;
      btn.style.opacity = "0.5";
      btn.style.pointerEvents = "none";
    });
  }

  try {
    const res = await fetch("/api/action_response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt_id: promptId,
        selected_option: optionId,
        timestamp: Date.now()
      })
    });
    if (res.ok) {
      if (statusText) statusText.textContent = "Decision submitted! Synchronizing training runtime...";
      setTimeout(() => {
        const backdrop = document.getElementById("action-modal-backdrop");
        if (backdrop) backdrop.style.display = "none";
      }, 1500);
    } else {
      if (statusText) statusText.textContent = "Error submitting response. Retrying...";
    }
  } catch (err) {
    console.error("Failed to submit action response:", err);
    if (statusText) statusText.textContent = "Network error submitting response.";
  }
}

// =========================================================================
// AGENT LIVE ACTIVITY STREAM & OBSERVABILITY
// =========================================================================
let agentTimelineOpen = false;

function toggleAgentTimeline() {
  const container = document.getElementById("agent-timeline-container");
  const icon = document.getElementById("timeline-toggle-icon");
  if (!container) return;

  agentTimelineOpen = !agentTimelineOpen;
  container.style.display = agentTimelineOpen ? "block" : "none";
  if (icon) icon.textContent = agentTimelineOpen ? "▲" : "▼";
}

let cachedAgentActivityStr = null;

function renderAgentActivity(activity) {
  if (!activity) return;

  const currentStr = JSON.stringify(activity);
  if (currentStr === cachedAgentActivityStr) return;
  cachedAgentActivityStr = currentStr;

  if (activity.status_badge) setText("agent-status-badge", activity.status_badge);
  if (activity.current_task) setText("agent-current-task", activity.current_task);
  if (activity.summary) setText("agent-task-desc", activity.summary);
  if (activity.next_action) setText("agent-next-step", activity.next_action);

  const timeline = activity.timeline || [];
  setText("timeline-count", timeline.length);

  const timelineList = document.getElementById("agent-timeline-list");
  if (timelineList && timeline.length > 0) {
    timelineList.innerHTML = timeline
      .map((item) => {
        const itemClass = item.status === "active" ? "active" : item.status === "success" ? "success" : "";
        const icon = item.status === "active" ? "⚡" : "✓";
        return `
          <div class="agent-timeline-item ${itemClass}">
            <div class="agent-tl-time font-mono">${escapeHtml(item.time || "")}</div>
            <div class="agent-tl-content">
              <div class="agent-tl-action font-mono">
                <span style="color: var(--accent-cyan); margin-right: 0.3rem;">${icon}</span>
                <strong>[${escapeHtml(item.phase || "")}]</strong> ${escapeHtml(item.action || "")}
              </div>
              <div class="agent-tl-detail font-mono">${escapeHtml(item.detail || "")}</div>
            </div>
          </div>
        `;
      })
      .join("");
  }
}

// =========================================================================
// CHECKPOINT RESOLUTION & COMPARISON TABLE RENDERER
// =========================================================================
let cachedCheckpointsStr = null;

async function renderCheckpointTable() {
  const tbody = document.getElementById("checkpoint-table-body");
  if (!tbody) return;

  try {
    const res = await fetch("/api/checkpoints_comparison");
    if (!res.ok) return;
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) return;

    const dataStr = JSON.stringify(data);
    if (dataStr === cachedCheckpointsStr) return;
    cachedCheckpointsStr = dataStr;

    tbody.innerHTML = data
      .map((row) => {
        const isSelected = row.status === "OFFICIAL_SELECTED_ADAPTER";
        const isOverfitted = row.status === "OVERFITTED_END_OF_TRAINING_STATE";
        const rowClass = isSelected ? "selected-row" : "";

        let statusBadge = "";
        if (isSelected) {
          statusBadge = '<span class="ckpt-badge-selected">★ SELECTED (MIN LOSS)</span>';
        } else if (isOverfitted) {
          statusBadge = '<span class="ckpt-badge-overfitted">OVERFITTED (DIVERGENCE)</span>';
        } else {
          statusBadge = '<span class="ckpt-badge-rejected">REJECTED (EVAL LOSS ↑)</span>';
        }

        const evalLossDisplay =
          row.eval_loss !== undefined
            ? isSelected
              ? `<span style="color: #34d399; font-weight: 700;">${row.eval_loss.toFixed(4)} ★</span>`
              : row.eval_loss.toFixed(4)
            : "--";

        const trainLossDisplay =
          row.train_loss !== undefined ? row.train_loss.toFixed(4) : "--";

        const schemaDisplay =
          row.schema_valid_rate !== undefined
            ? `${(row.schema_valid_rate * 100).toFixed(1)}%`
            : "--";

        const typeF1Display =
          row.incident_type_macro_f1 !== undefined
            ? row.incident_type_macro_f1.toFixed(4)
            : "--";

        const sevF1Display =
          row.severity_macro_f1 !== undefined
            ? row.severity_macro_f1.toFixed(4)
            : "--";

        const msgRecallDisplay =
          row.messaging_recall !== undefined
            ? `${(row.messaging_recall * 100).toFixed(1)}%`
            : "--";

        const p4RecallDisplay =
          row.p4_low_recall !== undefined
            ? `${(row.p4_low_recall * 100).toFixed(1)}%`
            : "--";

        return `
          <tr class="${rowClass}">
            <td style="padding: 0.7rem 0.6rem; font-weight: 600;">
              ${isSelected ? "⭐ " : ""}${escapeHtml(row.checkpoint)}
            </td>
            <td style="padding: 0.7rem 0.6rem; color: var(--text-dim);">${row.step}</td>
            <td style="padding: 0.7rem 0.6rem;">${evalLossDisplay}</td>
            <td style="padding: 0.7rem 0.6rem; color: var(--accent-cyan);">${trainLossDisplay}</td>
            <td style="padding: 0.7rem 0.6rem;">${schemaDisplay}</td>
            <td style="padding: 0.7rem 0.6rem;">${typeF1Display}</td>
            <td style="padding: 0.7rem 0.6rem;">${sevF1Display}</td>
            <td style="padding: 0.7rem 0.6rem;">${msgRecallDisplay}</td>
            <td style="padding: 0.7rem 0.6rem;">${p4RecallDisplay}</td>
            <td style="padding: 0.7rem 0.6rem;">${statusBadge}</td>
          </tr>
        `;
      })
      .join("");
  } catch (err) {
    console.warn("Error rendering checkpoint table:", err);
  }
}

// Apply initial tab on page load
document.addEventListener("DOMContentLoaded", () => {
  switchTab(currentTab);
  renderCheckpointTable();
});
