chrome.action.onClicked.addListener((tab) => {
    if (tab.url.includes("sipp.bpjsketenagakerjaan.go.id")) {
      chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
    } else {
      alert("Please open BPJS website first (https://sipp.bpjsketenagakerjaan.go.id)");
    }
  });