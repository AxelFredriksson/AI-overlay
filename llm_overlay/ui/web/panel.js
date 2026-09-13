"use strict";

const $ = (id) => document.getElementById(id);

let backend = null;
let state = null;
let streamingAnswer = null;

const THEME_ICON = { light: "#i-sun", dark: "#i-moon", system: "#i-contrast" };

new QWebChannel(qt.webChannelTransport, (channel) => {
  backend = channel.objects.backend;
  backend.stateChanged.connect(onState);
  backend.chunkReceived.connect(onChunk);
  backend.historyLoaded.connect(renderHistory);
  wireControls();
  backend.ready();
});

function wireControls() {
  $("session-btn").onclick = () => backend.setView(state.view === "history" ? "transcript" : "history");
  $("new-btn").onclick = () => backend.newSession();
  $("theme-btn").onclick = () => backend.cycleTheme();
  $("close-btn").onclick = () => backend.closePanel();
  $("remove-image").onclick = () => backend.removeImage();
  $("open-settings").onclick = () => backend.openSettings();
  $("open-folder").onclick = (event) => {
    event.preventDefault();
    backend.openHistoryFolder();
  };
  $("search").oninput = (event) => backend.searchHistory(event.target.value);
  $("send").onclick = submit;
  const input = $("input");
  input.onkeydown = (event) => {
    if (event.key === "Enter") {
      submit();
    }
  };
  input.onfocus = () => $("pill").classList.add("focused");
  input.onblur = () => $("pill").classList.remove("focused");
}

function submit() {
  const input = $("input");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  backend.send(question);
}

// -- rendering --------------------------------------------------------------

function onState(json) {
  state = JSON.parse(json);
  document.documentElement.style.cssText = state.theme.vars;
  $("theme-icon").setAttribute("href", THEME_ICON[state.theme.mode] || "#i-contrast");
  $("theme-btn").title = `Tema: ${state.theme.label}`;

  $("session-title").textContent = state.sessionTitle;
  $("session-chevron").style.transform = state.view === "history" ? "rotate(180deg)" : "none";

  renderImageRow(state.image);
  renderTranscript(state);

  $("error-card").classList.toggle("hidden", state.hasBackend);
  $("composer").classList.toggle("hidden", !state.hasBackend);
  $("meta-left").textContent =
    `${state.meta.model} · detalj: ${state.meta.detail} · tänker: ${state.meta.thinking}`;
  $("meta-right").textContent = state.meta.hotkey;

  const showHistory = state.view === "history";
  $("history").classList.toggle("hidden", !showHistory);
  $("transcript").classList.toggle("hidden", showHistory);
  if (showHistory) {
    $("search").focus();
  }

  const input = $("input");
  input.disabled = state.streaming;
  $("send").disabled = state.streaming;
  if (!state.streaming && state.hasBackend && !showHistory) {
    input.focus();
  }
}

function renderImageRow(image) {
  const row = $("image-row");
  row.classList.toggle("hidden", !image);
  if (image) {
    $("image-thumb").src = image.thumbnail;
    $("image-meta").textContent = image.meta;
  }
}

function renderTranscript(state) {
  const container = $("transcript");
  container.innerHTML = "";
  streamingAnswer = null;

  if (state.messages.length === 0) {
    container.appendChild(emptyState(state.image !== null));
    return;
  }

  state.messages.forEach((message, index) => {
    const last = index === state.messages.length - 1;
    container.appendChild(
      message.role === "user"
        ? userBubble(message)
        : assistantBlock(message, last && state.streaming)
    );
  });
  scrollToBottom();
}

function emptyState(hasImage) {
  const wrap = document.createElement("div");
  wrap.className = "empty";
  wrap.innerHTML = `
    <div class="badge"><svg class="ic"><use href="#i-chat"></use></svg></div>
    <div>${
      hasImage
        ? "Fråga vad som helst. Skärmdumpen ovan följer med — ta bort den om frågan inte handlar om skärmen."
        : "Fråga vad som helst."
    }</div>`;
  return wrap;
}

