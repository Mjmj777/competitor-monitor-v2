import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function dataKey(name) {
  return name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

class MockNode {
  constructor(tag = "node", text = "") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.className = "";
    this.textContent = text;
    this.listeners = {};
    this.classList = {
      add: (...names) => {
        const values = new Set(this.className.split(/\s+/).filter(Boolean));
        names.forEach((name) => values.add(name));
        this.className = [...values].join(" ");
      },
      remove: (...names) => {
        const removed = new Set(names);
        this.className = this.className.split(/\s+/).filter((name) => name && !removed.has(name)).join(" ");
      },
      contains: (name) => this.className.split(/\s+/).includes(name),
    };
  }

  append(...nodes) {
    nodes.flat().forEach((node) => this.appendChild(node));
  }

  appendChild(node) {
    const child = node instanceof MockNode ? node : new MockNode("#text", String(node));
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  removeChild(node) {
    this.children = this.children.filter((child) => child !== node);
    node.parentNode = null;
  }

  get firstChild() {
    return this.children[0] || null;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name.startsWith("data-")) this.dataset[dataKey(name)] = String(value);
  }

  addEventListener(name, handler) {
    this.listeners[name] = handler;
  }

  querySelectorAll(selector) {
    const matches = [];
    const test = selector === "[data-count-target]"
      ? (node) => Object.hasOwn(node.attributes, "data-count-target")
      : () => false;
    const walk = (node) => {
      node.children.forEach((child) => {
        if (test(child)) matches.push(child);
        walk(child);
      });
    };
    walk(this);
    return matches;
  }
}

globalThis.Node = MockNode;
globalThis.document = {
  createElement: (tag) => new MockNode(tag),
  createTextNode: (text) => new MockNode("#text", String(text)),
  documentElement: { lang: "en", dir: "ltr" },
  querySelectorAll: () => [],
};
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.location = { href: "https://example.test/", reload: () => {} };
globalThis.window = {
  matchMedia: () => ({ matches: true }),
  addEventListener: () => {},
  dispatchEvent: () => {},
};
globalThis.performance = { now: () => 0 };

const common = fs.readFileSync(new URL("../assets/common.js", import.meta.url), "utf8");
vm.runInThisContext(common, { filename: "assets/common.js" });
const C = window.CM;
assert.ok(C, "Common module did not expose window.CM");

const bars = new MockNode("div");
C.renderBarChart(bars, [
  { label: "Low", value: 1 },
  { label: "High", value: 3 },
], { keepZero: true });
assert.equal(bars.children.length, 2, "Bar chart row count changed");
assert.equal(bars.children[0].children[0].children[0].textContent, "High", "Bar chart is not sorted descending");
assert.ok(bars.classList.contains("is-chart-visible"), "Reduced-motion fallback did not reveal the chart");

const stacked = new MockNode("div");
C.renderStackedBarChart(stacked, [
  { label: "A", values: { one: 2, two: 1 } },
], [
  { id: "one", label: "One", color: "#111" },
  { id: "two", label: "Two", color: "#222" },
], { normalize: true });
assert.equal(stacked.children.length, 2, "Stacked chart must contain a legend and one row");
assert.ok(stacked.classList.contains("is-chart-visible"), "Stacked chart was not revealed");

const grouped = new MockNode("div");
C.renderGroupedBarChart(grouped, [
  { label: "A", values: { current: 4, previous: 2 }, colors: { current: "#123" } },
], [
  { id: "current", label: "Current", color: "#111" },
  { id: "previous", label: "Previous", color: "#999" },
]);
assert.equal(grouped.children.length, 2, "Grouped chart must contain a legend and one row");

const donut = new MockNode("div");
C.renderDonutChart(donut, [
  { label: "Remittance", value: 7, color: "#123", onClick: () => {} },
  { label: "Card", value: 3, color: "#456" },
], { centerLabel: "Active" });
assert.equal(donut.children.length, 1, "Donut chart layout was not rendered");
assert.ok(donut.classList.contains("is-chart-visible"), "Donut chart was not revealed");

