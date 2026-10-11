const prettyDate = (value) => {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
};

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const listBlock = (title, items, empty, render) => {
  if (!items.length) {
    return `<div class="related"><h3>${esc(title)}</h3><p>${esc(empty)}</p></div>`;
  }
  return `<div class="related"><h3>${esc(title)}</h3><ul>${items
    .map((item) => `<li>${render(item)}</li>`)
    .join("")}</ul></div>`;
};

const card = (company) => {
  const name = company.name || "Name missing from this snapshot";
  const apps = listBlock(
    "Applications",
    company.applications || [],
    "No related applications in the public log.",
    (row) => {
      const bits = [
        prettyDate(row.submittedOn),
        row.status,
        row.board,
        row.role,
        row.recruiter ? "recruiter" : "",
        row.referred ? "referral" : "",
      ].filter(Boolean);
      return esc(bits.join(" · "));
    }
  );
  const meetings = listBlock(
    "Meetings",
    company.meetings || [],
    "No related meetings in the public log.",
    (row) => esc(`${prettyDate(row.date)} · ${row.kind || "other"}`)
  );
  return `<article class="company-card" data-haystack="${esc(
    `${company.alias} ${name}`.toLowerCase()
  )}">
    <h2><span class="alias">${esc(company.alias)}</span> ${esc(name)}</h2>
    <p class="meta">${esc(company.status || "Unknown")}</p>
    ${apps}
    ${meetings}
  </article>`;
};

const render = (data) => {
  const snapshot = document.getElementById("snapshot");
  snapshot.dateTime = data.generatedOn;
  snapshot.textContent = prettyDate(data.generatedOn);

  const companies = data.companies || [];
  const ledger = document.getElementById("ledger");
  const count = document.getElementById("ledger-count");
  const search = document.getElementById("search");
  ledger.innerHTML = companies.map(card).join("");

  const paint = () => {
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    for (const node of ledger.querySelectorAll(".company-card")) {
      const on = !q || (node.dataset.haystack || "").includes(q);
      node.hidden = !on;
      if (on) shown += 1;
    }
    count.textContent =
      shown === 1 ? "1 company" : `${shown} companies`;
  };

  search.addEventListener("input", paint);
  paint();
};

fetch("./data.json")
  .then((res) => res.json())
  .then(render)
  .catch((err) => {
    const note = document.createElement("p");
    note.setAttribute("role", "alert");
    note.textContent = `Could not load hidden/data.json: ${err}`;
    document.querySelector("h1").after(note);
  });
