const $ = (id) => document.getElementById(id);
let voicePoll = null;

function api() {
  return window.pywebview && window.pywebview.api;
}

async function call(name, ...args) {
  const bridge = api();
  if (!bridge) throw new Error("Desktop bridge is not ready");
  return bridge[name](...args);
}

function fillSelect(id, items, selected, fallback) {
  const sel = $(id);
  if (!sel) return;
  sel.innerHTML = "";
  (items || []).forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.label || item.id;
    if (item.id === (selected || fallback)) opt.selected = true;
    sel.appendChild(opt);
  });
}

async function refresh() {
  const state = await call("state");
  $("hw").textContent = state.hw || "";
  fillSelect("speakVoice", state.voices, state.voice, "en-IN-NeerjaNeural");
  $("voiceStatus").textContent = state.cloned
    ? "Voices cloned. Name a new one and upload another sample anytime."
    : "No clone yet. Name the voice and upload 10–30 seconds of speech.";
  if (state.audio) {
    $("voicePlayer").src = state.audio;
    $("voicePath").textContent = state.audio_path || "";
  }
}

function setVoiceBusy(busy) {
  $("cloneBtn").disabled = busy;
  $("speakBtn").disabled = busy;
}

function voiceFx() {
  const speed = (Number($("voiceSpeed") && $("voiceSpeed").value) || 100) / 100;
  const pitch = Number($("voicePitch") && $("voicePitch").value) || 0;
  return { speed, pitch };
}

function syncFxLabels() {
  if (!$("speedVal") || !$("pitchVal")) return;
  const { speed, pitch } = voiceFx();
  $("speedVal").textContent = speed.toFixed(2) + "×";
  $("pitchVal").textContent = (pitch > 0 ? "+" : "") + pitch + " st";
}

async function pollVoiceJob() {
  if (voicePoll) clearInterval(voicePoll);
  voicePoll = setInterval(async () => {
    const job = await call("voice_job_status");
    $("voiceStatus").textContent = job.message || job.state;
    if (job.state === "cloned") {
      clearInterval(voicePoll);
      setVoiceBusy(false);
      await refresh();
      $("voiceStatus").textContent = job.message;
    }
    if (job.state === "done") {
      clearInterval(voicePoll);
      setVoiceBusy(false);
      $("voicePlayer").src = job.output + "?t=" + Date.now();
      $("voicePath").textContent = job.output_path || "";
      $("voiceStatus").textContent = "Voice ready.";
    }
    if (job.state === "error") {
      clearInterval(voicePoll);
      setVoiceBusy(false);
      $("voiceStatus").textContent = job.message || "Failed";
    }
  }, 400);
}

function cloneName() {
  return (($("cloneName") && $("cloneName").value) || "").trim();
}

async function pickVoice() {
  $("voiceStatus").textContent = "Cloning voice…";
  setVoiceBusy(true);
  const res = await call("pick_voice_sample", cloneName());
  if (res && res.error) {
    $("voiceStatus").textContent = res.error;
    setVoiceBusy(false);
    return;
  }
  if (!res || !res.ok) {
    setVoiceBusy(false);
    return;
  }
  await pollVoiceJob();
}

async function onVoiceFile(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    $("voiceStatus").textContent = "Cloning voice…";
    setVoiceBusy(true);
    const res = await call("import_voice_b64", file.name, reader.result, cloneName());
    if (res && res.error) {
      $("voiceStatus").textContent = res.error;
      setVoiceBusy(false);
      return;
    }
    await pollVoiceJob();
  };
  reader.readAsDataURL(file);
}

async function generateVoice() {
  const text = $("voiceScript").value.trim();
  if (!text) {
    $("voiceStatus").textContent = "Type the text you want spoken.";
    return;
  }
  $("voiceStatus").textContent = "Generating voice…";
  setVoiceBusy(true);
  const fx = voiceFx();
  const res = await call("start_speak", text, $("speakVoice").value, fx.speed, fx.pitch);
  if (res && res.error) {
    $("voiceStatus").textContent = res.error;
    setVoiceBusy(false);
    return;
  }
  await pollVoiceJob();
}

window.addEventListener("pywebviewready", refresh);
$("cloneBtn").addEventListener("click", pickVoice);
$("voiceInput").addEventListener("change", onVoiceFile);
$("speakBtn").addEventListener("click", generateVoice);
if ($("voiceSpeed")) $("voiceSpeed").addEventListener("input", syncFxLabels);
if ($("voicePitch")) $("voicePitch").addEventListener("input", syncFxLabels);
syncFxLabels();
setTimeout(refresh, 400);
