const API_BASE_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "focus_topic";

const focusTopicInput = document.querySelector("#focus-topic");
const startDateInput = document.querySelector("#start-date");
const endDateInput = document.querySelector("#end-date");
const generateButton = document.querySelector("#generate-summary");
const stopButton = document.querySelector("#stop-summary");
const restartButton = document.querySelector("#restart-summary");
const copyButton = document.querySelector("#copy-summary");
const clearPagesButton = document.querySelector("#clear-pages");
const clearHistoryButton = document.querySelector("#clear-history");
const statusBadge = document.querySelector("#status");
const pageCountValue = document.querySelector("#page-count");
const summaryOutput = document.querySelector("#summary");
const sitesList = document.querySelector("#sites-list");
const historyList = document.querySelector("#history-list");

let rawSummaryText = "Пока пусто.";
let summaryJobPollId = null;
let pagesRefreshPollId = null;
let autoRangeEnabled = true;
let autoRangeDurationMs = 24 * 60 * 60 * 1000;

function setStatus(message) {
  statusBadge.textContent = message;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function applyInlineMarkdown(text) {
  return text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/~~([^~]+)~~/g, "<del>$1</del>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/_([^_]+)_/g, "<em>$1</em>");
}

function renderMarkdown(markdown) {
  const escaped = escapeHtml(markdown).replace(/\r\n/g, "\n");
  const lines = escaped.split("\n");
  const html = [];
  let listType = null;
  let inCodeBlock = false;
  let codeBuffer = [];
  let quoteBuffer = [];
  let paragraphBuffer = [];

  function flushParagraph() {
    if (!paragraphBuffer.length) {
      return;
    }

    html.push(`<p>${applyInlineMarkdown(paragraphBuffer.join("<br />"))}</p>`);
    paragraphBuffer = [];
  }

  function flushList() {
    if (!listType) {
      return;
    }

    html.push(listType === "ol" ? "</ol>" : "</ul>");
    listType = null;
  }

  function flushQuote() {
    if (!quoteBuffer.length) {
      return;
    }

    html.push(`<blockquote>${applyInlineMarkdown(quoteBuffer.join("<br />"))}</blockquote>`);
    quoteBuffer = [];
  }

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      flushQuote();

      if (inCodeBlock) {
        html.push(`<pre><code>${codeBuffer.join("\n")}</code></pre>`);
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }

    const unorderedMatch = line.match(/^[-*] (.+)$/);
    const orderedMatch = line.match(/^\d+\. (.+)$/);

    if (unorderedMatch || orderedMatch) {
      flushParagraph();
      flushQuote();

      const nextListType = unorderedMatch ? "ul" : "ol";
      if (listType !== nextListType) {
        flushList();
        html.push(nextListType === "ol" ? "<ol>" : "<ul>");
        listType = nextListType;
      }

      html.push(`<li>${applyInlineMarkdown((unorderedMatch || orderedMatch)[1])}</li>`);
      continue;
    }

    flushList();

    if (line.trim() === "---" || line.trim() === "***") {
      flushParagraph();
      flushQuote();
      html.push("<hr />");
      continue;
    }

    if (line.startsWith("### ")) {
      flushParagraph();
      flushQuote();
      html.push(`<h3>${applyInlineMarkdown(line.slice(4))}</h3>`);
      continue;
    }

    if (line.startsWith("## ")) {
      flushParagraph();
      flushQuote();
      html.push(`<h2>${applyInlineMarkdown(line.slice(3))}</h2>`);
      continue;
    }

    if (line.startsWith("# ")) {
      flushParagraph();
      flushQuote();
      html.push(`<h1>${applyInlineMarkdown(line.slice(2))}</h1>`);
      continue;
    }

    if (line.startsWith("> ")) {
      flushParagraph();
      quoteBuffer.push(line.slice(2));
      continue;
    }

    flushQuote();
    paragraphBuffer.push(line);
  }

  if (inCodeBlock) {
    html.push(`<pre><code>${codeBuffer.join("\n")}</code></pre>`);
  }

  flushParagraph();
  flushList();
  flushQuote();

  return html.join("");
}

function setSummary(markdownText) {
  rawSummaryText = markdownText;
  summaryOutput.innerHTML = renderMarkdown(markdownText);
}

function setLoading(isLoading) {
  generateButton.disabled = isLoading;
  generateButton.textContent = isLoading ? "Формирую..." : "Получить сводку";
  stopButton.disabled = !isLoading;
  restartButton.disabled = false;
}

function stopSummaryJobPolling() {
  if (summaryJobPollId) {
    clearInterval(summaryJobPollId);
    summaryJobPollId = null;
  }
}

function stopPagesRefreshPolling() {
  if (pagesRefreshPollId) {
    clearInterval(pagesRefreshPollId);
    pagesRefreshPollId = null;
  }
}

