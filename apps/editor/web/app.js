const state = {
  config: null,
  posts: [],
  currentPath: null,
  currentDoc: null,
  previewRequestId: 0,
};

const els = {
  postList: document.querySelector("#post-list"),
  postCount: document.querySelector("#post-count"),
  currentPath: document.querySelector("#current-path"),
  configSummary: document.querySelector("#config-summary"),
  publishStatus: document.querySelector("#publish-status"),
  postKind: document.querySelector("#post-kind"),
  title: document.querySelector("#title"),
  date: document.querySelector("#date"),
  category: document.querySelector("#category"),
  slug: document.querySelector("#slug"),
  lang: document.querySelector("#lang"),
  tags: document.querySelector("#tags"),
  summary: document.querySelector("#summary"),
  translationKey: document.querySelector("#translation-key"),
  bodyMarkdown: document.querySelector("#body-markdown"),
  preview: document.querySelector("#preview"),
  aiStatus: document.querySelector("#ai-status"),
  aiResults: document.querySelector("#ai-results"),
  targetLang: document.querySelector("#target-lang"),
  createPostForm: document.querySelector("#create-post-form"),
};

const buttons = {
  save: document.querySelector("#save-post"),
  publish: document.querySelector("#publish-post"),
  unpublish: document.querySelector("#unpublish-post"),
  crosspost: document.querySelector("#crosspost-post"),
  refreshPosts: document.querySelector("#refresh-posts"),
  translate: document.querySelector("#translate-post"),
};

// --- views (Posts / Write / Social) ---

const VIEW_NAMES = ["posts", "editor", "social"];

function switchView(name) {
  document.querySelectorAll("#view-nav [data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  for (const view of VIEW_NAMES) {
    document.querySelector(`#view-${view}`).classList.toggle("hidden", view !== name);
  }
  window.scrollTo({ top: 0 });
}

window.editorApp = { switchView };

document.querySelectorAll("#view-nav [data-view]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

// "New post" from the editor: jump to the creation form in the Posts view
document.querySelector("#new-post-shortcut").addEventListener("click", () => {
  switchView("posts");
  const createCard = document.querySelector("#create-post-card");
  createCard.open = true;
  document.querySelector("#create-title").focus();
});

// --- write/preview toggle (mobile only; desktop shows both panes) ---

const workbench = document.querySelector("#editor-workbench");
document.querySelectorAll("#write-toggle [data-pane]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("#write-toggle [data-pane]").forEach((other) => {
      other.classList.toggle("active", other === button);
    });
    workbench.dataset.activePane = button.dataset.pane;
    if (button.dataset.pane === "preview") {
      schedulePreview(0);
    }
  });
});

const api = {
  async get(path) {
    const response = await fetch(path);
    return parseResponse(response);
  },
  async post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return parseResponse(response);
  },
  async put(path, body) {
    const response = await fetch(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return parseResponse(response);
  },
};

function parseResponse(response) {
  if (!response.ok) {
    return response.json().then((payload) => {
      throw new Error(payload.detail || response.statusText);
    });
  }
  return response.json();
}

function flash(message) {
  window.alert(message);
}

function setStatus(message, level = "muted") {
  els.publishStatus.textContent = message || "";
  els.publishStatus.className = `status-line ${level}`;
}

function currentPayload() {
  return {
    title: els.title.value,
    date: els.date.value,
    category: els.category.value,
    slug: els.slug.value,
    tags: els.tags.value.split(",").map((item) => item.trim()).filter(Boolean),
    lang: els.lang.value,
    summary: els.summary.value,
    translation_key: els.translationKey.value || null,
    translation_model: state.currentDoc?.translation_model || null,
    translation_at: state.currentDoc?.translation_at || null,
    translation_source_lang: state.currentDoc?.translation_source_lang || null,
    body_markdown: els.bodyMarkdown.value,
  };
}

