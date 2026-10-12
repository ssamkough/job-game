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

const listSection = (title, items) => {
  if (!items.length) {
    return `<section class="question-block">
      <h2>${esc(title)}</h2>
      <p>None in this snapshot.</p>
    </section>`;
  }
  return `<section class="question-block">
    <h2>${esc(title)}</h2>
    <ol class="question-list">
      ${items.map((item) => `<li>${esc(item)}</li>`).join("")}
    </ol>
  </section>`;
};

const technicalSection = (items) => {
  if (!items.length) {
    return `<section class="question-block">
      <h2>Technical</h2>
      <p>None in this snapshot.</p>
    </section>`;
  }
  return `<section class="question-block">
    <h2>Technical</h2>
    ${items
      .map((item, index) => {
        const title = item.title || `Prompt ${index + 1}`;
        const prompt = item.prompt || "";
        return `<article class="prompt">
          <h3>${esc(title)}</h3>
          <pre>${esc(prompt)}</pre>
        </article>`;
      })
      .join("")}
  </section>`;
};

const render = (data) => {
  const snapshot = document.getElementById("snapshot");
  snapshot.dateTime = data.generatedOn;
  snapshot.textContent = prettyDate(data.generatedOn);
  const questions = data.questions || {};
  const behavioral = questions.behavioral || [];
  const technical = questions.technical || [];
  document.getElementById("questions").innerHTML = [
    listSection("Behavioral", behavioral),
    technicalSection(technical),
  ].join("");
};

fetch("../data.json")
  .then((res) => res.json())
  .then(render)
  .catch((err) => {
    const note = document.createElement("p");
    note.setAttribute("role", "alert");
    note.textContent = `Could not load data.json: ${err}`;
    document.querySelector("h1").after(note);
  });
