const $ = (id) => document.getElementById(id);
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));
const tidy = (s) => String(s == null ? "" : s).replace(/\s+/g, " ").trim();

let files = [];
const results = {};
const statuses = {};
const ticked = new Set();
let selected = null;
let viewerFile = null;
let instance = null;
let highlights = [];
let activeItemEl = null;
let busy = false;
let stopRequested = false;
let currentAbort = null;
let webSdkLicenseKey = "";  // empty = Web SDK evaluation mode

/* ---------------------------------------------------------------- init */

async function init() {
  try {
    files = await (await fetch("/api/files")).json();
    const cfg = await (await fetch("/api/config")).json();
    webSdkLicenseKey = cfg.web_sdk_license_key || "";
  } catch {
    toast("Could not reach the API.", true);
    return;
  }
  files.forEach((f) => (statuses[f.name] = "pending"));
  $("docCount").textContent = files.length;
  renderFileList();
}

function fmtPages(pages) {
  if (!pages) return "unknown length";
  return pages + (pages > 1 ? " pages" : " page");
}

function scoreOf(name) {
  const r = results[name];
  if (!r) return null;
  let yes = 0, total = 0;
  for (const c of r.checklists) { yes += c.found; total += c.total; }
  return { yes, total };
}

function renderFileList() {
  const list = $("fileList");
  list.innerHTML = "";
  for (const f of files) {
    const st = statuses[f.name];
    const card = document.createElement("div");
    card.className = "file-card" + (st === "done" ? " done" : "") + (selected === f.name ? " selected" : "");
    const sc = scoreOf(f.name);
    const labels = { pending: "Not reviewed", processing: "Reviewing", done: "Reviewed", error: "Error" };
    card.innerHTML = `
      <div class="pick-circle ${ticked.has(f.name) ? "on" : ""}" role="checkbox" aria-checked="${ticked.has(f.name)}">&#10003;</div>
      <div>
        <div class="fname">${esc(f.name)}</div>
        <div class="fmeta">
          <span>${fmtPages(f.pages)}</span>
          <span class="status-pill ${st}">${labels[st]}</span>
        </div>
        ${sc ? `<div class="fscore">Checklist: <b class="${sc.yes / sc.total >= 0.7 ? "good" : "poor"}">${sc.yes} YES</b> · ${sc.total - sc.yes} NO</div>` : ""}
      </div>
    `;
    const pick = card.querySelector(".pick-circle");
    pick.onclick = (e) => {
      e.stopPropagation();
      if (ticked.has(f.name)) ticked.delete(f.name); else ticked.add(f.name);
      updateReviewBtn();
      renderFileList();
    };
    if (st === "done") card.onclick = () => selectFile(f.name);
    list.appendChild(card);
  }
}

function updateReviewBtn() {
  const btn = $("reviewBtn");
  if (ticked.size) btn.textContent = `Review selected (${ticked.size})`;
  else btn.textContent = files.some((f) => statuses[f.name] === "done") ? "Review again" : "Review all documents";
}

/* ---------------------------------------------------------- processing */