function applyDocument(doc) {
  state.currentDoc = doc;
  state.currentPath = doc.path;
  els.currentPath.textContent = doc.path;
  els.postKind.textContent = doc.kind;
  els.title.value = doc.title || "";
  els.date.value = doc.date || "";
  els.category.value = doc.category || "blog";
  els.slug.value = doc.slug || "";
  els.lang.value = doc.lang || "ko";
  els.tags.value = (doc.tags || []).join(", ");
  els.summary.value = doc.summary || "";
  els.translationKey.value = doc.translation_key || "";
  els.bodyMarkdown.value = doc.body_markdown || "";
  buttons.save.disabled = false;
  buttons.publish.disabled = doc.kind !== "draft";
  buttons.unpublish.disabled = doc.kind !== "article";
  buttons.crosspost.disabled = doc.kind !== "article";
  buttons.translate.disabled = false;
}

function renderPosts() {
  els.postCount.textContent = `${state.posts.length} posts`;
  els.postList.innerHTML = "";
  for (const post of state.posts) {
    const wrapper = document.createElement("div");
    wrapper.className = `post-item${post.path === state.currentPath ? " active" : ""}`;
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = `
      <strong>${escapeHtml(post.title || post.slug || post.path)}</strong>
      <div class="muted">${escapeHtml(post.path)}</div>
      <div class="muted">${escapeHtml(post.lang)} · ${escapeHtml(post.kind)} · ${escapeHtml(post.date || "")}</div>
    `;
    button.addEventListener("click", () => loadPost(post.path));
    wrapper.appendChild(button);
    els.postList.appendChild(wrapper);
  }
}

