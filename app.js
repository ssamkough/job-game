const PAGE_SIZE = 10;
const TABS = ["meetings", "applications", "companies"];

const formatDate = (value) => {
  if (!value) return "—";
  return value.slice(0, 10);
};

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

const fillSelect = (select, values) => {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
};

const paginator = (tbody, sentinel, countEl) => {
  const scroller = sentinel.closest(".table-wrap");
  let rows = [];
  let shown = 0;
  let pending = false;

  const paintCount = () => {
    if (!countEl) return;
    const n = rows.length;
    countEl.textContent = n === 1 ? "1 in total" : `${n} in total`;
  };

  const append = () => {
    if (pending || shown >= rows.length) {
      sentinel.hidden = shown >= rows.length || rows.length === 0;
      return;
    }
    const panel = tbody.closest(".panel");
    if (panel?.hidden) return;
    pending = true;
    const next = rows.slice(shown, shown + PAGE_SIZE);
    shown += next.length;
    tbody.insertAdjacentHTML("beforeend", next.join(""));
    sentinel.hidden = shown >= rows.length;
    pending = false;
  };

  const reset = (htmlRows) => {
    rows = htmlRows;
    shown = 0;
    tbody.replaceChildren();
    sentinel.hidden = rows.length === 0;
    scroller.scrollTop = 0;
    paintCount();
    append();
  };

  scroller.addEventListener("scroll", () => {
    if (
      scroller.scrollTop + scroller.clientHeight >=
      scroller.scrollHeight - 64
    ) {
      append();
    }
  });

  return { reset, append, fill: () => { if (shown === 0) append(); } };
};

const showTab = (name) => {
  const selected = TABS.includes(name) ? name : "meetings";
  for (const tab of TABS) {
    const button = document.getElementById(`tab-${tab}`);
    const panel = document.getElementById(`panel-${tab}`);
    const on = tab === selected;
    button.setAttribute("aria-selected", on ? "true" : "false");
    button.tabIndex = on ? 0 : -1;
    panel.hidden = !on;
  }
  if (location.hash.replace("#", "") !== selected) {
    history.replaceState(null, "", `#${selected}`);
  }
};

const render = (data) => {
  const meetings = data.meetings || data.calls || [];
  const meetingTotal = data.totals.meetings ?? data.totals.calls ?? 0;

  const started = document.getElementById("started");
  const snapshot = document.getElementById("snapshot");
  started.dateTime = data.cutoff;
  started.textContent = prettyDate(data.cutoff);
  snapshot.dateTime = data.generatedOn;
  snapshot.textContent = prettyDate(data.generatedOn);

  const stats = [
    ["Applications", data.totals.applications],
    ["Submitted", data.totals.applicationsSubmitted],
    ["Companies", data.totals.companiesThisSearch],
    ["Meetings", meetingTotal],
    ["Recruiter screens", data.totals.recruiterScreens],
    ["Referrals", data.totals.referrals],
  ];
  document.getElementById("stats").innerHTML = stats
    .map(([label, n]) => `<div><b>${n}</b><span>${label}</span></div>`)
    .join("");

  const companyFilter = document.getElementById("company-filter");
  const appFilter = document.getElementById("app-filter");
  fillSelect(
    companyFilter,
    [...new Set(data.companies.map((row) => row.status))].sort()
  );
  fillSelect(
    appFilter,
    [...new Set(data.applications.map((row) => row.status))].sort()
  );

  const meetingPages = paginator(
    document.getElementById("timeline"),
    document.querySelector('[data-for="timeline"]'),
    document.getElementById("meeting-count")
  );
  const appPages = paginator(
    document.getElementById("app-rows"),
    document.querySelector('[data-for="app-rows"]'),
    document.getElementById("app-count")
  );
  const companyPages = paginator(
    document.getElementById("company-rows"),
    document.querySelector('[data-for="company-rows"]'),
    document.getElementById("company-count")
  );

  meetingPages.reset(
    meetings.map((meeting) => {
      const companies = meeting.companies.length
        ? meeting.companies.join(", ")
        : "Unlinked";
      return `<tr><td>${formatDate(meeting.date)}</td><td>${meeting.kind}</td><td>${companies}</td></tr>`;
    })
  );

  const paintCompanies = () => {
    const value = companyFilter.value;
    const rows = data.companies.filter(
      (row) => value === "all" || row.status === value
    );
    companyPages.reset(
      rows.map(
        (row) => `<tr>
          <td>${row.alias}</td>
          <td>${row.status}</td>
          <td>${row.role || "—"}</td>
          <td>${row.meetingsThisSearch ?? row.callsThisSearch ?? 0}</td>
          <td>${formatDate(row.firstInterviewOn)}</td>
        </tr>`
      )
    );
  };

  const paintApps = () => {
    const value = appFilter.value;
    const rows = data.applications.filter(
      (row) => value === "all" || row.status === value
    );
    appPages.reset(
      rows.map(
        (row) => `<tr>
          <td>${formatDate(row.submittedOn)}</td>
          <td>${row.companies.join(", ") || "—"}</td>
          <td>${row.status}</td>
          <td>${row.board}</td>
          <td>${row.referred ? "yes" : "no"}</td>
        </tr>`
      )
    );
  };

  companyFilter.addEventListener("change", paintCompanies);
  appFilter.addEventListener("change", paintApps);
  paintCompanies();
  paintApps();

  const activate = (name) => {
    showTab(name);
    meetingPages.fill();
    appPages.fill();
    companyPages.fill();
  };
  document.querySelector(".tabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab]");
    if (button) activate(button.dataset.tab);
  });
  window.addEventListener("hashchange", () =>
    activate(location.hash.replace("#", ""))
  );
  activate(location.hash.replace("#", "") || "meetings");
};

fetch("./data.json")
  .then((res) => res.json())
  .then(render)
  .catch((err) => {
    document.querySelector("h1").insertAdjacentText(
      "afterend",
      ` Could not load data.json: ${err}`
    );
  });
