window.addEventListener("load", () => {
  const data = {
    action: "sendData",
    title: document.title,
    headers: getAllHeaders(),
    url: getSiteUrl(),
  };
  chrome.runtime.sendMessage(data);
});

const getAllHeaders = () => {
  const headers = [];

  for (const header of document.querySelectorAll("h1")) {
    headers.push(header.textContent);
  }
  return headers;
};

const getSiteUrl = () => {
  return window.location.href;
};
