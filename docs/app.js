const state = {
  terms: [], templates: [], mappings: [], view: "terms", visible: 48,
  query: "", module: "", category: "", image: ""
};

const $ = (selector) => document.querySelector(selector);
const grid = $("#content-grid");
const searchInput = $("#search");
const heroSearch = $("#hero-search");
const moduleFilter = $("#module-filter");
const categoryFilter = $("#category-filter");
const imageFilter = $("#image-filter");
const loadMore = $("#load-more");
const dialog = $("#term-dialog");
const dialogContent = $("#dialog-content");
const toast = $("#toast");

const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const normalize = (value = "") => String(value).toLocaleLowerCase().normalize("NFKC");

async function loadData() {
  const [terms, templates, mappings] = await Promise.all([
    fetch("data/terms.json").then(r => r.json()),
    fetch("data/prompt-templates.json").then(r => r.json()),
    fetch("data/abstract-mappings.json").then(r => r.json())
  ]);
  Object.assign(state, {terms, templates, mappings});
  populateModules();
  render();
  openHashTerm();
}

function populateModules() {
  const modules = [...new Set(state.terms.map(term => term.module))];
  moduleFilter.insertAdjacentHTML("beforeend", modules.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join(""));
  populateCategories();
}

function populateCategories() {
  const current = categoryFilter.value;
  const categories = [...new Set(state.terms.filter(t => !state.module || t.module === state.module).map(t => t.category))];
  categoryFilter.innerHTML = `<option value="">全部分类</option>${categories.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("")}`;
  if (categories.includes(current)) categoryFilter.value = current;
}

function matchingTerms() {
  const q = normalize(state.query);
  return state.terms.filter(term => {
    const status = term.image?.status || "none";
    const haystack = normalize([term.nameZh, term.nameEn, term.module, term.category, term.plainExplanation, term.promptExample, term.commonPairings].join(" "));
    return (!q || haystack.includes(q)) && (!state.module || term.module === state.module) && (!state.category || term.category === state.category) && (!state.image || status === state.image);
  });
}

function termCard(term) {
  const visual = term.image
    ? `<div class="card-visual"><img loading="lazy" src="${escapeHtml(term.image.path)}" alt="${escapeHtml(term.image.altZh)}"><span class="image-status">${term.image.status === "available" ? `抽象视觉 #${term.abstractIndex}` : "图片待补"}</span></div>`
    : `<div class="card-visual text-only" aria-hidden="true">${escapeHtml(term.nameEn.slice(0, 2).toUpperCase())}</div>`;
  return `<article class="term-card"><button class="card-open" data-term-id="${term.id}" aria-label="查看 ${escapeHtml(term.nameZh)} 详情">${visual}<div class="card-body"><div class="card-meta"><span>${escapeHtml(term.module)}</span><span>${escapeHtml(term.id)}</span></div><h3>${escapeHtml(term.nameZh)}<small>${escapeHtml(term.nameEn)}</small></h3><p>${escapeHtml(term.plainExplanation)}</p></div></button></article>`;
}

function templateCard(item) {
  return `<article class="template-card"><span class="data-label">${escapeHtml(item.type)} · ${escapeHtml(item.useCase)}</span><h3>${escapeHtml(item.name)}</h3><div class="data-row"><strong>推荐结构</strong><p>${escapeHtml(item.recommendedStructure)}</p></div><div class="data-row"><strong>直接复制示例</strong><p>${escapeHtml(item.copyReadyExample)}</p></div><button class="copy-inline" data-copy="${escapeHtml(item.copyReadyExample)}">复制示例</button></article>`;
}

function mappingCard(item) {
  return `<article class="mapping-card"><span class="data-label">${escapeHtml(item.id)}</span><h3>${escapeHtml(item.concept)}</h3><p>${escapeHtml(item.plainExplanation)}</p><div class="data-row"><strong>常用视觉载体</strong><p>${escapeHtml(item.visualCarrier)}</p></div><div class="data-row"><strong>核心动作</strong><p>${escapeHtml(item.coreAction)}</p></div><div class="data-row"><strong>提示词示例</strong><p>${escapeHtml(item.promptExample)}</p></div><button class="copy-inline" data-copy="${escapeHtml(item.promptExample)}">复制提示词</button></article>`;
}

