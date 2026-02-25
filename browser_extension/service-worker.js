chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action == "sendData") {
    console.log("SITE: " + request.url);
    console.log("Headers: " + request.headers);
  }
});
