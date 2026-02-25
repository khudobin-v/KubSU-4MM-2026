const LESS_LINES_THRESHOLD = 30;

// Удаление лишних пробелов, нормализация юникода и удаление нулевых символов
const normalizeText = (text) => {
  return text
    .normalize("NFKC")
    .replace(/\u0000/g, "")
    .replace(/\s+/g, " ")
    .replace(/\n+/g, "\n")
    .replace(/[^\S\r\n]+/g, " ")
    .trim();
};

// Удаление строк короче 30 символов и дубликатов
const removeDuplicateLines = (text) => {
  const seen = new Set();
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter((line) => {
      if (line.length < LESS_LINES_THRESHOLD) return false;
      if (seen.has(line)) return false;
      seen.add(line);
      return true;
    })
    .join("\n");
};

// Получение видимого текста элемента, игнорируя скрытые блоки
const getVisibleText = (el) => {
  const style = window.getComputedStyle(el);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    el.offsetHeight === 0
  ) {
    return "";
  }
  return el.innerText.trim();
};

// Оценка элемента по количеству текста, ссылок, кнопок и абзацев, а также по классу и id
const scoreElement = (el) => {
  const text = getVisibleText(el);
  if (text.length < 300) return 0;

  const links = el.querySelectorAll("a").length;
  const buttons = el.querySelectorAll("button").length;
  const paragraphs = el.querySelectorAll("p").length;

  let score = text.length;

  score -= links * 60;
  score -= buttons * 40;
  score += paragraphs * 100;

  const badPatterns = /nav|menu|footer|header|sidebar|comment|ads?|promo/i;
  if (badPatterns.test(el.className) || badPatterns.test(el.id)) {
    score *= 0.2;
  }

  return score;
};

// Извлечение основного блока наилучшим образом
const extractMainBlock = () => {
  const semantic =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.querySelector('[role="main"]');

  if (semantic) {
    const text = getVisibleText(semantic);
    if (text.length > 500) return semantic;
  }

  const candidates = [...document.querySelectorAll("div, section, article")];

  let bestEl = null;
  let bestScore = 0;

  for (const el of candidates) {
    const score = scoreElement(el);
    if (score > bestScore) {
      bestScore = score;
      bestEl = el;
    }
  }

  return bestEl;
};

// Парсинг текста страницы, нормализация и удаление дубликатов
const parseContentText = () => {
  const block = extractMainBlock();
  if (!block) return "";

  let text = getVisibleText(block);
  text = normalizeText(text);
  text = removeDuplicateLines(text);

  return text;
};

window.addEventListener("load", () => {
  setTimeout(() => {
    const payload = {
      type: "view",
      url: location.href,
      title: normalizeText(document.title || ""),
      lang: document.documentElement?.lang || "",
      text: parseContentText(),
    };

    chrome.runtime.sendMessage(payload);
  }, 1500);
});