function render() {
  const filters = $("#term-filters");
  if (state.view === "terms") {
    filters.hidden = false;
    const matches = matchingTerms();
    const visible = matches.slice(0, state.visible);
    grid.innerHTML = visible.length ? visible.map(termCard).join("") : `<div class="empty-state"><h3>没有找到匹配词条</h3><p>换一个关键词，或清除筛选后再试。</p></div>`;
    $("#result-count").textContent = `找到 ${matches.length} 个词条 · 当前显示 ${visible.length} 个`;
    loadMore.hidden = visible.length >= matches.length;
  } else if (state.view === "templates") {
    filters.hidden = true;
    grid.innerHTML = state.templates.map(templateCard).join("");
    $("#result-count").textContent = `共 ${state.templates.length} 个提示词模板`;
    loadMore.hidden = true;
  } else {
    filters.hidden = true;
    grid.innerHTML = state.mappings.map(mappingCard).join("");
    $("#result-count").textContent = `共 ${state.mappings.length} 个抽象意象映射`;
    loadMore.hidden = true;
  }
}

function openTerm(id, updateHash = true) {
  const term = state.terms.find(item => item.id === id);
  if (!term) return;
  const image = term.image ? `<img class="dialog-hero" src="${escapeHtml(term.image.path)}" alt="${escapeHtml(term.image.altZh)}">` : "";
  dialogContent.innerHTML = `${image}<div class="dialog-body"><span class="data-label">${escapeHtml(term.module)} · ${escapeHtml(term.category)} · ${escapeHtml(term.id)}</span><h2 id="dialog-title">${escapeHtml(term.nameZh)}<small>${escapeHtml(term.nameEn)}</small></h2><div class="dialog-grid"><section class="dialog-panel"><h3>一句大白话解释</h3><p>${escapeHtml(term.plainExplanation)}</p></section><section class="dialog-panel"><h3>常见搭配</h3><p>${escapeHtml(term.commonPairings)}</p></section><section class="dialog-panel full"><h3>AI 提示词示例</h3><p>${escapeHtml(term.promptExample)}</p><button class="dialog-copy" data-copy="${escapeHtml(term.promptExample)}">复制提示词</button></section></div><div class="dialog-footer"><span>${term.abstractIndex ? `抽象视觉编号 #${term.abstractIndex}` : "双语视觉词条"}</span><span>CC BY 4.0</span></div></div>`;
  if (!dialog.open) dialog.showModal();
  if (updateHash) history.pushState(null, "", `#${term.id}`);
}

function closeDialog(updateHash = true) {
  if (dialog.open) dialog.close();
  if (updateHash && location.hash.startsWith("#AVL-")) history.replaceState(null, "", location.pathname + location.search + "#library");
}

function openHashTerm() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (id.startsWith("AVL-")) openTerm(id, false);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text; document.body.append(area); area.select(); document.execCommand("copy"); area.remove();
  }
  toast.textContent = "已复制到剪贴板";
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1500);
}

document.addEventListener("click", event => {
  const card = event.target.closest("[data-term-id]");
  if (card) openTerm(card.dataset.termId);
  const copy = event.target.closest("[data-copy]");
  if (copy) copyText(copy.dataset.copy);
});

$("#hero-search-form").addEventListener("submit", event => {
  event.preventDefault(); state.view = "terms"; state.query = heroSearch.value.trim(); searchInput.value = state.query; state.visible = 48;
  document.querySelectorAll(".view-tab").forEach(button => { const active = button.dataset.view === "terms"; button.classList.toggle("active", active); button.setAttribute("aria-selected", active); });
  render(); $("#library").scrollIntoView();
});

searchInput.addEventListener("input", event => { state.query = event.target.value.trim(); state.visible = 48; render(); });
moduleFilter.addEventListener("change", event => { state.module = event.target.value; state.category = ""; populateCategories(); state.visible = 48; render(); });
categoryFilter.addEventListener("change", event => { state.category = event.target.value; state.visible = 48; render(); });
imageFilter.addEventListener("change", event => { state.image = event.target.value; state.visible = 48; render(); });
$("#reset-filters").addEventListener("click", () => { Object.assign(state, {query:"", module:"", category:"", image:"", visible:48}); searchInput.value = ""; moduleFilter.value = ""; imageFilter.value = ""; populateCategories(); render(); });
loadMore.addEventListener("click", () => { state.visible += 48; render(); });
document.querySelectorAll(".view-tab").forEach(button => button.addEventListener("click", () => { state.view = button.dataset.view; button.parentElement.querySelectorAll(".view-tab").forEach(item => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-selected", active); }); render(); }));
$("#dialog-close").addEventListener("click", () => closeDialog());
dialog.addEventListener("click", event => { if (event.target === dialog) closeDialog(); });
dialog.addEventListener("cancel", event => { event.preventDefault(); closeDialog(); });
window.addEventListener("hashchange", openHashTerm);

loadData().catch(error => {
  console.error(error);
  grid.innerHTML = `<div class="empty-state"><h3>数据载入失败</h3><p>请刷新页面，或前往 GitHub 下载数据文件。</p></div>`;
  $("#result-count").textContent = "暂时无法载入词条";
});