function toDateTimeLocalValue(date) {
  const tzOffset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
}

function toUtcIsoString(localDateTimeValue) {
  return new Date(localDateTimeValue).toISOString();
}

function syncAutoRangeToNow() {
  if (!autoRangeEnabled) {
    return;
  }

  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - autoRangeDurationMs);
  startDateInput.value = toDateTimeLocalValue(startDate);
  endDateInput.value = toDateTimeLocalValue(endDate);
}

function buildDateRange() {
  if (!startDateInput.value || !endDateInput.value) {
    return null;
  }

  return {
    start_at: toUtcIsoString(startDateInput.value),
    end_at: toUtcIsoString(endDateInput.value),
  };
}

function getFaviconUrl(url) {
  return `https://www.google.com/s2/favicons?sz=64&domain_url=${encodeURIComponent(url)}`;
}

function renderSites(items) {
  if (!items.length) {
    sitesList.innerHTML = '<p class="empty-copy">За выбранный период страниц не найдено.</p>';
    return;
  }

  sitesList.innerHTML = items
    .map((item) => {
      const hostname = new URL(item.url).hostname;
      const formattedTime = new Date(item.source_timestamp).toLocaleString("ru-RU");
      return `
        <article class="site-item">
          <img class="site-icon" src="${getFaviconUrl(item.url)}" alt="" />
          <div>
            <p class="site-title">${item.title || hostname}</p>
            <p class="site-meta">${hostname}</p>
            <p class="site-meta">${formattedTime}</p>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = '<p class="empty-copy">История сводок пока пуста.</p>';
    return;
  }

  historyList.innerHTML = items
    .map((item) => {
      const createdAt = new Date(item.created_at).toLocaleString("ru-RU");
      const dateRange =
        `${new Date(item.start_at).toLocaleString("ru-RU")} - ` +
        `${new Date(item.end_at).toLocaleString("ru-RU")}`;

      return `
        <details class="history-item">
          <summary class="history-toggle">
            <div class="history-toggle-content">
              <p class="history-title">${escapeHtml(item.focus_topic)}</p>
              <p class="history-meta">${createdAt}</p>
              <p class="history-meta">${dateRange}</p>
              <p class="history-meta">Страниц: ${item.page_count}</p>
            </div>
            <span class="history-chevron" aria-hidden="true"></span>
          </summary>
          <div class="history-summary-content">${renderMarkdown(item.summary)}</div>
        </details>
      `;
    })
    .join("");
}

async function loadSettings() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  focusTopicInput.value = stored[STORAGE_KEY] || "";

  const now = new Date();
  const dayAgo = new Date(now);
  dayAgo.setHours(now.getHours() - 24);
  autoRangeDurationMs = now.getTime() - dayAgo.getTime();

  startDateInput.value = toDateTimeLocalValue(dayAgo);
  endDateInput.value = toDateTimeLocalValue(now);
}

async function saveSettings() {
  await chrome.storage.local.set({ [STORAGE_KEY]: focusTopicInput.value.trim() });
}

async function fetchPagesForPeriod() {
  syncAutoRangeToNow();

  const period = buildDateRange();
  if (!period) {
    return;
  }

  const response = await fetch(`${API_BASE_URL}/api/pages/list`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(period),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || `API error: ${response.status}`);
  }

  pageCountValue.textContent = String(payload.page_count);
  renderSites(payload.items);
}

async function fetchSummaryHistory() {
  const response = await fetch(`${API_BASE_URL}/api/summaries/history`);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || `API error: ${response.status}`);
  }

  renderHistory(payload.items);
}

function sendRuntimeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!response?.ok) {
        reject(new Error(response?.error || "Неизвестная ошибка"));
        return;
      }
      resolve(response.state);
    });
  });
}

async function syncSummaryJobState() {
  const state = await sendRuntimeMessage({ type: "get-summary-job-state" });
  if (!state) {
    setLoading(false);
    return false;
  }

  if (state.status === "running") {
    setLoading(true);
    setStatus("Анализ");
    setSummary("Собираю сводку по выбранным страницам...");
    return true;
  }

  setLoading(false);

  if (state.status === "completed") {
    setSummary(state.summary || "Сводка пуста.");
    setStatus(`Готово · ${state.model}`);
    await fetchSummaryHistory();
    return false;
  }

  if (state.status === "failed") {
    setStatus("Ошибка");
    setSummary(state.error || "Неизвестная ошибка");
    return false;
  }

  if (state.status === "cancelled") {
    setStatus("Остановлено");
    setSummary(state.error || "Анализ остановлен.");
    return false;
  }

  return false;
}

async function pollSummaryJobState() {
  try {
    const shouldContinue = await syncSummaryJobState();
    if (!shouldContinue) {
      stopSummaryJobPolling();
    }
  } catch (error) {
    stopSummaryJobPolling();
    setLoading(false);
    setStatus("Ошибка");
    setSummary(error instanceof Error ? error.message : "Не удалось получить состояние задачи.");
  }
}

function ensureSummaryJobPolling() {
  if (summaryJobPollId) {
    return;
  }

  summaryJobPollId = setInterval(() => {
    pollSummaryJobState().catch(() => {
      stopSummaryJobPolling();
    });
  }, 1000);
}

async function fetchSummary() {
  syncAutoRangeToNow();

  const period = buildDateRange();
  if (!period) {
    setStatus("Выберите даты");
    setSummary("Нужно задать начало и конец периода.");
    return;
  }

  setLoading(true);
  setStatus("Анализ");
  setSummary("Собираю сводку по выбранным страницам...");

  try {
    await saveSettings();
    await fetchPagesForPeriod();

    await sendRuntimeMessage({
      type: "start-summary-job",
      payload: {
        ...period,
        focus_topic: focusTopicInput.value.trim() || undefined,
      },
    });

    await pollSummaryJobState();
    ensureSummaryJobPolling();
  } catch (error) {
    stopSummaryJobPolling();
    setLoading(false);
    setStatus("Ошибка");
    setSummary(error instanceof Error ? error.message : "Неизвестная ошибка");
  }
}

async function copySummary() {
  if (!rawSummaryText || rawSummaryText === "Пока пусто.") {
    return;
  }

  await navigator.clipboard.writeText(rawSummaryText);
  setStatus("Скопировано");
}

async function stopSummary() {
  try {
    await sendRuntimeMessage({ type: "stop-summary-job" });
    stopSummaryJobPolling();
    setLoading(false);
    setStatus("Остановлено");
    setSummary("Анализ остановлен.");
  } catch (error) {
    setStatus("Ошибка");
    setSummary(error instanceof Error ? error.message : "Не удалось остановить анализ.");
  }
}

async function restartSummary() {
  syncAutoRangeToNow();

  const period = buildDateRange();
  if (!period) {
    setStatus("Выберите даты");
    setSummary("Нужно задать начало и конец периода.");
    return;
  }

  setLoading(true);
  setStatus("Перезапуск");
  setSummary("Перезапускаю анализ по выбранным страницам...");

  try {
    await saveSettings();
    await fetchPagesForPeriod();

    await sendRuntimeMessage({
      type: "restart-summary-job",
      payload: {
        ...period,
        focus_topic: focusTopicInput.value.trim() || undefined,
      },
    });

    await pollSummaryJobState();
    ensureSummaryJobPolling();
  } catch (error) {
    stopSummaryJobPolling();
    setLoading(false);
    setStatus("Ошибка");
    setSummary(error instanceof Error ? error.message : "Не удалось перезапустить анализ.");
  }
}

async function clearPages() {
  await fetch(`${API_BASE_URL}/api/pages`, { method: "DELETE" });
  renderSites([]);
  pageCountValue.textContent = "0";
  setStatus("Страницы очищены");
}

async function clearHistory() {
  await fetch(`${API_BASE_URL}/api/summaries/history`, { method: "DELETE" });
  renderHistory([]);
  setStatus("История очищена");
}

async function handlePeriodChange() {
  autoRangeEnabled = false;
  setStatus("Обновление");
  try {
    await fetchPagesForPeriod();
    setStatus("Готов");
  } catch (error) {
    setStatus("Ошибка");
    sitesList.innerHTML = `<p class="empty-copy">${
      error instanceof Error ? error.message : "Не удалось загрузить список сайтов."
    }</p>`;
  }
}

function ensurePagesRefreshPolling() {
  if (pagesRefreshPollId) {
    return;
  }

  pagesRefreshPollId = setInterval(() => {
    fetchPagesForPeriod().catch(() => {});
  }, 3000);
}

generateButton.addEventListener("click", fetchSummary);
stopButton.addEventListener("click", stopSummary);
restartButton.addEventListener("click", restartSummary);
copyButton.addEventListener("click", copySummary);
clearPagesButton.addEventListener("click", clearPages);
clearHistoryButton.addEventListener("click", clearHistory);
focusTopicInput.addEventListener("change", saveSettings);
startDateInput.addEventListener("change", handlePeriodChange);
endDateInput.addEventListener("change", handlePeriodChange);

loadSettings()
  .then(handlePeriodChange)
  .then(fetchSummaryHistory)
  .then(syncSummaryJobState)
  .then((isRunning) => {
    if (isRunning) {
      ensureSummaryJobPolling();
    }
    ensurePagesRefreshPolling();
  });

setLoading(false);

window.addEventListener("beforeunload", () => {
  stopSummaryJobPolling();
  stopPagesRefreshPolling();
});
