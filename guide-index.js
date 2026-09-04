const guideSearch = document.querySelector("#guide-search");
const guideFilters = Array.from(document.querySelectorAll("[data-guide-filter]"));
const guideSections = Array.from(document.querySelectorAll("[data-guide-section]"));
const guideCards = Array.from(document.querySelectorAll("[data-guide-card]"));
const guideStatus = document.querySelector("#guide-index-status");
const guideEmpty = document.querySelector("#guide-index-empty");

let activeGame = "all";

const requestedGame = new URLSearchParams(window.location.search).get("game");
if (requestedGame && guideFilters.some((button) => button.dataset.guideFilter === requestedGame)) {
  activeGame = requestedGame;
}

function normalize(value = "") {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function updateGuideIndex() {
  const query = normalize(guideSearch?.value);
  let visibleCount = 0;

  guideCards.forEach((card) => {
    const matchesGame = activeGame === "all" || card.dataset.game === activeGame;
    const matchesQuery = !query || normalize(card.dataset.search).includes(query);
    const visible = matchesGame && matchesQuery;
    card.hidden = !visible;
    if (visible) visibleCount += 1;
  });

  guideSections.forEach((section) => {
    section.hidden = !section.querySelector("[data-guide-card]:not([hidden])");
  });

  if (guideStatus) {
    const gameLabel = activeGame === "all" ? "all games" : activeGame.toUpperCase();
    guideStatus.textContent = `${visibleCount} guide${visibleCount === 1 ? "" : "s"} shown across ${gameLabel}.`;
  }

  if (guideEmpty) guideEmpty.hidden = visibleCount !== 0;
}

guideFilters.forEach((button) => {
  button.setAttribute("aria-pressed", String(button.dataset.guideFilter === activeGame));
  button.addEventListener("click", () => {
    activeGame = button.dataset.guideFilter;
    guideFilters.forEach((filter) => {
      filter.setAttribute("aria-pressed", String(filter === button));
    });
    updateGuideIndex();
    window.RaidBenchAnalytics?.track("guide_filter_change", { game: activeGame });
  });
});

guideSearch?.addEventListener("input", updateGuideIndex);
updateGuideIndex();