async function reviewAll() {
  if (busy) return;
  busy = true;
  stopRequested = false;
  $("reviewBtn").disabled = true;
  $("stopBtn").hidden = false;
  $("stopBtn").disabled = false;
  $("progressTrack").hidden = false;
  $("progressLabel").hidden = false;

  const queue = ticked.size ? files.filter((f) => ticked.has(f.name)) : files.slice();
  const total = queue.length;
  let done = 0;
  let stopped = false;
  const t0 = Date.now();

  for (const f of queue) {
    if (stopRequested) { stopped = true; break; }
    statuses[f.name] = "processing";
    renderFileList();
    setProgress(done / total, `Reviewing ${f.name} (${done + 1} of ${total})`);

    const job = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
    const timer = setInterval(async () => {
      try {
        const p = await (await fetch(`/api/progress?job=${encodeURIComponent(job)}`)).json();
        if (!p.known) return;
        const frac = p.total ? p.done / p.total : 0;
        setProgress((done + Math.min(frac + 0.15, 0.9)) / total,
          `Reviewing ${f.name} (${done + 1} of ${total}) · ${p.stage}`);
      } catch { /* keep polling */ }
    }, 900);

    currentAbort = new AbortController();
    try {
      const res = await fetch(`/api/process?file=${encodeURIComponent(f.name)}&job=${encodeURIComponent(job)}`,
        { method: "POST", signal: currentAbort.signal });
      const data = await res.json();
      if (data.detail || data.error) throw new Error(data.detail || data.error);
      results[f.name] = data;
      statuses[f.name] = "done";
      done++;
      if (selected === f.name || !selected) selectFile(f.name);
    } catch (err) {
      if (err.name === "AbortError") {
        statuses[f.name] = "pending";
        stopped = true;
      } else {
        statuses[f.name] = "error";
        toast(`${f.name}: ${err.message}`, true);
        done++;
      }
    } finally {
      clearInterval(timer);
      currentAbort = null;
    }
    renderFileList();
    if (stopped) break;
    setProgress(done / total, `Reviewed ${done} of ${total}`);
  }

  const secs = Math.round((Date.now() - t0) / 1000);
  if (stopped) setProgress(done / total, `Stopped · ${done} of ${total} reviewed`);
  else setProgress(1, `Done · ${total} document${total > 1 ? "s" : ""} in ${secs >= 60 ? Math.floor(secs / 60) + "m " + (secs % 60) + "s" : secs + "s"}`);
  busy = false;
  stopRequested = false;
  $("reviewBtn").disabled = false;
  $("stopBtn").hidden = true;
  updateReviewBtn();
}

function stopRun() {
  if (!busy) return;
  stopRequested = true;
  $("stopBtn").disabled = true;
  $("progressLabel").textContent = "Stopping...";
  if (currentAbort) currentAbort.abort();
}

function setProgress(frac, label) {
  $("progressBar").style.width = Math.round(frac * 100) + "%";
  $("progressLabel").textContent = label;
}

/* -------------------------------------------------------------- review */

async function selectFile(name) {
  selected = name;
  renderFileList();
  renderReview(name);
  await openInViewer(name);
}

function confClass(c) { return c >= 80 ? "high" : c >= 55 ? "mid" : "low"; }

function renderReview(name) {
  const r = results[name];
  if (!r) {
    $("reviewEmpty").hidden = false;
    $("reviewBody").hidden = true;
    return;
  }
  $("reviewEmpty").hidden = true;
  const body = $("reviewBody");
  body.hidden = false;

  let html = `
    <div class="doc-title">
      <h2>${esc(name)}</h2>
      <p>Reviewed in ${r.processing_seconds}s · ${r.page_count} pages · click a YES item to see its evidence in the document${
        r.strikethrough_check && !r.strikethrough_check.active
          ? ` · <span class="warn" title="${esc(r.strikethrough_check.error || "")}">struck-through text check unavailable with this license</span>`
          : ""}</p>
    </div>
  `;
  for (const c of r.checklists) {
    const good = c.found / c.total >= 0.7;
    html += `
      <div class="check-card">
        <div class="check-head">
          <h3>${esc(c.label)}</h3>
          <span class="check-tally ${good ? "good" : "poor"}">${c.found} of ${c.total} YES</span>
        </div>
        ${c.items.map((it, i) => renderItem(c.key, it, i)).join("")}
      </div>
    `;
  }
  body.innerHTML = html;

  body.querySelectorAll(".check-item.clickable").forEach((el) => {
    el.onclick = () => {
      const item = r.checklists.find((c) => c.key === el.dataset.checklist).items[Number(el.dataset.idx)];
      if (activeItemEl) activeItemEl.classList.remove("active");
      el.classList.add("active");
      activeItemEl = el;
      showEvidence(name, item, r);
    };
  });
}

