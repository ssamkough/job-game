const statusOrder = [
  "Interviewing",
  "Applied",
  "Not started",
  "Not Started",
  "Potential",
  "Submitted",
  "Archived",
  "Ended",
  "Denied",
  "Interviewed",
  "Re-apply",
  "Finding role...",
  "Unknown",
];

const formatDate = (value) => {
  if (!value) return "—";
  return value.slice(0, 10);
};

const listRows = (counts) => {
  return Object.entries(counts)
    .sort(
      (a, b) =>
        (statusOrder.indexOf(a[0]) === -1 ? 99 : statusOrder.indexOf(a[0])) -
        (statusOrder.indexOf(b[0]) === -1 ? 99 : statusOrder.indexOf(b[0]))
    )
    .map(([label, n]) => `<li>${label}: ${n}</li>`)
    .join("");
};

const fillSelect = (select, values) => {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
};

const render = (data) => {
  document.getElementById("generated").textContent =
    `Snapshot ${data.generatedOn}. Cutoff ${data.cutoff}. ${data.privacy}`;

  const stats = [
    ["Applications", data.totals.applications],
    ["Submitted", data.totals.applicationsSubmitted],
    ["Companies", data.totals.companiesThisSearch],
    ["Calls", data.totals.calls],
    ["Recruiter screens", data.totals.recruiterScreens],
    ["Referrals", data.totals.referrals],
  ];
  document.getElementById("stats").innerHTML = stats
    .map(
      ([label, n]) =>
        `<div><b>${n}</b><span>${label}</span></div>`
    )
    .join("");

  document.getElementById("live-bars").innerHTML = listRows(
    data.companyStatusThisSearch
  );
  document.getElementById("tagged-bars").innerHTML = listRows(
    data.companyStatusTagged
  );

  document.getElementById("call-kinds").textContent = Object.entries(
    data.callKinds
  )
    .map(([label, n]) => `${label}: ${n}`)
    .join(", ");

  document.getElementById("timeline").innerHTML = data.calls
    .map((call) => {
      const companies = call.companies.length
        ? call.companies.join(", ")
        : "Unlinked";
      return `<tr><td>${formatDate(call.date)}</td><td>${call.kind}</td><td>${companies}</td></tr>`;
    })
    .join("");

  document.getElementById("boards").textContent = Object.entries(
    data.applicationBoards
  )
    .map(([label, n]) => `${label}: ${n}`)
    .join(", ");

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

  const paintCompanies = () => {
    const value = companyFilter.value;
    const rows = data.companies.filter(
      (row) => value === "all" || row.status === value
    );
    document.getElementById("company-rows").innerHTML = rows
      .map(
        (row) => `<tr>
          <td>${row.alias}</td>
          <td>${row.status}</td>
          <td>${row.role || "—"}</td>
          <td>${row.callsThisSearch}</td>
          <td>${formatDate(row.firstInterviewOn)}</td>
        </tr>`
      )
      .join("");
  };

  const paintApps = () => {
    const value = appFilter.value;
    const rows = data.applications.filter(
      (row) => value === "all" || row.status === value
    );
    document.getElementById("app-rows").innerHTML = rows
      .map(
        (row) => `<tr>
          <td>${formatDate(row.submittedOn)}</td>
          <td>${row.companies.join(", ") || "—"}</td>
          <td>${row.status}</td>
          <td>${row.board}</td>
          <td>${row.referred ? "yes" : "no"}</td>
        </tr>`
      )
      .join("");
  };

  companyFilter.addEventListener("change", paintCompanies);
  appFilter.addEventListener("change", paintApps);
  paintCompanies();
  paintApps();
};

fetch("./data.json")
  .then((res) => res.json())
  .then(render)
  .catch((err) => {
    document.querySelector("p").textContent = `Could not load data.json: ${err}`;
  });
