"use strict";

const $ = (id) => document.getElementById(id);

let backend = null;
let config = null;
const segments = {};
const dropdowns = {};

new QWebChannel(qt.webChannelTransport, (channel) => {
  backend = channel.objects.backend;
  backend.stateChanged.connect(onState);
  backend.themeChanged.connect((vars) => (document.documentElement.style.cssText = vars));
  backend.saveFailed.connect(showError);
  wireControls();
  backend.ready();
});

/**
 * A themed dropdown. A native <select> popup is drawn by the OS and ignores the palette, and
 * <datalist> filters its suggestions by what is already typed — which hid every model but one.
 */
function buildDropdown(hostId, options, value, { editable = false } = {}) {
  const host = document.getElementById(hostId);
  host.innerHTML = "";
  host.classList.add("dropdown");

  const field = document.createElement(editable ? "input" : "button");
  field.className = "control dd-field";
  if (editable) {
    field.type = "text";
    field.spellcheck = false;
    field.value = value;
  } else {
    field.type = "button";
    const label = options.find(([key]) => key === value);
    field.textContent = label ? label[1] : value;
  }
  host.appendChild(field);

  const chevron = document.createElement("button");
  chevron.type = "button";
  chevron.className = "dd-toggle";
  chevron.innerHTML = '<svg class="ic sm"><use href="#i-chevron"></use></svg>';
  host.appendChild(chevron);

  const list = document.createElement("div");
  list.className = "dd-list hidden";
  host.appendChild(list);

  const state = { value, options };
  dropdowns[hostId] = {
    get value() {
      return editable ? field.value.trim() : state.value;
    },
  };

  const close = () => list.classList.add("hidden");
  const open = () => {
    list.innerHTML = "";
    options.forEach(([key, label]) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "dd-item" + (key === state.value ? " active" : "");
      item.textContent = label;
      item.onclick = () => {
        state.value = key;
        if (editable) {
          field.value = key;
        } else {
          field.textContent = label;
        }
        close();
      };
      list.appendChild(item);
    });
    list.classList.remove("hidden");
  };

  const toggle = () => (list.classList.contains("hidden") ? open() : close());
  chevron.onclick = toggle;
  if (!editable) {
    field.onclick = toggle;
  } else {
    field.oninput = () => (state.value = field.value.trim());
  }
  host.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  document.addEventListener("click", (event) => {
    if (!host.contains(event.target)) close();
  });
}

function wireControls() {
  document.querySelectorAll(".nav-item[data-page]").forEach((item) => {
    item.onclick = () => {
      document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
      document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
      item.classList.add("active");
      $(`page-${item.dataset.page}`).classList.add("active");
    };
  });

  $("quit").onclick = () => backend.quitApp();
  $("cancel").onclick = () => backend.cancel();
  $("save").onclick = save;
  $("open-folder").onclick = () => backend.openHistoryFolder();
  $("toggle-key").onclick = () => {
    const field = $("api-key");
    const hidden = field.type === "password";
    field.type = hidden ? "text" : "password";
    $("toggle-key").textContent = hidden ? "Dölj" : "Visa";
  };
  $("hotkey").oninput = (event) => renderKeycaps(event.target.value);

  bindSwitch("auto-send");
  bindSwitch("save-history", (on) => setSwitch("save-history-2", on));
  bindSwitch("save-history-2", (on) => setSwitch("save-history", on));
}

function bindSwitch(id, onToggle) {
  $(id).onclick = () => {
    const on = !$(id).classList.contains("on");
    setSwitch(id, on);
    if (onToggle) onToggle(on);
  };
}

function setSwitch(id, on) {
  $(id).classList.toggle("on", on);
  $(id).setAttribute("aria-checked", String(on));
}

