"use strict";
(function () {
  const snapshot = window.QSOL_RESEARCH_SNAPSHOT;
  const grid = document.getElementById("records-grid");
  const empty = document.getElementById("empty-state");
  const report = document.getElementById("result-status");
  const input = document.getElementById("search");
  const system = document.getElementById("system");
  const status = document.getElementById("status");
  const safe = function (r) {
    return r && typeof r === "object" &&
      ["name", "system", "record_type", "status", "summary", "source_ref",
        "source_commit", "source_url", "last_verified"].every(function (key) {
        return typeof r[key] === "string";
      }) &&
      /^https:\/\/github\.com\/QSOLKCB\/[A-Za-z0-9._/-]+$/.test(r.source_url) &&
      r.source_url.slice("https://github.com/".length).split("/").every(function (s) {
        return s !== "" && s !== "." && s !== "..";
      });
  };
  if (!snapshot || snapshot.schema !== "qsol-nexus-public-observatory/1" ||
      !Array.isArray(snapshot.records) || snapshot.records.length > 200 ||
      !snapshot.records.every(safe)) {
    report.textContent = "Rejected: invalid public snapshot.";
    empty.textContent = "No trusted research snapshot is available.";
    return;
  }
  const records = snapshot.records;
  document.getElementById("count").textContent = String(records.length);
  document.getElementById("systems").textContent = String(new Set(records.map(function (r) {
    return r.system;
  })).size);
  const digest = snapshot.digest;
  document.getElementById("digest").textContent =
    typeof digest === "string" && /^sha256:[0-9a-f]{64}$/.test(digest)
      ? digest.slice(7, 19) + "…" : "NOT EXPORTED";
  function addOption(select, value) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  Array.from(new Set(records.map(function (r) { return r.system; }))).sort()
    .forEach(function (s) { addOption(system, s); });
  Array.from(new Set(records.map(function (r) { return r.status; }))).sort()
    .forEach(function (s) { addOption(status, s); });
  function detail(label, value) {
    const div = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value || "—";
    div.append(dt, dd);
    return div;
  }
  function createCard(r) {
    const article = document.createElement("article");
    article.className = "research-card";
    const meta = document.createElement("div");
    meta.className = "record-meta";
    meta.textContent = r.system + " / " + r.record_type + " / " + r.status;
    const heading = document.createElement("h3");
    heading.textContent = r.name;
    const summary = document.createElement("p");
    summary.textContent = r.summary;
    const dl = document.createElement("dl");
    dl.append(detail("SOURCE REF", r.source_ref), detail("COMMIT", r.source_commit),
      detail("LAST VERIFIED", r.last_verified));
    const link = document.createElement("a");
    link.href = r.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Inspect cited source ↗";
    article.append(meta, heading, summary, dl, link);
    return article;
  }
  function update() {
    const needle = input.value.trim().toLocaleLowerCase();
    const filtered = records.filter(function (r) {
      return (!system.value || r.system === system.value) &&
        (!status.value || r.status === status.value) &&
        (!needle || [r.name, r.summary, r.source_ref, r.system].join(" ")
          .toLocaleLowerCase().includes(needle));
    });
    grid.replaceChildren();
    filtered.forEach(function (r) { grid.appendChild(createCard(r)); });
    empty.hidden = filtered.length !== 0;
    empty.textContent = records.length ?
      "No records match the selected filters." :
      "Nothing is published yet. Private records remain private until explicitly approved and exported.";
    report.textContent = filtered.length + " of " + records.length + " public records (static)";
  }
  input.addEventListener("input", update);
  system.addEventListener("change", update);
  status.addEventListener("change", update);
  update();
})();
