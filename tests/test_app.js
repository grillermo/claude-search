const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const appSource = fs.readFileSync(
  path.join(__dirname, "..", "static", "app.js"),
  "utf8",
);

class FakeText {
  constructor(data) {
    this.data = data;
  }

  get textContent() {
    return this.data;
  }
}

class FakeClassList {
  constructor() {
    this.names = new Set();
  }

  add(name) {
    this.names.add(name);
  }

  remove(name) {
    this.names.delete(name);
  }

  contains(name) {
    return this.names.has(name);
  }

  toggle(name, force) {
    if (force === undefined) {
      force = !this.names.has(name);
    }
    if (force) {
      this.names.add(name);
    } else {
      this.names.delete(name);
    }
    return force;
  }
}

class FakeElement {
  constructor(id = "") {
    this.id = id;
    this.children = [];
    this.classList = new FakeClassList();
    this.disabled = false;
    this.value = "";
    this.checked = false;
    this.scrollTop = 0;
    this.listeners = new Map();
  }

  append(...nodes) {
    this.children.push(...nodes);
  }

  replaceChildren(...nodes) {
    this.children = nodes;
  }

  addEventListener(type, listener) {
    this.listeners.set(type, [...(this.listeners.get(type) || []), listener]);
  }

  async dispatch(type, event = {}) {
    for (const listener of this.listeners.get(type) || []) {
      await listener({
        preventDefault() {
          event.defaultPrevented = true;
        },
        ...event,
      });
    }
    return event;
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  get textContent() {
    return this.children.map((child) => child.textContent).join("");
  }

  set className(value) {
    this.classList.names = new Set(value.split(/\s+/).filter(Boolean));
  }
}

const elementIds = [
  "search-form",
  "search-term",
  "case-sensitive",
  "result-status",
  "result-viewport",
  "result-content",
  "result-relative-date",
  "result-project-path",
  "result-title",
  "matching-message-container",
  "matching-message",
  "resume-command",
  "resume-command-text",
  "copy-command",
  "result-navigation",
  "previous-result",
  "result-position",
  "next-result",
];

function makeResult(title, match = title) {
  return {
    relative_date: "just now",
    cwd: "/tmp/project",
    title,
    match,
    resume_command: "claude --resume test-id",
    title_segments: [{ text: title, highlighted: false }],
    match_segments: [{ text: match, highlighted: false }],
  };
}

function makeResponse(results) {
  return {
    ok: true,
    json: async () => ({ results }),
  };
}

function loadApp({ fetch, clipboard = { writeText: async () => {} } } = {}) {
  const elements = Object.fromEntries(
    elementIds.map((id) => [id, new FakeElement(id)]),
  );
  const documentListeners = new Map();
  const windowListeners = new Map();
  const selection = {
    ranges: [],
    removeAllRanges() {
      this.ranges = [];
    },
    addRange(range) {
      this.ranges.push(range);
    },
    toString() {
      return this.ranges[0]?.node.textContent || "";
    },
  };
  const document = {
    activeElement: null,
    querySelector(selector) {
      return elements[selector.slice(1)];
    },
    createTextNode(value) {
      return new FakeText(value);
    },
    createElement() {
      return new FakeElement();
    },
    createRange() {
      return {
        selectNodeContents(node) {
          this.node = node;
        },
      };
    },
    addEventListener(type, listener) {
      documentListeners.set(type, [...(documentListeners.get(type) || []), listener]);
    },
    async dispatch(type, event = {}) {
      for (const listener of documentListeners.get(type) || []) {
        await listener({
          preventDefault() {
            event.defaultPrevented = true;
          },
          ...event,
        });
      }
      return event;
    },
  };
  for (const element of Object.values(elements)) {
    element.ownerDocument = document;
  }
  const window = {
    addEventListener(type, listener) {
      windowListeners.set(type, [...(windowListeners.get(type) || []), listener]);
    },
    async dispatch(type) {
      for (const listener of windowListeners.get(type) || []) {
        await listener();
      }
    },
    getSelection() {
      return selection;
    },
    setTimeout() {},
  };
  vm.runInNewContext(appSource, {
    document,
    window,
    navigator: { clipboard },
    fetch,
  });

  return { document, elements, selection, window };
}

test("latest search response wins when requests finish out of order", async () => {
  const pending = [];
  const app = loadApp({
    fetch(url) {
      return new Promise((resolve) => pending.push({ resolve, url }));
    },
  });
  const { elements } = app;

  elements["search-term"].value = "first ";
  const firstSearch = elements["search-form"].dispatch("submit");
  elements["search-term"].value = "second ";
  const secondSearch = elements["search-form"].dispatch("submit");

  assert.deepEqual(
    pending.map((request) => request.url),
    [
      "/api/search?term=first%20&case_sensitive=false",
      "/api/search?term=second%20&case_sensitive=false",
    ],
  );
  pending[1].resolve(makeResponse([makeResult("second result")]));
  await secondSearch;
  pending[0].resolve(makeResponse([makeResult("first result")]));
  await firstSearch;

  assert.equal(elements["result-title"].textContent, "second result");
});

test("rendering a different result resets the result viewport scroll position", async () => {
  const app = loadApp({
    fetch: async () => makeResponse([makeResult("first"), makeResult("second")]),
  });
  const { elements } = app;

  elements["search-term"].value = "term";
  await elements["search-form"].dispatch("submit");
  elements["result-viewport"].scrollTop = 480;
  await elements["next-result"].dispatch("click");

  assert.equal(elements["result-title"].textContent, "second");
  assert.equal(elements["result-viewport"].scrollTop, 0);
});

test("result rendering preserves text as nodes and highlights only marked segments", async () => {
  const result = makeResult("ignored");
  result.title_segments = [
    { text: "<img src=x onerror=alert(1)>", highlighted: false },
    { text: "needle", highlighted: true },
  ];
  const app = loadApp({ fetch: async () => makeResponse([result]) });
  const { elements } = app;

  elements["search-term"].value = "needle";
  await elements["search-form"].dispatch("submit");

  assert.equal(typeof elements["result-title"].children[0].data, "string");
  assert.equal(
    elements["result-title"].children[0].data,
    "<img src=x onerror=alert(1)>",
  );
  assert.equal(elements["result-title"].children[1].children[0].data, "needle");
});

test("focus, navigation bounds, keyboard navigation, and clipboard fallback work", async () => {
  const app = loadApp({
    fetch: async () => makeResponse([makeResult("first"), makeResult("second")]),
    clipboard: { writeText: async () => Promise.reject(new Error("denied")) },
  });
  const { document, elements, selection, window } = app;

  await window.dispatch("DOMContentLoaded");
  assert.equal(document.activeElement, elements["search-term"]);
  elements["search-term"].value = "term";
  await elements["search-form"].dispatch("submit");
  assert.equal(elements["previous-result"].disabled, true);
  assert.equal(elements["next-result"].disabled, false);

  document.activeElement = elements["result-title"];
  const right = await document.dispatch("keydown", { key: "ArrowRight" });
  assert.equal(right.defaultPrevented, true);
  assert.equal(elements["result-position"].textContent, "Result 2 of 2");
  assert.equal(elements["next-result"].disabled, true);

  elements["search-term"].focus();
  const ignoredRight = await document.dispatch("keydown", { key: "ArrowRight" });
  assert.equal(ignoredRight.defaultPrevented, undefined);
  assert.equal(elements["result-position"].textContent, "Result 2 of 2");

  await elements["copy-command"].dispatch("click");
  assert.equal(elements["copy-command"].textContent, "Select and copy the command.");
  assert.equal(selection.toString(), "claude --resume test-id");
});