function userBubble(message) {
  const node = document.createElement("div");
  node.className = "msg-user";
  node.innerHTML = message.html;
  return node;
}

function assistantBlock(message, streaming) {
  const node = document.createElement("div");
  node.className = streaming ? "msg-assistant streaming" : "msg-assistant";

  const caption = document.createElement("div");
  caption.className = "caption";
  caption.innerHTML = `<span class="dot"></span><span>${message.caption}</span>`;
  node.appendChild(caption);

  const answer = document.createElement("div");
  answer.className = "answer";
  answer.innerHTML = message.html + (streaming ? '<span class="cursor"></span>' : "");
  node.appendChild(answer);
  decorateCodeBlocks(answer);

  if (streaming) {
    streamingAnswer = answer;
    const stop = document.createElement("div");
    stop.className = "msg-actions";
    stop.innerHTML = '<button class="chip"><svg class="ic sm"><use href="#i-stop"></use></svg>Stoppa</button>';
    stop.firstElementChild.onclick = () => backend.stop();
    node.appendChild(stop);
  } else if (message.text) {
    node.appendChild(answerActions(message.text, message.canRegenerate));
  }
  return node;
}

function answerActions(text, canRegenerate) {
  const actions = document.createElement("div");
  actions.className = "msg-actions";

  const copy = document.createElement("button");
  copy.className = "chip";
  copy.innerHTML = '<svg class="ic sm"><use href="#i-copy"></use></svg>Kopiera';
  copy.onclick = () => {
    backend.copyText(text);
    copy.lastChild.textContent = "Kopierat";
    setTimeout(() => (copy.lastChild.textContent = "Kopiera"), 1200);
  };
  actions.appendChild(copy);

  if (canRegenerate) {
    const again = document.createElement("button");
    again.className = "chip";
    again.innerHTML = '<svg class="ic sm"><use href="#i-refresh"></use></svg>Svara igen';
    again.onclick = () => backend.regenerate();
    actions.appendChild(again);
  }
  return actions;
}

function decorateCodeBlocks(container) {
  container.querySelectorAll("pre.code-block").forEach((pre) => {
    const wrap = document.createElement("div");
    wrap.className = "code-wrap";
    const head = document.createElement("div");
    head.className = "code-head mono";
    head.innerHTML = `<span>${pre.dataset.lang || "kod"}</span>`;
    const copy = document.createElement("button");
    copy.className = "icon-btn sm";
    copy.innerHTML = '<svg class="ic sm"><use href="#i-copy"></use></svg>';
    copy.onclick = () => backend.copyText(pre.textContent);
    head.appendChild(copy);
    pre.replaceWith(wrap);
    wrap.appendChild(head);
    wrap.appendChild(pre);
  });
}

// -- streaming ---------------------------------------------------------------

function onChunk(html) {
  if (!streamingAnswer) return;
  streamingAnswer.innerHTML = html + '<span class="cursor"></span>';
  decorateCodeBlocks(streamingAnswer);
  scrollToBottom();
}

function scrollToBottom() {
  const container = $("transcript");
  container.scrollTop = container.scrollHeight;
}

// -- history -----------------------------------------------------------------

function renderHistory(json) {
  const data = JSON.parse(json);
  const list = $("history-list");
  list.innerHTML = "";

  if (data.groups.length === 0) {
    list.innerHTML = '<div class="history-empty">Inga sparade sessioner än.</div>';
  }

  data.groups.forEach((group) => {
    const label = document.createElement("div");
    label.className = "history-group";
    label.textContent = group.label;
    list.appendChild(label);

    group.items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "history-row";
      row.innerHTML = `
        <img src="${item.thumbnail}" alt="">
        <div class="text">
          <div class="title">${item.title}</div>
          <div class="meta">${item.time} · ${item.turns} ${item.turns === 1 ? "tur" : "turer"}</div>
        </div>`;
      row.onclick = () => backend.openSession(item.id);
      list.appendChild(row);
    });
  });

  $("history-count").textContent = `${data.total} sparade sessioner`;
}
