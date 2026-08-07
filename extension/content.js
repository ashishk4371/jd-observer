(function () {
  let floatingPill = null;
  let selectedJDText = "";

  function removeFloatingPill() {
    if (floatingPill && floatingPill.parentNode) {
      floatingPill.parentNode.removeChild(floatingPill);
    }
    floatingPill = null;
  }

  function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "jd-analyzer-toast";
    toast.innerHTML = `✨ <span>${message}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 2800);
  }

  function handleSelectionChange(e) {
    // Ignore clicks inside our floating pill
    if (e && e.target && e.target.closest && e.target.closest(".jd-analyzer-floating-pill")) {
      return;
    }

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      removeFloatingPill();
      return;
    }

    const text = selection.toString().trim();
    if (text.length < 15) {
      removeFloatingPill();
      return;
    }

    selectedJDText = text;

    try {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();

      if (!rect || rect.width === 0 || rect.height === 0) {
        removeFloatingPill();
        return;
      }

      if (!floatingPill) {
        floatingPill = document.createElement("div");
        floatingPill.className = "jd-analyzer-floating-pill";
        floatingPill.innerHTML = `<span class="jd-icon">⚡</span> Analyze with Resume`;
        
        floatingPill.addEventListener("mousedown", (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          
          if (selectedJDText) {
            chrome.runtime.sendMessage({
              type: "OPEN_SIDE_PANEL_WITH_JD",
              text: selectedJDText
            }, (res) => {
              showToast("Opening Job Description Analyzer...");
              removeFloatingPill();
            });
          }
        });

        document.body.appendChild(floatingPill);
      }

      // Position pill right above or below selection
      const topPos = window.scrollY + rect.top - 42;
      const leftPos = window.scrollX + rect.left + Math.max(0, (rect.width / 2) - 80);

      floatingPill.style.top = `${Math.max(10, topPos)}px`;
      floatingPill.style.left = `${Math.max(10, leftPos)}px`;
    } catch (err) {
      removeFloatingPill();
    }
  }

  // Listen for selection mouseup
  document.addEventListener("mouseup", (e) => {
    setTimeout(() => handleSelectionChange(e), 50);
  });

  // Remove pill when user clicks elsewhere or scrolls
  document.addEventListener("selectionchange", () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) {
      removeFloatingPill();
    }
  });

  window.addEventListener("scroll", () => {
    removeFloatingPill();
  }, { passive: true });

})();