function buildSegmented(id, options, value, onPick) {
  const host = $(id);
  host.innerHTML = "";
  segments[id] = value;
  options.forEach(([key, label]) => {
    const button = document.createElement("button");
    button.textContent = label;
    button.classList.toggle("active", key === value);
    button.onclick = () => {
      segments[id] = key;
      host.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      if (onPick) onPick(key);
    };
    host.appendChild(button);
  });
}

function renderKeycaps(combo) {
  const host = $("keycaps");
  host.innerHTML = "";
  combo
    .split("+")
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((part) => {
      const cap = document.createElement("span");
      cap.className = "keycap";
      cap.textContent = part.charAt(0).toUpperCase() + part.slice(1);
      host.appendChild(cap);
    });
}

function onState(json) {
  const state = JSON.parse(json);
  config = state.config;
  document.documentElement.style.cssText = state.theme.vars;

  $("auto-question").value = config.autoSendQuestion;
  setSwitch("auto-send", config.autoSend);
  setSwitch("save-history", config.saveHistory);
  setSwitch("save-history-2", config.saveHistory);

  buildSegmented("detail", config.detailLevels, config.detailLevel);
  buildSegmented("theme", config.themeModes, config.themeMode, (mode) => backend.previewTheme(mode));
  buildDropdown("thinking", config.thinkingLevels, config.thinkingLevel);
  buildDropdown(
    "model",
    config.models.map((name) => [name, name]),
    config.model,
    { editable: true }
  );

  $("api-key").value = config.apiKey;
  const status = $("key-status");
  status.classList.toggle("connected", config.hasKey);
  status.textContent = config.hasKey ? "✓  Ansluten · sparad i .env" : "Ingen nyckel sparad ännu";

  $("hotkey").value = config.hotkey;
  renderKeycaps(config.hotkey);

  $("overlay-width").value = config.overlay.width;
  $("overlay-height").value = config.overlay.height;
  $("overlay-line").value = config.overlay.lineWidth;
  $("overlay-grab").value = config.overlay.grab;
  $("overlay-corner").value = config.overlay.corner;
  buildColorSwatches(config.overlay.colorPresets, config.overlay.color);
  $("history-path").textContent = `Sparas i ${config.historyPath}`;
}

function buildColorSwatches(presets, value) {
  const host = $("color-swatches");
  const hex = $("overlay-color");
  host.innerHTML = "";
  hex.value = value;

  const mark = (selected) => {
    host.querySelectorAll(".swatch").forEach((node) => {
      node.classList.toggle("active", node.dataset.value.toLowerCase() === selected.toLowerCase());
    });
  };

  presets.forEach((preset) => {
    const swatch = document.createElement("button");
    swatch.type = "button";
    swatch.className = "swatch" + (preset.value === "" ? " auto" : "");
    swatch.dataset.value = preset.value;
    swatch.title = preset.label;
    if (preset.value) swatch.style.background = preset.value;
    swatch.onclick = () => {
      hex.value = preset.value;
      mark(preset.value);
    };
    host.appendChild(swatch);
  });

  hex.oninput = () => mark(hex.value.trim());
  mark(value);
}

function save() {
  $("error").classList.add("hidden");
  backend.save(
    JSON.stringify({
      apiKey: $("api-key").value.trim(),
      model: dropdowns["model"].value,
      hotkey: $("hotkey").value.trim().toLowerCase(),
      autoSend: $("auto-send").classList.contains("on"),
      autoSendQuestion: $("auto-question").value.trim(),
      detailLevel: segments["detail"],
      thinkingLevel: dropdowns["thinking"].value,
      saveHistory: $("save-history").classList.contains("on"),
      themeMode: segments["theme"],
      overlay: {
        width: Number($("overlay-width").value),
        height: Number($("overlay-height").value),
        lineWidth: Number($("overlay-line").value),
        grab: Number($("overlay-grab").value),
        corner: Number($("overlay-corner").value),
        color: $("overlay-color").value,
      },
    })
  );
}

function showError(message) {
  const error = $("error");
  error.textContent = message;
  error.classList.remove("hidden");
}
