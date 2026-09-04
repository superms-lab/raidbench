(function () {
  const button = document.querySelector("#copy-widget-code");
  const status = document.querySelector("#widget-copy-status");
  const code = '<iframe src="https://raidbench.com/embed/rust-raid-calculator.html" title="Rust raid cost calculator by RaidBench" width="100%" height="350" loading="lazy" style="border:0;max-width:760px" referrerpolicy="strict-origin-when-cross-origin"></iframe>';

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      const input = document.createElement("textarea");
      input.value = code;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    status.textContent = "Embed code copied.";
    window.RaidBenchAnalytics?.track("widget_embed_code_copy");
  }

  button?.addEventListener("click", copyCode);
})();