const columns = new MockNode("div");
C.renderColumnChart(columns, [
  { label: "A", value: 4, onClick: () => {} },
  { label: "B", value: 0 },
], { keepZero: true });
assert.equal(columns.children.length, 1, "Column chart wrapper was not rendered");
assert.equal(columns.children[0].children.length, 2, "Column chart must preserve zero-value competitors");
assert.ok(columns.classList.contains("is-chart-visible"), "Column chart was not revealed");

const matrix = new MockNode("div");
C.renderMatrix(matrix, [{ id: "a", label: "A" }], [{ id: "x", label: "X" }], () => 2, { onCellClick: () => {} });
assert.equal(matrix.children.length, 1, "Heatmap table was not rendered");
assert.ok(matrix.classList.contains("is-chart-visible"), "Heatmap was not revealed");

const indexSource = fs.readFileSync(new URL("../assets/index.js", import.meta.url), "utf8");
const matrixCallStart = indexSource.indexOf('C.renderMatrix(\n      document.getElementById("coverage-matrix")');
const matrixCallEnd = indexSource.indexOf("\n    );", matrixCallStart);
assert.ok(matrixCallStart >= 0 && matrixCallEnd > matrixCallStart, "Coverage matrix call was not found");
const coverageMatrixCall = indexSource.slice(matrixCallStart, matrixCallEnd);
assert.match(
  coverageMatrixCall,
  /\n\s+categorySeries,\n/,
  "Coverage matrix must receive labeled category definitions",
);
assert.match(indexSource, /C\.renderDonutChart\(/, "Campaign categories must use a donut chart");
assert.match(indexSource, /C\.renderColumnChart\(/, "Remittance comparison must use a column chart");
assert.match(indexSource, /upcomingExpiries7d/, "Seven-day expiry signal is missing");
assert.match(indexSource, /recent-market-changes/, "Recent verified market changes are missing");
assert.match(indexSource, /inCampaignChangePeriod/, "Campaign change custom-period filtering is missing");
assert.match(indexSource, /campaignChangeCustom/, "Custom campaign change state is missing");
assert.match(indexSource, /C\.competitorLogo\(competitor\.id\)/, "Competitor cards must render logo assets");

const indexHtml = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
assert.match(indexHtml, /id="data-freshness"/, "Viewer data freshness indicator is missing");
assert.match(indexHtml, /id="upcoming-expiries"/, "Upcoming expiry section is missing");
assert.match(indexHtml, /id="recent-market-changes"/, "Recent market changes section is missing");
assert.match(indexHtml, /value="custom"/, "Campaign changes chart is missing its custom-period option");
assert.match(indexHtml, /class="section-nav"/, "Main-page scroll navigation is missing");
assert.match(indexHtml, /href="#management-summary"/, "Management Summary scroll link is missing");
assert.match(indexHtml, /id="intelligence-field"/, "Intelligence OS competitor field is missing");
assert.match(indexHtml, /id="site-experience"/, "Admin Site Experience control is missing");
assert.match(indexSource, /set_site_layout/, "Persistent Site Experience publishing is missing");
assert.match(common, /isAdmin\(\)\?merged:\[\]/, "Merged records must be removed from Viewer data");
assert.match(common, /localStorage\.removeItem\("cm_home_layout_preview"\)/, "Publishing a layout must clear the private Admin preview");
assert.match(common, /protectedCategories=new Set\(\["remittance","musaned","sadad","card","engagement"\]\)/, "Merge target choices must block incompatible campaign categories");
assert.doesNotMatch(indexHtml, /market-orbit/, "Retired Market Orbit layout must not remain in the page");
assert.doesNotMatch(indexSource, /market-orbit/, "Retired Market Orbit logic must not remain in JavaScript");
for (const id of ["stc-bank", "barq", "mobily-pay", "tiqmo", "urpay", "alinma-pay"]) {
  assert.ok(fs.existsSync(new URL(`../assets/logos/${id}.webp`, import.meta.url)), `Missing logo asset for ${id}`);
}
for (const id of ["barq", "tiqmo"]) {
  assert.ok(fs.existsSync(new URL(`../assets/logos/${id}-dark.png`, import.meta.url)), `Missing Intelligence OS logo asset for ${id}`);
}

console.log("Chart renderer tests passed");
