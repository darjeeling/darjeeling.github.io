const state = {
  accounts: [],
  drafts: [],
  currentDraft: null,
  renders: [],
  selected: new Set(),
  saveTimers: new Map(),
  pendingEdits: new Map(),
  publishing: false,
  mentionBox: null,
};

const els = {
  accounts: document.querySelector("#social-accounts"),
  baseLang: document.querySelector("#social-base-lang"),
  baseText: document.querySelector("#social-base-text"),
  link: document.querySelector("#social-link"),
  draftId: document.querySelector("#social-draft-id"),
  draftList: document.querySelector("#social-drafts"),
  draftCount: document.querySelector("#social-draft-count"),
  renders: document.querySelector("#social-renders"),
  status: document.querySelector("#social-status"),
  results: document.querySelector("#social-results"),
  imageFile: document.querySelector("#social-image-file"),
  imageList: document.querySelector("#social-images"),
};

const buttons = {
  refreshAccounts: document.querySelector("#social-refresh-accounts"),
  newDraft: document.querySelector("#social-new-draft"),
  preview: document.querySelector("#social-preview"),
  confirm: document.querySelector("#social-confirm"),
  instagram: document.querySelector("#social-instagram"),
  sync: document.querySelector("#social-sync"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }
  return response.json();
}

