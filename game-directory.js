const gameSelect = document.querySelector("#homepage-game-select");
const openSelectedGame = document.querySelector("#open-selected-game");
const gameFilters = Array.from(document.querySelectorAll("[data-game-filter]"));
const gameRows = Array.from(document.querySelectorAll("[data-game-row]"));
const gameDirectoryStatus = document.querySelector("#game-directory-status");

function openGame() {
  const destination = gameSelect?.value;
  if (!destination || !destination.startsWith("/games/")) return;
  window.RaidBenchAnalytics?.track("game_directory_open", {
    game: destination.split("/").filter(Boolean).at(-1) || "unknown",
    placement: "homepage_selector",
  });
  window.location.assign(destination);
}

openSelectedGame?.addEventListener("click", openGame);
gameSelect?.addEventListener("change", () => {
  window.RaidBenchAnalytics?.track("game_selector_change", {
    game: gameSelect.value.split("/").filter(Boolean).at(-1) || "unknown",
  });
});

gameFilters.forEach((button) => {
  button.addEventListener("click", () => {
    const activeGenre = button.dataset.gameFilter || "all";
    let visible = 0;
    gameFilters.forEach((filter) => filter.setAttribute("aria-pressed", String(filter === button)));
    gameRows.forEach((row) => {
      const matches = activeGenre === "all" || row.dataset.genre === activeGenre;
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (gameDirectoryStatus) {
      gameDirectoryStatus.textContent = `${visible} game${visible === 1 ? "" : "s"} shown.`;
    }
    window.RaidBenchAnalytics?.track("game_directory_filter", { genre: activeGenre });
  });
});

if (gameDirectoryStatus) gameDirectoryStatus.textContent = `${gameRows.length} games shown.`;
