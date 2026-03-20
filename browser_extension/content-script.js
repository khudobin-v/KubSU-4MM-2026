const LESS_LINES_THRESHOLD = 30;
const VIEW_SEND_DELAY_MS = 1500;

let lastSentUrl = "";
let pendingSendTimeoutId = null;
let lastKnownHref = location.href;

const normalizeText = (text) => {
  return text
    .normalize("NFKC")
    .replace(/\u0000/g, "")
    .replace(/\s+/g, " ")
    .replace(/\n+/g, "\n")
    .replace(/[^\S\r\n]+/g, " ")
    .trim();
};

const removeDuplicateLines = (text) => {
  const seen = new Set();
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => {
      if (line.length < LESS_LINES_THRESHOLD) {
        return false;
      }
      if (seen.has(line)) {
        return false;
      }
      seen.add(line);
      return true;
    })
    .join("\n");
};

const getVisibleText = (element) => {
  const style = window.getComputedStyle(element);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    element.offsetHeight === 0
  ) {
    return "";
  }
  return element.innerText.trim();
};

const scoreElement = (element) => {
  const text = getVisibleText(element);
  if (text.length < 300) {
    return 0;
  }

  const links = element.querySelectorAll("a").length;
  const buttons = element.querySelectorAll("button").length;
  const paragraphs = element.querySelectorAll("p").length;

  let score = text.length;
  score -= links * 60;
  score -= buttons * 40;
  score += paragraphs * 100;

  const badPatterns = /nav|menu|footer|header|sidebar|comment|ads?|promo/i;
  if (badPatterns.test(element.className) || badPatterns.test(element.id)) {
    score *= 0.2;
  }

  return score;
};

const extractMainBlock = () => {
  const semantic =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.querySelector('[role="main"]');

  if (semantic) {
    const text = getVisibleText(semantic);
    if (text.length > 500) {
      return semantic;
    }
  }

  const candidates = [...document.querySelectorAll("div, section, article")];
  let bestElement = null;
  let bestScore = 0;

  for (const element of candidates) {
    const score = scoreElement(element);
    if (score > bestScore) {
      bestScore = score;
      bestElement = element;
    }
  }

  return bestElement;
};

const parseContentText = () => {
  const block = extractMainBlock();
  if (!block) {
    return "";
  }

  let text = getVisibleText(block);
  text = normalizeText(text);
  text = removeDuplicateLines(text);
  return text;
};

function sendCurrentView() {
  if (lastSentUrl === location.href) {
    return;
  }

  const payload = {
    type: "view",
    url: location.href,
    title: normalizeText(document.title || ""),
    lang: document.documentElement?.lang || "",
    text: parseContentText(),
  };

  chrome.runtime.sendMessage(payload);
  lastSentUrl = location.href;
}

function scheduleViewSend() {
  if (pendingSendTimeoutId) {
    clearTimeout(pendingSendTimeoutId);
  }

  pendingSendTimeoutId = setTimeout(() => {
    pendingSendTimeoutId = null;
    sendCurrentView();
  }, VIEW_SEND_DELAY_MS);
}

function handleLocationChange() {
  if (location.href === lastKnownHref) {
    return;
  }

  lastKnownHref = location.href;
  scheduleViewSend();
}

const originalPushState = history.pushState;
history.pushState = function pushState(...args) {
  originalPushState.apply(this, args);
  handleLocationChange();
};

const originalReplaceState = history.replaceState;
history.replaceState = function replaceState(...args) {
  originalReplaceState.apply(this, args);
  handleLocationChange();
};

window.addEventListener("popstate", handleLocationChange);
window.addEventListener("load", scheduleViewSend);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    scheduleViewSend();
  }
});

const observer = new MutationObserver(() => {
  handleLocationChange();
});

observer.observe(document.documentElement, {
  childList: true,
  subtree: true,
});
