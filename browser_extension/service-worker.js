const IGNORE_URL_PREFIXES = ["chrome://", "about:", "edge://"];

function buildPayload(message) {
  return {
    url: message.url,
    title: message.title,
    lang: message.lang,
    text: message.text,
    timestamp: new Date().toISOString(),
  };
}

chrome.runtime.onMessage.addListener(async (message) => {
  console.log("Полученное сообщение:", message);

  if (!message || message.type !== "view") {
    return;
  }
  if (
    !message.url ||
    IGNORE_URL_PREFIXES.some((prefix) => message.url.startsWith(prefix))
  ) {
    return;
  }

  const payload = buildPayload(message);
  console.log("Полезная нагрузка:", payload);
});
