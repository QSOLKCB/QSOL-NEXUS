"use strict";

// Public projection only. Never call the NEXUS / CONTROL / ORACLE control planes.
const PHI_STRIDE = 17;
const CELL_COUNT = 27;
const informationRoles = ["question", "response", "evidence"];
const epistemicRoles = ["observed", "derived", "unresolved"];
const temporalRoles = ["current", "historical", "recovery"];

const filter = document.getElementById("system-filter");
const cards = Array.from(document.querySelectorAll("[data-system]"));
const filterStatus = document.getElementById("filter-status");
const empty = document.getElementById("no-results");
function filterSystems() {
  const needle = filter.value.toLocaleLowerCase().trim();
  let visible = 0;
  cards.forEach(function (card) {
    const show = card.textContent.toLocaleLowerCase().includes(needle);
    card.hidden = !show;
    if (show) visible += 1;
  });
  filterStatus.textContent = String(visible) + " of " + String(cards.length) + " systems shown";
  empty.hidden = visible !== 0;
}
filter.addEventListener("input", filterSystems);

// Match LATTICE's reference implementation: for x, for y, for z.
// Lexicographic index = x*9 + y*3 + z; phi index = (step*17) mod 27.
// The inverse of 17 modulo 27 is 8, allowing click-to-step navigation.
const cells = [];
for (let x = 0; x < 3; x += 1) {
  for (let y = 0; y < 3; y += 1) {
    for (let z = 0; z < 3; z += 1) {
      cells.push({x: x, y: y, z: z, address: "L[" + x + "," + y + "," + z + "]"});
    }
  }
}
const grid = document.getElementById("lattice-grid");
const buttons = [];
for (let x = 0; x < 3; x += 1) {
  const pane = document.createElement("section");
  pane.className = "lattice-pane";
  const heading = document.createElement("h3");
  heading.textContent = "X" + String(x) + " / " + informationRoles[x].toUpperCase();
  pane.appendChild(heading);
  const panel = document.createElement("div");
  panel.className = "lattice-cells";
  for (let y = 0; y < 3; y += 1) {
    for (let z = 0; z < 3; z += 1) {
      const index = x * 9 + y * 3 + z;
      const cell = cells[index];
      const button = document.createElement("button");
      button.type = "button";
      button.className = "lattice-cell";
      button.textContent = String(y) + "," + String(z);
      button.setAttribute("aria-label", cell.address + " / " + epistemicRoles[y] + " / " + temporalRoles[z]);
      button.addEventListener("click", function () {
        step = traversal === "phi" ? (index * 8) % CELL_COUNT : index;
        update();
      });
      panel.appendChild(button);
      buttons[index] = button;
    }
  }
  pane.appendChild(panel);
  grid.appendChild(pane);
}
const phiButton = document.getElementById("phi-mode");
const lexButton = document.getElementById("lex-mode");
let traversal = "phi";
let step = 0;
function update() {
  const index = traversal === "phi" ? (step * PHI_STRIDE) % CELL_COUNT : step;
  const cell = cells[index];
  buttons.forEach(function (button, i) {
    const selected = i === index;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  document.getElementById("selected-address").textContent = cell.address;
  document.getElementById("axis-x").textContent = informationRoles[cell.x];
  document.getElementById("axis-y").textContent = epistemicRoles[cell.y];
  document.getElementById("axis-z").textContent = temporalRoles[cell.z];
  document.getElementById("traversal-step").textContent =
    "STEP " + String(step + 1).padStart(2, "0") + " / 27";
  phiButton.setAttribute("aria-pressed", String(traversal === "phi"));
  lexButton.setAttribute("aria-pressed", String(traversal === "lex"));
}
phiButton.addEventListener("click", function () { traversal = "phi"; step = 0; update(); });
lexButton.addEventListener("click", function () { traversal = "lex"; step = 0; update(); });
document.getElementById("previous-cell").addEventListener("click", function () {
  step = (step + CELL_COUNT - 1) % CELL_COUNT;
  update();
});
document.getElementById("next-cell").addEventListener("click", function () {
  step = (step + 1) % CELL_COUNT;
  update();
});
update();