function renderItem(checklistKey, it, idx) {
  const yes = it.answer === "YES";
  const mark = `<div class="mark ${yes ? "yes" : "no"}">${yes ? "&#10003;" : "&#10005;"}</div>`;
  const conf = yes
    ? `<div class="conf"><div class="conf-num ${confClass(it.confidence)}">${it.confidence}%</div><div class="conf-cap">confidence</div></div>`
    : `<div class="conf"><div class="conf-num" style="color:var(--red)">NO</div></div>`;
  const detail = yes
    ? `<ul class="ievidence">${it.evidence.map((e) =>
        `<li><span class="iquote">${esc(tidy(e.text))}</span>${e.page ? `<span class="ipage">p. ${e.page}</span>` : ""}</li>`).join("")}</ul>`
    : `<div class="imissing">Not covered by this document</div>`;
  return `
    <div class="check-item ${yes && it.boxes.length ? "clickable" : ""}" data-checklist="${checklistKey}" data-idx="${idx}">
      ${mark}
      <div>
        <div class="ilabel">${esc(it.label)}</div>
        ${detail}
      </div>
      ${conf}
    </div>
  `;
}

/* -------------------------------------------------------------- viewer */

async function openInViewer(name) {
  if (viewerFile === name && instance) return;
  $("viewerEmpty").style.display = "none";
  if (instance) { PSPDFKit.unload("#viewer"); instance = null; }
  highlights = [];
  viewerFile = null;

  try {
    instance = await PSPDFKit.load({
      container: "#viewer",
      document: `/api/pdf?name=${encodeURIComponent(name)}`,
      // The Web SDK assets load from the CDN the script came from.
      licenseKey: webSdkLicenseKey || undefined,
    });
    viewerFile = name;
  } catch (err) {
    const empty = $("viewerEmpty");
    empty.style.display = "";
    empty.querySelector("h3").textContent = "Viewer unavailable";
    empty.querySelector("p").textContent =
      "The document viewer could not start in this environment. Open this page in Chrome, Safari or Edge.";
    toast(`Could not open the viewer: ${err.message}`, true);
  }
}

async function clearHighlights() {
  if (!instance || highlights.length === 0) return;
  try { await instance.delete(highlights); } catch { /* already gone */ }
  highlights = [];
}

// The backend returns exact source bounding boxes (in the extraction's page
// space) plus each page's dimensions in the same space, so highlights map to
// the viewer with a simple ratio: no text searching involved. Every quote of
// the item is highlighted, on whichever page it sits; the view jumps to the
// first one.
async function showEvidence(name, item, result) {
  await openInViewer(name);
  if (!instance || !item.boxes.length) return;

  const annotations = [];
  for (const b of item.boxes) {
    const pageIndex = (b.page || 1) - 1;
    const meta = (result.pages || []).find((p) => p.page === (b.page || 1));
    const info = meta && instance.pageInfoForIndex(pageIndex);
    if (!info) continue;
    const sx = info.width / meta.width;
    const sy = info.height / meta.height;
    const rect = new PSPDFKit.Geometry.Rect({
      left: b.x * sx,
      top: b.y * sy,
      width: b.width * sx,
      height: b.height * sy,
    });
    annotations.push(new PSPDFKit.Annotations.HighlightAnnotation({
      pageIndex,
      rects: PSPDFKit.Immutable.List([rect]),
      boundingBox: rect,
      color: new PSPDFKit.Color({ r: 255, g: 214, b: 0 }),
    }));
  }
  if (!annotations.length) { toast("No page geometry for this evidence.", true); return; }

  await clearHighlights();
  const firstPage = annotations[0].pageIndex;
  await instance.setViewState((vs) => vs.set("currentPageIndex", firstPage));
  instance.jumpToRect(firstPage, annotations[0].boundingBox);
  const created = await instance.create(annotations);
  highlights = created.map((a) => a.id);
}

/* --------------------------------------------------------------- toast */

let toastTimer = null;
function toast(msg, isError) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " error" : "");
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 5000);
}

$("reviewBtn").onclick = reviewAll;
$("stopBtn").onclick = stopRun;
init();
