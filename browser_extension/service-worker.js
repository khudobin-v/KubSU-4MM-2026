const IGNORE_URL_PREFIXES = ["chrome://", "about:", "edge://"];
const API_ENDPOINT = "http://127.0.0.1:8000/api/payloads";

function buildPayload(message) {
  return {
    url: message.url,
    title: message.title,
    lang: message.lang,
    text: message.text,
    timestamp: new Date().toISOString(),
  };
}

async function sendPayloadToApi(payload) {
  const response = await fetch(API_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const result = await response.json();
  console.log("Payload saved:", result);
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

  try {
    await sendPayloadToApi(payload);
  } catch (error) {
    console.error("Ошибка отправки payload в API:", error);
  }
});
