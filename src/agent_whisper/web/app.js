(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const runtimeTitle = $("#runtime-title");
  const runtimeDetail = $("#runtime-detail");
  const dictationButton = $("#dictation-button");
  const latestTranscript = $("#latest-transcript");
  const copyLatest = $("#copy-latest");
  const wordCount = $("#word-count");
  const routeState = $("#route-state");
  const routeProvider = $("#route-provider");
  const routeModel = $("#route-model");
  const signalStatus = $(".signal-status");
  const privacyState = $("#privacy-state");
  const toast = $("#toast");
  const canvas = $("#signal-canvas");
  const context = canvas.getContext("2d");

  const ui = {
    runtime: null,
    settings: null,
    vocabulary: null,
    history: [],
    provider: "local",
    page: "speak",
    polling: false,
    latestRendered: null,
    lastVersion: -1,
    lastHistoryRevision: -1,
    hotkeyCapturing: false,
    hotkeyCaptureTimer: null,
    clearArmed: false,
    quitArmed: false,
    toastTimer: null,
    phase: 0,
    visualLevel: 0,
    peakLevel: 0,
    visualLevels: Array(18).fill(0),
    reduceMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  };

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("is-visible");
    clearTimeout(ui.toastTimer);
    ui.toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2200);
  }

  function showPage(name) {
    ui.page = name;
    $$(".nav-item").forEach((button) => {
      const selected = button.dataset.page === name;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-current", selected ? "page" : "false");
    });
    $$(".page").forEach((page) => {
      page.classList.toggle("is-visible", page.id === `page-${name}`);
    });
    if (name === "history") refreshHistory();
  }

  function stateCopy(runtime) {
    const hotkey = runtime.hotkey_label || "Right Ctrl";
    const defaults = {
      idle: {
        title: `Ready — hold ${hotkey}`,
        detail: "Release the key when you finish speaking.",
        button: "Start dictation",
        disabled: false,
      },
      listening: {
        title: `Listening · ${formatDuration(runtime.recording_seconds)}`,
        detail: `Release ${hotkey} to transcribe. Clicking Finish also works.`,
        button: "Finish & transcribe",
        disabled: false,
      },
      transcribing: {
        title: "Processing your speech",
        detail: "Your selected provider is turning audio into text.",
        button: "Processing…",
        disabled: true,
      },
      success: {
        title: runtime.pasted ? "Transcript pasted" : "Transcript ready",
        detail: runtime.detail || "Saved locally in History.",
        button: "Start dictation",
        disabled: false,
      },
      error: {
        title: "Could not finish dictation",
        detail: runtime.detail || "Check the problem, then try again.",
        button: "Try again",
        disabled: false,
      },
    };
    const copy = defaults[runtime.state] || defaults.idle;
    if (runtime.detail && runtime.state === "transcribing") copy.detail = runtime.detail;
    return copy;
  }

  function formatDuration(seconds) {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
  }

  function renderRuntime(runtime) {
    ui.runtime = runtime;
    const copy = stateCopy(runtime);
    runtimeTitle.textContent = copy.title;
    runtimeDetail.textContent = copy.detail;
    dictationButton.textContent = copy.button;
    dictationButton.disabled = copy.disabled;
    routeState.textContent = {
      idle: "Ready",
      listening: "Listening",
      transcribing: "Processing",
      success: "Complete",
      error: "Needs attention",
    }[runtime.state] || "Ready";
    signalStatus.dataset.state = runtime.state;
    routeProvider.textContent = runtime.provider_name;
    routeModel.textContent = runtime.model;

    privacyState.classList.toggle("is-cloud", !runtime.local);
    $("span:last-child", privacyState).textContent = runtime.local
      ? "Audio stays on this PC"
      : `Audio sent to ${runtime.provider_name}`;

    if (ui.latestRendered !== runtime.latest_text) {
      ui.latestRendered = runtime.latest_text;
      latestTranscript.replaceChildren();
      const paragraph = document.createElement("p");
      if (runtime.latest_text) {
        paragraph.textContent = runtime.latest_text;
      } else {
        paragraph.className = "placeholder";
        paragraph.textContent =
          "Your latest transcript will appear here and remain available in local history.";
      }
      latestTranscript.append(paragraph);
    }
    wordCount.textContent = runtime.word_count ? `${runtime.word_count} words` : "";
    copyLatest.disabled = !runtime.latest_text;

    ui.lastVersion = runtime.version;
    if (runtime.history_revision !== ui.lastHistoryRevision) {
      const previousRevision = ui.lastHistoryRevision;
      ui.lastHistoryRevision = runtime.history_revision;
      if (ui.page === "history" && previousRevision >= 0) refreshHistory();
    }
  }

  function setProvider(provider) {
    ui.provider = provider;
    $$(".provider-option").forEach((option) => {
      const selected = option.dataset.provider === provider;
      option.classList.toggle("is-selected", selected);
      option.setAttribute("aria-checked", String(selected));
      option.tabIndex = selected ? 0 : -1;
    });
    $$("[data-provider-panel]").forEach((panel) => {
      panel.classList.toggle("is-hidden", panel.dataset.providerPanel !== provider);
    });
  }

  function fillSelect(select, options, selectedValue) {
    select.replaceChildren();
    options.forEach((option) => {
      const element = document.createElement("option");
      element.value = String(option.value);
      element.textContent = option.label;
      element.selected = String(option.value) === String(selectedValue ?? "");
      select.append(element);
    });
  }

  function populateSettings(bootstrap) {
    const settings = bootstrap.settings;
    ui.settings = settings;
    setProvider(settings.provider);
    $("#local-model-dir").value = settings.local_model_dir || "";
    fillSelect(
      $("#groq-model"),
      bootstrap.groq_models.map((value) => ({ value, label: value })),
      settings.groq_model,
    );
    $("#custom-base-url").value = settings.custom_base_url || "";
    $("#custom-model").value = settings.custom_model || "";
    $("#hotkey").value = settings.hotkey;
    $("#hotkey-display").textContent = settings.hotkey_label;
    fillSelect($("#input-device"), bootstrap.devices, settings.input_device ?? "");
    $("#language").value = settings.language || "en";
    $("#paste-result").checked = Boolean(settings.paste_result);
    $("#restore-clipboard").checked = Boolean(settings.restore_clipboard);
    $("#cleanup-speech").checked = settings.cleanup_speech !== false;
    $("#start-with-windows").checked = Boolean(settings.start_with_windows);
    $("#project-path").value = settings.project_path || "";
    $("#groq-key-status").textContent = settings.groq_key_saved
      ? "API key saved · encrypted with Windows DPAPI."
      : "No API key saved · encrypted with Windows DPAPI when added.";
    $("#custom-key-status").textContent = settings.custom_key_saved
      ? "API key saved · HTTPS required outside localhost."
      : "No API key saved · HTTPS required outside localhost.";
    const deviceError = $("#device-error");
    deviceError.textContent = bootstrap.device_error || "";
    deviceError.classList.toggle("is-hidden", !bootstrap.device_error);
    renderVocabulary(bootstrap.vocabulary);
  }

  async function finishHotkeyCapture(message = "Click, then press any keyboard key") {
    clearTimeout(ui.hotkeyCaptureTimer);
    ui.hotkeyCaptureTimer = null;
    const recorder = $("#hotkey-recorder");
    recorder.classList.remove("is-capturing");
    recorder.setAttribute("aria-pressed", "false");
    $("#hotkey-instruction").textContent = message;
    if (!ui.hotkeyCapturing) return;
    ui.hotkeyCapturing = false;
    try {
      await window.pywebview.api.end_hotkey_capture();
    } catch (error) {
      showToast(error.message || String(error));
    }
  }

  async function beginHotkeyCapture() {
    if (ui.hotkeyCapturing) return;
    try {
      await window.pywebview.api.begin_hotkey_capture();
      ui.hotkeyCapturing = true;
      const recorder = $("#hotkey-recorder");
      recorder.classList.add("is-capturing");
      recorder.setAttribute("aria-pressed", "true");
      $("#hotkey-display").textContent = "Press a key…";
      $("#hotkey-instruction").textContent = "Any single keyboard key works";
      recorder.focus();
      ui.hotkeyCaptureTimer = setTimeout(() => {
        $("#hotkey-display").textContent = ui.settings.hotkey_label;
        finishHotkeyCapture("Capture timed out — click to try again");
      }, 8000);
    } catch (error) {
      showToast(error.message || String(error));
    }
  }

  function settingsPayload() {
    return {
      provider: ui.provider,
      local_model_dir: $("#local-model-dir").value,
      groq_model: $("#groq-model").value,
      groq_api_key: $("#groq-api-key").value,
      custom_base_url: $("#custom-base-url").value,
      custom_model: $("#custom-model").value,
      custom_api_key: $("#custom-api-key").value,
      hotkey: $("#hotkey").value,
      input_device: $("#input-device").value,
      language: $("#language").value,
      paste_result: $("#paste-result").checked,
      restore_clipboard: $("#restore-clipboard").checked,
      cleanup_speech: $("#cleanup-speech").checked,
      start_with_windows: $("#start-with-windows").checked,
      project_path: $("#project-path").value,
    };
  }

  function renderVocabulary(vocabulary) {
    ui.vocabulary = vocabulary;
    const projectStatus = $("#project-term-status");
    projectStatus.textContent = vocabulary.project_path
      ? `${vocabulary.project_term_count} project spelling${vocabulary.project_term_count === 1 ? "" : "s"} ready · scan stays on this PC.`
      : "No project folder selected.";

    const learned = vocabulary.learned || [];
    $("#learned-count").textContent = `${learned.length} saved`;
    const list = $("#learned-list");
    list.replaceChildren();
    if (!learned.length) {
      const empty = document.createElement("p");
      empty.className = "learned-empty";
      empty.textContent = "No learned corrections yet.";
      list.append(empty);
      return;
    }

    learned.forEach((item) => {
      const row = document.createElement("div");
      row.className = "learned-row";
      const mapping = document.createElement("span");
      const alias = document.createElement("span");
      alias.textContent = item.alias;
      const separator = document.createElement("i");
      separator.textContent = "becomes";
      const canonical = document.createElement("code");
      canonical.textContent = item.canonical;
      mapping.append(alias, separator, canonical);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "learned-remove";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove correction ${item.alias} to ${item.canonical}`);
      remove.addEventListener("click", async () => {
        remove.disabled = true;
        try {
          renderVocabulary(
            await window.pywebview.api.forget_correction(item.alias, item.canonical),
          );
          showToast("Correction removed");
        } catch (error) {
          remove.disabled = false;
          showToast(error.message || String(error));
        }
      });
      row.append(mapping, remove);
      list.append(row);
    });
  }

  function suggestedCorrection(item) {
    const before = String(item.raw_text || "").trim().split(/\s+/).filter(Boolean);
    const after = String(item.text || "").trim().split(/\s+/).filter(Boolean);
    let prefix = 0;
    while (
      prefix < before.length &&
      prefix < after.length &&
      before[prefix].toLocaleLowerCase() === after[prefix].toLocaleLowerCase()
    ) {
      prefix += 1;
    }
    let suffix = 0;
    while (
      suffix < before.length - prefix &&
      suffix < after.length - prefix &&
      before[before.length - 1 - suffix].toLocaleLowerCase() ===
        after[after.length - 1 - suffix].toLocaleLowerCase()
    ) {
      suffix += 1;
    }
    const alias = before.slice(prefix, before.length - suffix).join(" ");
    const canonical = after.slice(prefix, after.length - suffix).join(" ");
    if (!alias || !canonical || alias.length > 120 || canonical.length > 120) {
      return { alias: "", canonical: "" };
    }
    return { alias, canonical };
  }

  function openTeachDialog(item) {
    const dialog = $("#teach-dialog");
    const suggestion = suggestedCorrection(item);
    $("#teach-source").textContent = `Transcript context: ${item.raw_text || item.text}`;
    $("#teach-alias").value = suggestion.alias;
    $("#teach-canonical").value = suggestion.canonical;
    $("#teach-status").className = "";
    $("#teach-status").textContent = "Saved only on this PC.";
    dialog.showModal();
    $(suggestion.alias ? "#teach-canonical" : "#teach-alias").focus();
  }

  function closeTeachDialog() {
    const dialog = $("#teach-dialog");
    if (dialog.open) dialog.close();
  }

  function localDateParts(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return { day: "Earlier", time: value };
    const today = new Date();
    const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const startDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const dayDifference = Math.round((startToday - startDate) / 86400000);
    const day =
      dayDifference === 0
        ? "Today"
        : dayDifference === 1
          ? "Yesterday"
          : new Intl.DateTimeFormat(undefined, {
              day: "numeric",
              month: "long",
              year: "numeric",
            }).format(date);
    const time = new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
    return { day, time };
  }

  function renderHistory(items) {
    ui.history = items;
    const list = $("#history-list");
    list.replaceChildren();
    $("#history-summary").textContent = `${items.length} local transcript${items.length === 1 ? "" : "s"}.`;
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "history-empty";
      const signal = document.createElement("div");
      signal.className = "empty-signal";
      signal.append(document.createElement("i"));
      const title = document.createElement("h2");
      title.textContent = "No transcripts yet";
      const copy = document.createElement("p");
      copy.textContent = `Hold ${ui.runtime?.hotkey_label || "Right Ctrl"} to begin dictating.`;
      empty.append(signal, title, copy);
      list.append(empty);
      return;
    }

    let currentDay = "";
    items.forEach((item) => {
      const date = localDateParts(item.created_at);
      if (date.day !== currentDay) {
        currentDay = date.day;
        const day = document.createElement("div");
        day.className = "history-day";
        day.textContent = currentDay;
        list.append(day);
      }
      const row = document.createElement("article");
      row.className = "history-row";
      const meta = document.createElement("div");
      meta.className = "history-meta";
      const time = document.createElement("span");
      time.textContent = date.time;
      const provider = document.createElement("span");
      provider.textContent = item.provider;
      meta.append(time, provider);
      const copy = document.createElement("p");
      copy.className = "history-copy";
      copy.textContent = item.text;
      const actions = document.createElement("div");
      actions.className = "history-actions";
      const teach = document.createElement("button");
      teach.className = "button button-quiet";
      teach.type = "button";
      teach.textContent = "Teach correction";
      teach.addEventListener("click", () => openTeachDialog(item));
      const copyButton = document.createElement("button");
      copyButton.className = "button button-quiet";
      copyButton.type = "button";
      copyButton.textContent = "Copy";
      copyButton.addEventListener("click", async () => {
        await window.pywebview.api.copy_text(item.text);
        showToast("Transcript copied");
      });
      actions.append(teach, copyButton);
      row.append(meta, copy, actions);
      list.append(row);
    });
  }

  async function refreshHistory() {
    if (!window.pywebview?.api) return;
    try {
      renderHistory(await window.pywebview.api.get_history());
    } catch (error) {
      showToast(`History unavailable: ${error.message || error}`);
    }
  }

  async function pollRuntime() {
    if (ui.polling || !window.pywebview?.api) return;
    ui.polling = true;
    try {
      renderRuntime(await window.pywebview.api.get_runtime());
    } catch (error) {
      runtimeDetail.textContent = `Connection problem: ${error.message || error}`;
    } finally {
      ui.polling = false;
    }
  }

  function resizeCanvas() {
    const rectangle = canvas.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(rectangle.width * ratio));
    const height = Math.max(1, Math.round(rectangle.height * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function drawMicrophone(x, y, color) {
    context.strokeStyle = color;
    context.lineWidth = 2.2;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(x, y - 11);
    context.lineTo(x, y + 4);
    context.stroke();
    context.beginPath();
    context.arc(x, y + 1, 10, 0, Math.PI);
    context.stroke();
    context.beginPath();
    context.moveTo(x, y + 11);
    context.lineTo(x, y + 17);
    context.stroke();
  }

  function drawModel(x, y, color) {
    context.strokeStyle = color;
    context.lineWidth = 1.8;
    context.strokeRect(x - 10, y - 10, 20, 20);
    context.fillStyle = color;
    context.font = '700 8px "Cascadia Mono", monospace';
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText("AI", x, y + 0.5);
    [-7, 0, 7].forEach((offset) => {
      context.beginPath();
      context.moveTo(x - 15, y + offset);
      context.lineTo(x - 11, y + offset);
      context.moveTo(x + 11, y + offset);
      context.lineTo(x + 15, y + offset);
      context.stroke();
    });
  }

  function drawCursor(x, y, color) {
    context.fillStyle = color;
    context.beginPath();
    context.moveTo(x - 7, y - 12);
    context.lineTo(x + 11, y);
    context.lineTo(x + 2, y + 2);
    context.lineTo(x + 7, y + 12);
    context.lineTo(x + 2, y + 14);
    context.lineTo(x - 3, y + 4);
    context.lineTo(x - 9, y + 9);
    context.closePath();
    context.fill();
  }

  function drawNode(x, y, type, active, color) {
    context.fillStyle = active ? "#e8efff" : "#edf1f5";
    context.strokeStyle = active ? color : "#bbc7d3";
    context.lineWidth = active ? 2.2 : 1.6;
    context.beginPath();
    context.arc(x, y, 25, 0, Math.PI * 2);
    context.fill();
    context.stroke();
    const iconColor = active ? color : "#91a0af";
    if (type === "mic") drawMicrophone(x, y, iconColor);
    if (type === "model") drawModel(x, y, iconColor);
    if (type === "cursor") drawCursor(x, y, iconColor);
  }

  function drawSignal() {
    resizeCanvas();
    const width = canvas.getBoundingClientRect().width;
    const height = canvas.getBoundingClientRect().height;
    context.clearRect(0, 0, width, height);
    if (!ui.runtime) {
      requestAnimationFrame(drawSignal);
      return;
    }

    const state = ui.runtime.state;
    const targetLevel = state === "listening" ? Number(ui.runtime.level || 0) : 0;
    ui.visualLevel += (targetLevel - ui.visualLevel) * 0.18;
    ui.peakLevel = Math.max(ui.visualLevel, ui.peakLevel * 0.94);
    ui.phase += ui.reduceMotion ? 0 : 0.075;
    const y = Math.min(86, height * 0.55);
    const x1 = Math.max(74, width * 0.095);
    const x2 = width / 2;
    const x3 = width - x1;
    const start = x1 + 26;
    const end = x3 - 26;

    context.strokeStyle = "#d8e0e7";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(start, y);
    context.lineTo(end, y);
    context.stroke();

    if (state === "listening") {
      const incoming = Array.isArray(ui.runtime.levels) ? ui.runtime.levels : [];
      ui.visualLevels = ui.visualLevels.map((value, index) => {
        const target = Number(incoming[index] ?? targetLevel);
        return value + (target - value) * (target > value ? 0.42 : 0.2);
      });
      const barWidth = Math.max(3, (end - start) / (ui.visualLevels.length * 1.8));
      const gap = ((end - start) - barWidth * ui.visualLevels.length) / (ui.visualLevels.length - 1);
      ui.visualLevels.forEach((value, index) => {
        const centerX = start + index * (barWidth + gap) + barWidth / 2;
        const heightValue = 5 + value * 34;
        context.strokeStyle = index > ui.visualLevels.length * 0.72 ? "#087456" : "#2f67e8";
        context.lineWidth = barWidth;
        context.lineCap = "round";
        context.beginPath();
        context.moveTo(centerX, y - heightValue / 2);
        context.lineTo(centerX, y + heightValue / 2);
        context.stroke();
      });
    } else if (state === "transcribing") {
      context.strokeStyle = "#087456";
      context.lineWidth = 2.7;
      context.beginPath();
      context.moveTo(start, y);
      context.lineTo(x2 - 26, y);
      context.stroke();
      const progress = (Math.sin(ui.phase * 2.2) + 1) / 2;
      const dotX = x2 + 26 + (end - x2 - 26) * progress;
      context.strokeStyle = "#e8efff";
      context.lineWidth = 4;
      context.beginPath();
      context.moveTo(x2 + 26, y);
      context.lineTo(end, y);
      context.stroke();
      context.fillStyle = "#2f67e8";
      context.beginPath();
      context.arc(dotX, y, 4, 0, Math.PI * 2);
      context.fill();
    } else {
      const color = state === "error" ? "#b63a50" : state === "success" ? "#087456" : "#2f67e8";
      context.strokeStyle = color;
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(start, y);
      context.lineTo(end, y);
      context.stroke();
      [0.22, 0.78].forEach((progress) => {
        context.fillStyle = color;
        context.beginPath();
        context.arc(start + (end - start) * progress, y, 3, 0, Math.PI * 2);
        context.fill();
      });
    }

    drawNode(x1, y, "mic", state === "listening", "#2f67e8");
    drawNode(x2, y, "model", state === "transcribing", "#2f67e8");
    drawNode(x3, y, "cursor", state === "success", "#087456");
    requestAnimationFrame(drawSignal);
  }

  async function initialize() {
    try {
      const bootstrap = await window.pywebview.api.get_bootstrap();
      renderRuntime(bootstrap.runtime);
      populateSettings(bootstrap);
      renderHistory(bootstrap.history);
      setInterval(pollRuntime, 60);
    } catch (error) {
      runtimeTitle.textContent = "AgentWisper could not start";
      runtimeDetail.textContent = error.message || String(error);
      dictationButton.disabled = true;
    }
  }

  $$(".nav-item").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.page));
  });

  $$(".provider-option").forEach((option) => {
    option.addEventListener("click", () => setProvider(option.dataset.provider));
    option.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const options = $$(".provider-option");
      const current = options.indexOf(option);
      const next = event.key === "ArrowRight" ? current + 1 : current - 1;
      const target = options[(next + options.length) % options.length];
      setProvider(target.dataset.provider);
      target.focus();
    });
  });

  $("#hotkey-recorder").addEventListener("click", beginHotkeyCapture);
  $("#hotkey-recorder").addEventListener("keydown", async (event) => {
    if (!ui.hotkeyCapturing || event.repeat) return;
    event.preventDefault();
    event.stopPropagation();
    try {
      if (!event.code) throw new Error("That key could not be identified");
      const captured = await window.pywebview.api.preview_hotkey(`code:${event.code}`);
      $("#hotkey").value = captured.value;
      $("#hotkey-display").textContent = captured.label;
      ui.settings.hotkey = captured.value;
      ui.settings.hotkey_label = captured.label;
      await finishHotkeyCapture("Captured — save settings to apply");
    } catch (error) {
      $("#hotkey-display").textContent = ui.settings.hotkey_label;
      await finishHotkeyCapture("Click, then press another key");
      showToast(error.message || String(error));
    }
  });

  dictationButton.addEventListener("click", async () => {
    dictationButton.disabled = true;
    try {
      await window.pywebview.api.toggle_recording();
      await pollRuntime();
    } catch (error) {
      showToast(error.message || String(error));
    } finally {
      if (ui.runtime?.state !== "transcribing") dictationButton.disabled = false;
    }
  });

  copyLatest.addEventListener("click", async () => {
    if (await window.pywebview.api.copy_latest()) showToast("Transcript copied");
  });

  $("#choose-project").addEventListener("click", async () => {
    try {
      const selected = await window.pywebview.api.choose_project_folder();
      if (!selected) return;
      $("#project-path").value = selected;
      $("#project-term-status").textContent = "Save settings to scan this folder locally.";
    } catch (error) {
      showToast(error.message || String(error));
    }
  });

  $("#close-teach-dialog").addEventListener("click", closeTeachDialog);
  $("#cancel-teach").addEventListener("click", closeTeachDialog);
  $("#teach-dialog").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) closeTeachDialog();
  });
  $("#teach-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("#save-teach");
    const status = $("#teach-status");
    button.disabled = true;
    button.textContent = "Saving…";
    status.className = "";
    status.textContent = "Validating correction…";
    try {
      const vocabulary = await window.pywebview.api.teach_correction(
        $("#teach-alias").value,
        $("#teach-canonical").value,
      );
      renderVocabulary(vocabulary);
      closeTeachDialog();
      showToast("Correction learned");
    } catch (error) {
      status.className = "is-error";
      status.textContent = error.message || String(error);
    } finally {
      button.disabled = false;
      button.textContent = "Save correction";
    }
  });

  $("#clear-history").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    if (!ui.clearArmed) {
      ui.clearArmed = true;
      button.textContent = "Confirm clear";
      button.classList.add("is-confirming");
      setTimeout(() => {
        ui.clearArmed = false;
        button.textContent = "Clear history";
        button.classList.remove("is-confirming");
      }, 3500);
      return;
    }
    ui.clearArmed = false;
    await window.pywebview.api.clear_history();
    button.textContent = "Clear history";
    button.classList.remove("is-confirming");
    renderRuntime(await window.pywebview.api.get_runtime());
    await refreshHistory();
    showToast("History cleared");
  });

  $("#hide-to-background").addEventListener("click", async () => {
    await finishHotkeyCapture();
    await window.pywebview.api.hide_window();
  });

  $("#quit-app").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    if (!ui.quitArmed) {
      ui.quitArmed = true;
      button.textContent = "Confirm quit";
      button.classList.add("is-confirming");
      setTimeout(() => {
        ui.quitArmed = false;
        button.textContent = "Quit AgentWisper";
        button.classList.remove("is-confirming");
      }, 3500);
      return;
    }
    button.disabled = true;
    button.textContent = "Quitting…";
    await window.pywebview.api.quit_app();
  });

  $("#settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("#save-settings");
    const status = $("#save-status");
    button.disabled = true;
    button.textContent = "Saving…";
    status.className = "";
    status.textContent = "Validating settings…";
    try {
      const settings = await window.pywebview.api.save_settings(settingsPayload());
      ui.settings = settings;
      $("#hotkey").value = settings.hotkey;
      $("#hotkey-display").textContent = settings.hotkey_label;
      $("#groq-api-key").value = "";
      $("#custom-api-key").value = "";
      renderVocabulary(await window.pywebview.api.get_vocabulary());
      $("#groq-key-status").textContent = settings.groq_key_saved
        ? "API key saved · encrypted with Windows DPAPI."
        : "No API key saved · encrypted when added.";
      $("#custom-key-status").textContent = settings.custom_key_saved
        ? "API key saved · HTTPS required outside localhost."
        : "No API key saved · HTTPS required outside localhost.";
      status.className = "is-success";
      status.textContent = "Settings saved";
      showToast("Settings saved");
      await pollRuntime();
    } catch (error) {
      status.className = "is-error";
      status.textContent = error.message || String(error);
    } finally {
      button.disabled = false;
      button.textContent = "Save settings";
    }
  });

  window.addEventListener("pywebviewready", initialize, { once: true });
  new ResizeObserver(resizeCanvas).observe(canvas);
  requestAnimationFrame(drawSignal);
})();
