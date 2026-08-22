(() => {
  "use strict";

  const node = document.querySelector("#signal-node");
  const title = document.querySelector("#title");
  const detail = document.querySelector("#detail");
  const bars = document.querySelector("#level-bars");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const visual = Array(18).fill(0);
  let snapshot = { state: "idle", levels: [] };
  let lastState = "";

  for (let index = 0; index < visual.length; index += 1) {
    bars.append(document.createElement("i"));
  }

  function copyFor(runtime) {
    const hotkey = runtime.hotkey_label || "Right Ctrl";
    const words = Number(runtime.word_count || 0);
    return {
      idle: ["Ready", `Hold ${hotkey}`],
      listening: [`Listening  ${formatDuration(runtime.recording_seconds)}`, `Release ${hotkey}`],
      transcribing: ["Processing", runtime.detail || "Turning speech into text"],
      success: [runtime.pasted ? "Pasted" : "Transcript ready", `${words} word${words === 1 ? "" : "s"} saved`],
      error: ["Needs attention", runtime.detail || "Open AgentWisper"],
      notice: ["Running in background", runtime.detail || `Hold ${hotkey} to dictate`],
    }[runtime.state] || ["Ready", `Hold ${hotkey}`];
  }

  function formatDuration(seconds) {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
  }

  function renderState() {
    const state = snapshot.state || "idle";
    if (state !== lastState) {
      node.className = `signal-node state-${state}`;
      node.setAttribute("aria-label", state === "listening" ? "Finish dictation" : "Start dictation");
      lastState = state;
    }
    const copy = copyFor(snapshot);
    title.textContent = copy[0];
    detail.textContent = copy[1];
  }

  function animate() {
    const levels = Array.isArray(snapshot.levels) ? snapshot.levels : [];
    const fallback = Number(snapshot.level || 0);
    [...bars.children].forEach((bar, index) => {
      const target = snapshot.state === "listening" ? Number(levels[index] ?? fallback) : 0;
      visual[index] += (target - visual[index]) * (target > visual[index] ? 0.5 : 0.2);
      const level = reduceMotion ? Math.max(.12, target) : Math.max(.12, visual[index]);
      bar.style.setProperty("--level", String(level));
    });
    const pulse = 1 + Math.max(0, Number(snapshot.level || 0)) * 0.18;
    node.style.setProperty("--pulse", String(reduceMotion ? 1 : pulse));
    renderState();
    requestAnimationFrame(animate);
  }

  async function poll() {
    try {
      snapshot = await window.pywebview.api.get_snapshot();
    } catch (_error) {
      return;
    }
    setTimeout(poll, snapshot.state === "listening" ? 48 : 110);
  }

  node.addEventListener("click", () => window.pywebview.api.toggle());
  node.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    window.pywebview.api.open_app();
  });
  window.addEventListener("pywebviewready", () => {
    poll();
    animate();
  });
})();