function setStatus(message, level = "muted") {
  els.status.textContent = message || "";
  els.status.className = `status-line ${level}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

// --- accounts ---

const AUTH_LABELS = {
  ok: "ready",
  needs_auth: "authorize needed",
  expired: "expired",
  missing_secret: "no secret",
};

async function loadAccounts() {
  state.accounts = await request("/api/social/accounts");
  els.accounts.innerHTML = "";
  for (const account of state.accounts) {
    const chip = document.createElement("div");
    chip.className = `account-chip auth-${account.auth_status}`;
    chip.innerHTML = `
      <strong>${escapeHtml(account.id)}</strong>
      <span class="muted">${escapeHtml(account.lang)} · ${escapeHtml(AUTH_LABELS[account.auth_status])}</span>
    `;
    const needsOauth =
      ["threads", "linkedin"].includes(account.network) &&
      ["needs_auth", "expired"].includes(account.auth_status);
    if (needsOauth) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = account.auth_status === "expired" ? "Re-authorize" : "Authorize";
      button.addEventListener("click", () => withError(() => authorizeAccount(account)));
      chip.appendChild(button);
    }
    els.accounts.appendChild(chip);
  }
}

async function authorizeAccount(account) {
  if (account.network === "linkedin") {
    const response = await request(
      `/api/social/oauth/linkedin/start?account_id=${encodeURIComponent(account.id)}`,
    );
    window.open(response.url, "_blank", "noopener");
    setStatus("Complete the LinkedIn authorization in the new tab, then refresh accounts.");
    return;
  }
  // Threads: HTTPS redirect required, so the user pastes the redirected URL back
  const response = await request(
    `/api/social/oauth/threads/start?account_id=${encodeURIComponent(account.id)}`,
  );
  window.open(response.url, "_blank", "noopener");
  const pasted = window.prompt(
    `After authorizing, the browser lands on ${response.redirect_uri}?code=...\n` +
      "Copy that full URL from the address bar and paste it here:",
  );
  if (!pasted) return;
  await request("/api/social/oauth/threads/exchange", {
    method: "POST",
    body: JSON.stringify({ account_id: account.id, redirect_url: pasted.trim() }),
  });
  setStatus("Threads authorized");
  await loadAccounts();
}

function accountById(id) {
  return state.accounts.find((account) => account.id === id);
}

// --- drafts ---

async function loadDrafts() {
  state.drafts = await request("/api/social/drafts");
  els.draftCount.textContent = `${state.drafts.length} drafts`;
  els.draftList.innerHTML = "";
  for (const draft of state.drafts) {
    const wrapper = document.createElement("div");
    const active = state.currentDraft && draft.id === state.currentDraft.id;
    wrapper.className = `post-item${active ? " active" : ""}`;
    const button = document.createElement("button");
    button.type = "button";
    const firstLine = (draft.base_text || "(empty)").split("\n")[0].slice(0, 60);
    button.innerHTML = `
      <strong>${escapeHtml(firstLine)}</strong>
      <div class="muted">${escapeHtml(draft.base_lang)} · ${escapeHtml(draft.status)} · ${escapeHtml(draft.created_at.slice(0, 10))}</div>
    `;
    button.addEventListener("click", () => withError(() => selectDraft(draft.id)));
    wrapper.appendChild(button);
    els.draftList.appendChild(wrapper);
  }
}

function applyDraft(draft) {
  state.currentDraft = draft;
  els.draftId.textContent = draft ? `${draft.id} · ${draft.status}` : "";
  els.baseLang.value = draft?.base_lang || "ko";
  els.baseText.value = draft?.base_text || "";
  els.link.value = draft?.link || "";
  buttons.confirm.disabled = !draft || !state.renders.length;
  buttons.instagram.disabled = !draft;
  withError(renderImages);
}

async function selectDraft(draftId) {
  const draft = await request(`/api/social/drafts/${draftId}`);
  state.renders = await request(`/api/social/drafts/${draftId}/renders`);
  applyDraft(draft);
  defaultSelection();
  renderCards();
  await loadDrafts();
  setStatus("");
  els.results.innerHTML = "";
}

function resetCompose() {
  state.renders = [];
  state.selected = new Set();
  state.pendingEdits.clear();
  applyDraft(null);
  renderCards();
  els.results.innerHTML = "";
  setStatus("");
  els.baseText.focus();
}

function composePayload() {
  return {
    base_lang: els.baseLang.value,
    base_text: els.baseText.value,
    link: els.link.value || null,
  };
}

async function ensureDraftSaved() {
  if (state.currentDraft) {
    const draft = await request(`/api/social/drafts/${state.currentDraft.id}`, {
      method: "PUT",
      body: JSON.stringify(composePayload()),
    });
    state.currentDraft = draft;
    return draft;
  }
  const draft = await request("/api/social/drafts", {
    method: "POST",
    body: JSON.stringify(composePayload()),
  });
  applyDraft(draft);
  return draft;
}

// --- renders ---

function defaultSelection() {
  state.selected = new Set(
    state.renders
      .filter((render) => {
        const account = accountById(render.account_id);
        return account && account.mode === "api" && account.auth_status === "ok";
      })
      .map((render) => render.account_id),
  );
}

async function previewAll() {
  if (!els.baseText.value.trim()) {
    setStatus("Write something first.", "error");
    return;
  }
  const draft = await ensureDraftSaved();
  setStatus("Rendering previews (translation may take a moment)...");
  state.renders = await request(`/api/social/drafts/${draft.id}/render`, {
    method: "POST",
  });
  defaultSelection();
  renderCards();
  await loadDrafts();
  setStatus("Previews ready. Edit per network, then confirm to publish.");
}

function counterText(render) {
  return `${render.count} / ${render.limit}`;
}

function renderCards() {
  els.renders.innerHTML = "";
  for (const render of state.renders) {
    const account = accountById(render.account_id);
    if (!account) continue;
    const card = document.createElement("section");
    card.className = "card render-card";
    card.dataset.accountId = render.account_id;

    const badges = [];
    if (render.translated) badges.push('<span class="badge">translated</span>');
    if (!render.translated && render.lang !== (state.currentDraft?.base_lang || "ko")) {
      badges.push('<span class="badge badge-warn">untranslated</span>');
    }
    if (render.manually_edited) badges.push('<span class="badge">edited</span>');
    if (account.mode === "generate_only") badges.push('<span class="badge">manual post</span>');

    const selectable = account.mode === "api";
    const checked = state.selected.has(render.account_id) ? "checked" : "";
    card.innerHTML = `
      <div class="section-header">
        <label class="render-select">
          ${selectable ? `<input type="checkbox" data-select ${checked}>` : ""}
          <strong>${escapeHtml(account.id)}</strong>
        </label>
        <span class="render-counter ${render.over_limit ? "over" : ""}" data-counter>${counterText(render)}</span>
      </div>
      <div class="render-badges">${badges.join(" ")}</div>
      <textarea class="render-text" data-text rows="6" spellcheck="false">${escapeHtml(render.text)}</textarea>
      <p class="render-status muted" data-status></p>
    `;
    const textarea = card.querySelector("[data-text]");
    textarea.addEventListener("input", () => onRenderEdit(render.account_id, textarea, card));
    textarea.addEventListener("keyup", (event) => onMentionKey(event, render.account_id, textarea));
    const checkbox = card.querySelector("[data-select]");
    if (checkbox) {
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.selected.add(render.account_id);
        else state.selected.delete(render.account_id);
      });
    }
    els.renders.appendChild(card);
  }
  buttons.confirm.disabled = !state.renders.length || state.publishing;
}

function setCardStatus(accountId, html, level = "muted") {
  const card = els.renders.querySelector(`[data-account-id="${accountId}"]`);
  if (!card) return;
  const status = card.querySelector("[data-status]");
  status.innerHTML = html;
  status.className = `render-status ${level}`;
}

async function saveRenderText(accountId, text, card) {
  const updated = await request(
    `/api/social/drafts/${state.currentDraft.id}/renders/${accountId}`,
    { method: "PUT", body: JSON.stringify({ text }) },
  );
  state.pendingEdits.delete(accountId);
  const index = state.renders.findIndex((r) => r.account_id === accountId);
  if (index >= 0) state.renders[index] = updated;
  if (card) {
    const counter = card.querySelector("[data-counter]");
    counter.textContent = counterText(updated);
    counter.classList.toggle("over", updated.over_limit);
  }
  return updated;
}

function onRenderEdit(accountId, textarea, card) {
  state.pendingEdits.set(accountId, textarea.value);
  clearTimeout(state.saveTimers.get(accountId));
  state.saveTimers.set(
    accountId,
    window.setTimeout(async () => {
      try {
        await saveRenderText(accountId, textarea.value, card);
      } catch (error) {
        setStatus(error.message, "error");
      }
    }, 500),
  );
}

async function flushPendingEdits() {
  for (const [accountId, text] of [...state.pendingEdits]) {
    clearTimeout(state.saveTimers.get(accountId));
    const card = els.renders.querySelector(`[data-account-id="${accountId}"]`);
    await saveRenderText(accountId, text, card);
  }
}

// --- images ---

async function renderImages() {
  els.imageList.innerHTML = "";
  const draft = state.currentDraft;
  if (!draft || !draft.image_ids?.length) return;
  for (const imageId of draft.image_ids) {
    let meta;
    try {
      meta = await request(`/api/social/images/${imageId}/meta`);
    } catch {
      // draft synced from another device: the image stayed there
      const missing = document.createElement("div");
      missing.className = "image-item";
      missing.innerHTML = `<span class="muted">image ${escapeHtml(imageId)} is not on this device</span>`;
      els.imageList.appendChild(missing);
      continue;
    }
    const item = document.createElement("div");
    item.className = "image-item";
    const altLang = els.baseLang.value || "ko";
    const altValue = meta.alt_text[altLang] || "";
    item.innerHTML = `
      <img src="/api/social/images/${imageId}" alt="" class="image-thumb">
      <div class="image-meta">
        <span class="muted">${escapeHtml(meta.original_name)} · ${meta.width}x${meta.height} · ${Math.round(meta.bytes / 1024)}KB</span>
        <textarea data-alt rows="2" placeholder="alt text (${escapeHtml(altLang)})">${escapeHtml(altValue)}</textarea>
        <div class="toolbar">
          <button type="button" data-ai-alt>AI alt text</button>
          <button type="button" data-remove>Remove</button>
        </div>
      </div>
    `;
    const altArea = item.querySelector("[data-alt]");
    altArea.addEventListener("change", () =>
      withError(() =>
        request(`/api/social/images/${imageId}/alt-text`, {
          method: "PUT",
          body: JSON.stringify({ lang: els.baseLang.value, text: altArea.value }),
        }),
      ),
    );
    item.querySelector("[data-ai-alt]").addEventListener("click", () =>
      withError(async () => {
        setStatus("Generating alt text...");
        const updated = await request(
          `/api/social/images/${imageId}/alt-text?lang=${els.baseLang.value}`,
          { method: "POST" },
        );
        altArea.value = updated.alt_text[els.baseLang.value] || "";
        setStatus("Alt text ready");
      }),
    );
    item.querySelector("[data-remove]").addEventListener("click", () =>
      withError(async () => {
        const updated = await request(
          `/api/social/drafts/${draft.id}/images/${imageId}`,
          { method: "DELETE" },
        );
        state.currentDraft = updated;
        await renderImages();
      }),
    );
    els.imageList.appendChild(item);
  }
}

async function uploadImage(file) {
  await ensureDraftSaved();
  setStatus(`Uploading ${file.name}...`);
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(
    `/api/social/drafts/${state.currentDraft.id}/images`,
    { method: "POST", body: form },
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }
  state.currentDraft = await request(`/api/social/drafts/${state.currentDraft.id}`);
  await renderImages();
  setStatus("Image uploaded and optimized");
}

async function showInstagramPackage() {
  if (!state.currentDraft) return;
  const aspect = window.confirm("OK = portrait(1080x1350), Cancel = square(1080x1080)")
    ? "portrait"
    : "square";
  const pkg = await request(
    `/api/social/drafts/${state.currentDraft.id}/instagram-package?aspect=${aspect}`,
  );
  els.results.innerHTML = "";
  const card = document.createElement("div");
  card.className = "publish-result success instagram-package";
  const links = pkg.image_urls
    .map(
      (url, index) =>
        `<a href="${escapeHtml(url)}" download>image ${index + 1} (${escapeHtml(pkg.aspect)})</a>`,
    )
    .join(" · ");
  card.innerHTML = `
    <strong>Instagram (${escapeHtml(pkg.lang)})</strong>
    <pre class="instagram-caption">${escapeHtml(pkg.caption)}</pre>
    <div class="toolbar">
      <button type="button" data-copy>Copy caption</button>
      ${links ? `<span>${links}</span>` : '<span class="muted">no images</span>'}
    </div>
  `;
  card.querySelector("[data-copy]").addEventListener("click", () => {
    navigator.clipboard.writeText(pkg.caption);
    setStatus("Caption copied");
  });
  els.results.appendChild(card);
}

// --- mention autocomplete ---

function closeMentionBox() {
  if (state.mentionBox) {
    state.mentionBox.remove();
    state.mentionBox = null;
  }
}

let mentionTimer = null;
function onMentionKey(event, accountId, textarea) {
  if (["ArrowUp", "ArrowDown", "Enter", "Escape"].includes(event.key)) return;
  const account = accountById(accountId);
  if (!account) return;
  const upToCursor = textarea.value.slice(0, textarea.selectionStart);
  const match = upToCursor.match(/@([^\s@]{2,})$/);
  closeMentionBox();
  if (!match) return;
  clearTimeout(mentionTimer);
  mentionTimer = window.setTimeout(async () => {
    try {
      const people = await request(
        `/api/social/people/search?network=${account.network}&q=${encodeURIComponent(match[1])}`,
      );
      if (people.length) showMentionBox(people, account, textarea, match[1]);
    } catch {
      /* search failures shouldn't interrupt typing */
    }
  }, 300);
}

function showMentionBox(people, account, textarea, query) {
  closeMentionBox();
  const box = document.createElement("div");
  box.className = "mention-box";
  for (const person of people.slice(0, 8)) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "mention-item";
    item.innerHTML = `
      <strong>${escapeHtml(person.handle)}</strong>
      <span class="muted">${escapeHtml(person.display_name || "")}</span>
    `;
    item.addEventListener("click", () => {
      insertMention(textarea, query, person.handle);
      request("/api/social/people/used", {
        method: "POST",
        body: JSON.stringify({ network: person.network, handle: person.handle }),
      }).catch(() => {});
      closeMentionBox();
      textarea.dispatchEvent(new Event("input"));
      textarea.focus();
    });
    box.appendChild(item);
  }
  const rect = textarea.getBoundingClientRect();
  box.style.left = `${rect.left + window.scrollX}px`;
  box.style.top = `${rect.bottom + window.scrollY + 4}px`;
  box.style.minWidth = `${rect.width / 2}px`;
  document.body.appendChild(box);
  state.mentionBox = box;
}

function insertMention(textarea, query, handle) {
  const cursor = textarea.selectionStart;
  const before = textarea.value.slice(0, cursor).replace(
    new RegExp(`@${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`),
    handle.startsWith("@") ? handle : `@${handle}`,
  );
  textarea.value = before + " " + textarea.value.slice(cursor);
  const position = before.length + 1;
  textarea.setSelectionRange(position, position);
}

document.addEventListener("click", (event) => {
  if (state.mentionBox && !state.mentionBox.contains(event.target)) {
    closeMentionBox();
  }
});

// --- publish ---

async function confirmAndPublish() {
  if (!state.currentDraft || state.publishing) return;
  // preserve card order: publish in the order the previews are shown
  const accountIds = state.renders
    .map((render) => render.account_id)
    .filter((id) => state.selected.has(id));
  if (!accountIds.length) {
    setStatus("Select at least one account to publish.", "error");
    return;
  }
  const overLimit = state.renders.filter(
    (render) => accountIds.includes(render.account_id) && render.over_limit,
  );
  if (overLimit.length) {
    setStatus(
      `Over limit: ${overLimit.map((render) => render.account_id).join(", ")}`,
      "error",
    );
    return;
  }
  if (!window.confirm(`다음 순서로 포스팅합니다:\n\n${accountIds.join("\n")}\n\n진행할까요?`)) {
    return;
  }

  state.publishing = true;
  buttons.confirm.disabled = true;
  buttons.preview.disabled = true;
  try {
    await flushPendingEdits();
    let okCount = 0;
    for (const accountId of accountIds) {
      setCardStatus(accountId, "Posting...");
      try {
        const response = await request(
          `/api/social/drafts/${state.currentDraft.id}/publish`,
          { method: "POST", body: JSON.stringify({ account_ids: [accountId] }) },
        );
        const result = response.results[0];
        if (result.ok) {
          okCount += 1;
          const link = result.remote_url
            ? ` · <a href="${escapeHtml(result.remote_url)}" target="_blank" rel="noopener">view post</a>`
            : "";
          setCardStatus(accountId, `Posted${link}`, "success");
        } else {
          setCardStatus(accountId, escapeHtml(result.error || "failed"), "error");
        }
      } catch (error) {
        setCardStatus(accountId, escapeHtml(error.message), "error");
      }
    }
    setStatus(
      `Published ${okCount}/${accountIds.length}`,
      okCount === accountIds.length ? "success" : "error",
    );
  } finally {
    state.publishing = false;
    buttons.confirm.disabled = !state.renders.length;
    buttons.preview.disabled = false;
  }
  await loadDrafts();
}

// --- article hand-off (used by app.js via custom event) ---

window.addEventListener("social:crosspost", (event) => {
  withError(async () => {
    const detail = event.detail || {};
    const draft = await request("/api/social/drafts", {
      method: "POST",
      body: JSON.stringify({
        source: "article",
        article_path: detail.article_path || null,
        base_lang: detail.lang || "ko",
        base_text: detail.text || "",
        link: detail.link || null,
      }),
    });
    window.editorApp.switchView("social");
    state.renders = [];
    applyDraft(draft);
    renderCards();
    await loadDrafts();
    await previewAll();
  });
});

// --- wiring ---

function withError(action) {
  Promise.resolve()
    .then(action)
    .catch((error) => setStatus(error.message, "error"));
}

buttons.refreshAccounts.addEventListener("click", (event) => {
  // the button lives inside a <summary>: don't toggle the accounts panel
  event.preventDefault();
  event.stopPropagation();
  withError(loadAccounts);
});
buttons.newDraft.addEventListener("click", () => resetCompose());
buttons.preview.addEventListener("click", () => withError(previewAll));
buttons.confirm.addEventListener("click", () => withError(confirmAndPublish));
buttons.instagram.addEventListener("click", () => withError(showInstagramPackage));
buttons.sync.addEventListener("click", (event) => {
  // the button lives inside a <summary>: don't toggle the drafts panel
  event.preventDefault();
  event.stopPropagation();
  withError(async () => {
    const counts = await request("/api/social/sync", { method: "POST" });
    await loadDrafts();
    setStatus(
      `Sync done: ${counts.imported} imported, ${counts.exported} exported, ${counts.skipped} unchanged`,
      "success",
    );
  });
});
els.imageFile.addEventListener("change", () => {
  const file = els.imageFile.files?.[0];
  if (file) {
    withError(() => uploadImage(file));
    els.imageFile.value = "";
  }
});

withError(async () => {
  await loadAccounts();
  await loadDrafts();
});
