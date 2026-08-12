// Background Service Worker for JD Glance

// Set side panel behavior to open on extension icon click
chrome.runtime.onInstalled.addListener(async () => {
  try {
    if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
      await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
    }
  } catch (err) {
    console.error("Error setting side panel behavior:", err);
  }

  // Create Context Menu item for selected text.
  // removeAll() first: onInstalled can fire again (extension reload, browser
  // restart) while Chrome still has the item from a prior registration —
  // creating over it without clearing throws "duplicate id" otherwise.
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "analyze_selected_jd",
      title: "⚡ Analyze with Resume (JD Glance)",
      contexts: ["selection"]
    });
  });
});

// Handle Context Menu click
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "analyze_selected_jd" && info.selectionText) {
    const selectedText = info.selectionText.trim();
    if (!selectedText) return;

    // Save pending selection in chrome.storage.local
    await chrome.storage.local.set({
      pending_jd_text: selectedText,
      pending_jd_timestamp: Date.now()
    });

    // Open side panel in the active window
    if (tab && tab.windowId) {
      try {
        await chrome.sidePanel.open({ windowId: tab.windowId });
      } catch (e) {
        console.log("Side panel open error or already open:", e);
      }
    }

    // Broadcast message to open sidepanel script
    chrome.runtime.sendMessage({
      type: "JD_TEXT_SELECTED",
      text: selectedText
    }).catch(() => {
      // Sidepanel might not be open yet; stored state in storage.local will be read on load
    });
  }
});

// Listen for messages from Content Scripts & Side Panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "OPEN_SIDE_PANEL_WITH_JD") {
    (async () => {
      const selectedText = message.text;
      await chrome.storage.local.set({
        pending_jd_text: selectedText,
        pending_jd_timestamp: Date.now()
      });

      if (sender.tab && sender.tab.windowId) {
        try {
          await chrome.sidePanel.open({ windowId: sender.tab.windowId });
        } catch (err) {
          console.error("Failed to open side panel:", err);
        }
      }

      // Notify any active sidepanel script
      chrome.runtime.sendMessage({
        type: "JD_TEXT_SELECTED",
        text: selectedText
      }).catch(() => {});

      sendResponse({ status: "ok" });
    })();
    return true; // Keep message channel open for async response
  }

  if (message.type === "GET_ACTIVE_TAB_SELECTION") {
    (async () => {
      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab && tab.id) {
          const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => window.getSelection() ? window.getSelection().toString() : ""
          });
          const text = results && results[0] ? results[0].result : "";
          sendResponse({ text });
        } else {
          sendResponse({ text: "" });
        }
      } catch (err) {
        sendResponse({ text: "", error: err.message });
      }
    })();
    return true;
  }
});
