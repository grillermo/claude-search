const state = {
  results: [],
  index: 0,
  loading: false,
};
let latestSearchId = 0;

const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-term");
const caseSensitiveInput = document.querySelector("#case-sensitive");
const resultStatus = document.querySelector("#result-status");
const resultViewport = document.querySelector("#result-viewport");
const resultContent = document.querySelector("#result-content");
const relativeDate = document.querySelector("#result-relative-date");
const projectPath = document.querySelector("#result-project-path");
const title = document.querySelector("#result-title");
const matchingMessageContainer = document.querySelector("#matching-message-container");
const matchingMessage = document.querySelector("#matching-message");
const resumeCommand = document.querySelector("#resume-command");
const resumeCommandText = document.querySelector("#resume-command-text");
const copyCommand = document.querySelector("#copy-command");
const navigation = document.querySelector("#result-navigation");
const previousResult = document.querySelector("#previous-result");
const resultPosition = document.querySelector("#result-position");
const nextResult = document.querySelector("#next-result");

function replaceWithText(container, value) {
  container.replaceChildren(document.createTextNode(value || ""));
}

function appendSegments(container, segments) {
  for (const segment of segments) {
    const text = document.createTextNode(segment.text || "");
    if (segment.highlighted) {
      const mark = document.createElement("mark");
      mark.className = "rounded bg-amber-300 px-0.5 text-slate-950";
      mark.append(text);
      container.append(mark);
    } else {
      container.append(text);
    }
  }
}

function renderSegments(container, segments, fallbackText) {
  container.replaceChildren();
  appendSegments(container, segments || [{ text: fallbackText, highlighted: false }]);
}

function setStatus(message) {
  replaceWithText(resultStatus, message);
  resultStatus.classList.toggle("hidden", message === "");
}

function resetResultViewport() {
  resultViewport.scrollTop = 0;
}

function renderNavigation() {
  const hasResults = state.results.length > 0;
  navigation.classList.toggle("hidden", !hasResults);
  previousResult.disabled = !hasResults || state.index === 0;
  nextResult.disabled = !hasResults || state.index === state.results.length - 1;
  replaceWithText(
    resultPosition,
    hasResults ? `Result ${state.index + 1} of ${state.results.length}` : "",
  );
}

function showResult(index) {
  resetResultViewport();
  if (!state.results.length) {
    resultContent.classList.add("hidden");
    resumeCommand.classList.add("hidden");
    renderNavigation();
    return;
  }

  state.index = Math.min(Math.max(index, 0), state.results.length - 1);
  const result = state.results[state.index];
  resultContent.classList.remove("hidden");
  resumeCommand.classList.remove("hidden");
  replaceWithText(relativeDate, result.relative_date);
  replaceWithText(projectPath, result.cwd);
  renderSegments(title, result.title_segments, result.title);

  const hasSeparateMatch = result.match !== result.title;
  matchingMessageContainer.classList.toggle("hidden", !hasSeparateMatch);
  if (hasSeparateMatch) {
    renderSegments(matchingMessage, result.match_segments, result.match);
  } else {
    matchingMessage.replaceChildren();
  }

  replaceWithText(resumeCommandText, result.resume_command);
  renderNavigation();
}

function renderMessage(message) {
  resetResultViewport();
  resultContent.classList.add("hidden");
  resumeCommand.classList.add("hidden");
  setStatus(message);
  renderNavigation();
}

function moveResult(delta) {
  if (!state.results.length) {
    return;
  }

  showResult(state.index + delta);
}

function selectResumeCommand() {
  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(resumeCommandText);
  selection.removeAllRanges();
  selection.addRange(range);
}

async function copyResumeCommand() {
  try {
    await navigator.clipboard.writeText(resumeCommandText.textContent);
    replaceWithText(copyCommand, "Copied");
    window.setTimeout(() => replaceWithText(copyCommand, "Copy"), 1000);
  } catch (_error) {
    selectResumeCommand();
    replaceWithText(copyCommand, "Select and copy the command.");
  }
}

async function searchHistory(event) {
  event.preventDefault();
  const searchId = ++latestSearchId;
  const term = searchInput.value;
  if (term.trim() === "") {
    state.results = [];
    state.index = 0;
    state.loading = false;
    renderMessage("Enter a search term.");
    return;
  }

  state.loading = true;
  state.results = [];
  state.index = 0;
  renderMessage("Searching conversations…");

  try {
    const caseSensitive = caseSensitiveInput.checked ? "true" : "false";
    const response = await fetch(
      `/api/search?term=${encodeURIComponent(term)}&case_sensitive=${caseSensitive}`,
    );
    const payload = await response.json();

    if (searchId !== latestSearchId) {
      return;
    }

    if (!response.ok) {
      renderMessage(payload.error?.message || "Search request could not be completed.");
      return;
    }

    state.results = payload.results || [];
    state.index = 0;
    if (!state.results.length) {
      renderMessage("No conversations found.");
      return;
    }

    setStatus("");
    showResult(0);
  } catch (_error) {
    if (searchId === latestSearchId) {
      renderMessage("Search failed unexpectedly.");
    }
  } finally {
    if (searchId === latestSearchId) {
      state.loading = false;
    }
  }
}

searchForm.addEventListener("submit", searchHistory);
copyCommand.addEventListener("click", copyResumeCommand);
previousResult.addEventListener("click", () => moveResult(-1));
nextResult.addEventListener("click", () => moveResult(1));

document.addEventListener("keydown", (event) => {
  if (
    (event.key !== "ArrowLeft" && event.key !== "ArrowRight") ||
    document.activeElement === searchInput ||
    !state.results.length
  ) {
    return;
  }

  event.preventDefault();
  moveResult(event.key === "ArrowLeft" ? -1 : 1);
});

window.addEventListener("DOMContentLoaded", () => searchInput.focus());