function renderAiResults(values, applyValue) {
  els.aiResults.innerHTML = "";
  for (const value of values) {
    const button = document.createElement("button");
    button.className = "result-chip";
    button.type = "button";
    button.textContent = value;
    button.addEventListener("click", () => {
      applyValue(value);
      schedulePreview();
    });
    els.aiResults.appendChild(button);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderPreview(preview) {
  const payload = currentPayload();
  const title = payload.title || payload.slug || "Untitled draft";
  const metaParts = [payload.lang, payload.date, payload.category].filter(Boolean);
  const summary = payload.summary ? `<p class="preview-summary">${escapeHtml(payload.summary)}</p>` : "";
  els.preview.innerHTML = `
    <article class="preview-shell">
      <h1>${escapeHtml(title)}</h1>
      <div class="preview-meta">${escapeHtml(metaParts.join(" · "))}</div>
      ${summary}
      ${preview.body_html}
      ${preview.provenance_html || ""}
    </article>
  `;
}

async function loadConfig() {
  state.config = await api.get("/api/config");
  els.configSummary.textContent = state.config.ai_enabled
    ? `AI: ${state.config.openai_model}`
    : "AI off";
  els.aiStatus.textContent = state.config.ai_enabled
    ? `ready (${state.config.openai_model})`
    : "disabled: set OPENAI_API_KEY";
}

async function loadPosts() {
  state.posts = await api.get("/api/posts");
  renderPosts();
}

async function loadPost(path) {
  const doc = await api.get(postPath(path));
  applyDocument(doc);
  renderPosts();
  setStatus("");
  switchView("editor");
  schedulePreview(0);
}

async function refreshPreview() {
  if (!state.currentPath) {
    return;
  }
  const requestId = ++state.previewRequestId;
  const preview = await api.post(`${postPath(state.currentPath)}/preview`, currentPayload());
  if (requestId !== state.previewRequestId) {
    return;
  }
  renderPreview(preview);
}

async function saveCurrent({ refresh = true } = {}) {
  if (!state.currentPath) {
    return null;
  }
  const updated = await api.put(postPath(state.currentPath), currentPayload());
  applyDocument(updated);
  await loadPosts();
  if (refresh) {
    await refreshPreview();
  }
  setStatus(`Saved ${updated.path}`, "muted");
  return updated;
}

async function publishCurrent() {
  if (!state.currentPath) {
    return;
  }
  setStatus("Publishing with production build and git push...", "muted");
  await saveCurrent({ refresh: false });
  const response = await api.post(`${postPath(state.currentPath)}/publish`, {});
  applyDocument(response.document);
  await loadPosts();
  await refreshPreview();
  setStatus(`Published ${response.document.path} · ${response.commit_sha.slice(0, 7)}`, "success");
  flash(`Published and pushed.\n\n${response.commit_summary}`);
}

async function unpublishCurrent() {
  if (!state.currentPath) {
    return;
  }
  const updated = await api.post(`${postPath(state.currentPath)}/unpublish`, {});
  applyDocument(updated);
  await loadPosts();
  await refreshPreview();
  setStatus(`Moved back to draft: ${updated.path}`, "muted");
}

function crosspostCurrent() {
  const doc = state.currentDoc;
  if (!doc || doc.kind !== "article") {
    flash("Publish the post first, then cross-post.");
    return;
  }
  const payload = currentPayload();
  const link = `https://iz4u.net/${payload.slug}-${payload.lang}.html`;
  const text = [payload.title, payload.summary].filter(Boolean).join("\n\n");
  window.dispatchEvent(
    new CustomEvent("social:crosspost", {
      detail: {
        article_path: state.currentPath,
        lang: payload.lang,
        text,
        link,
      },
    }),
  );
}

async function createDraft(event) {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const created = await api.post("/api/posts", {
    title: form.get("title"),
    lang: form.get("lang"),
    category: form.get("category"),
  });
  await loadPosts();
  applyDocument(created);
  formElement.reset();
  document.querySelector("#create-category").value = "blog";
  setStatus(`Created ${created.path}`, "muted");
  switchView("editor");
  schedulePreview(0);
}

async function runAiAction(action) {
  if (!state.currentDoc) {
    flash("Load a post first.");
    return;
  }
  const endpoint = `/api/ai/${action}`;
  const document = { ...state.currentDoc, ...currentPayload(), path: state.currentPath };
  const response = await api.post(endpoint, document);
  if (response.values) {
    const applyTarget = {
      title: (value) => {
        els.title.value = value;
      },
      tags: (value) => {
        const current = els.tags.value.split(",").map((item) => item.trim()).filter(Boolean);
        if (!current.includes(value)) {
          current.push(value);
        }
        els.tags.value = current.join(", ");
      },
    };
    renderAiResults(response.values, applyTarget[action]);
    return;
  }
  if (response.value) {
    if (action === "slug") {
      els.slug.value = response.value;
    }
    if (action === "summary") {
      els.summary.value = response.value;
    }
    renderAiResults([response.value], (value) => {
      if (action === "slug") {
        els.slug.value = value;
      } else {
        els.summary.value = value;
      }
    });
  }
}

async function translateCurrent() {
  if (!state.currentPath) {
    flash("Save the source post before translating.");
    return;
  }
  await saveCurrent();
  const translated = await api.post("/api/ai/translate", {
    source_path: state.currentPath,
    target_lang: els.targetLang.value,
  });
  await loadPosts();
  applyDocument(translated);
  setStatus(`Created translation draft: ${translated.path}`, "success");
  await refreshPreview();
}

function postPath(path) {
  return `/api/posts/${encodeURIComponent(path).replaceAll("%2F", "/")}`;
}

let previewTimer = null;
function schedulePreview(delay = 350) {
  clearTimeout(previewTimer);
  previewTimer = window.setTimeout(() => withError(refreshPreview), delay);
}

function withError(action) {
  Promise.resolve()
    .then(action)
    .catch((error) => {
      setStatus(error.message, "error");
      flash(error.message);
    });
}

buttons.refreshPosts.addEventListener("click", () => withError(loadPosts));
buttons.save.addEventListener("click", () => withError(() => saveCurrent()));
buttons.publish.addEventListener("click", () => withError(publishCurrent));
buttons.unpublish.addEventListener("click", () => withError(unpublishCurrent));
buttons.crosspost.addEventListener("click", () => withError(crosspostCurrent));
buttons.translate.addEventListener("click", () => withError(translateCurrent));
els.createPostForm.addEventListener("submit", (event) => withError(() => createDraft(event)));

document.querySelectorAll("[data-ai-action]").forEach((button) => {
  button.addEventListener("click", () => withError(() => runAiAction(button.dataset.aiAction)));
});

[
  els.title,
  els.date,
  els.category,
  els.slug,
  els.lang,
  els.tags,
  els.summary,
  els.translationKey,
  els.bodyMarkdown,
].forEach((element) => {
  element.addEventListener("input", () => schedulePreview());
  element.addEventListener("change", () => schedulePreview());
});

async function bootstrap() {
  await loadConfig();
  await loadPosts();
}

withError(bootstrap);
