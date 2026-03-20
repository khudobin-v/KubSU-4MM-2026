const IGNORE_URL_PREFIXES = ["chrome://", "about:", "edge://"];
const API_BASE_URL = "http://127.0.0.1:8000";
const PAYLOAD_ENDPOINT = `${API_BASE_URL}/api/payloads`;
const SUMMARY_ENDPOINT = `${API_BASE_URL}/api/pages/summary`;
const SUMMARY_JOB_STATE_KEY = "summary_job_state";
const SUMMARY_JOB_TIMEOUT_MS = 90000;

let activeSummaryJob = null;
let activeSummaryAbortController = null;
let activeSummaryAbortReason = null;

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
  const response = await fetch(PAYLOAD_ENDPOINT, {
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

async function getSummaryJobState() {
  const stored = await chrome.storage.local.get(SUMMARY_JOB_STATE_KEY);
  const state = stored[SUMMARY_JOB_STATE_KEY] || null;
  if (!state) {
    return null;
  }

  if (state.status === "running" && !activeSummaryJob) {
    const interruptedState = {
      ...state,
      status: "failed",
      completed_at: new Date().toISOString(),
      error: "Анализ был прерван. Запустите его снова.",
    };
    await saveSummaryJobState(interruptedState);
    return interruptedState;
  }

  return state;
}

async function saveSummaryJobState(state) {
  await chrome.storage.local.set({ [SUMMARY_JOB_STATE_KEY]: state });
  return state;
}

async function saveSummaryJobStateIfCurrent(jobId, state) {
  const currentState = await getSummaryJobState();
  if (currentState?.id !== jobId) {
    return currentState;
  }
  return saveSummaryJobState(state);
}

async function runSummaryJob(request) {
  const jobId = Date.now();
  activeSummaryAbortController = new AbortController();
  activeSummaryAbortReason = null;
  const timeoutId = setTimeout(() => {
    if (activeSummaryAbortController) {
      activeSummaryAbortReason = "timeout";
      activeSummaryAbortController.abort();
    }
  }, SUMMARY_JOB_TIMEOUT_MS);
  const runningState = {
    id: jobId,
    status: "running",
    started_at: new Date().toISOString(),
    request,
    summary: null,
    model: null,
    error: null,
  };

  await saveSummaryJobState(runningState);

  try {
    const response = await fetch(SUMMARY_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: activeSummaryAbortController.signal,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `API error: ${response.status}`);
    }

      await saveSummaryJobStateIfCurrent(jobId, {
        ...runningState,
        status: "completed",
        completed_at: new Date().toISOString(),
        summary: payload.summary,
        model: payload.model,
      });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      const wasTimedOut = activeSummaryAbortReason === "timeout";
      await saveSummaryJobStateIfCurrent(jobId, {
        ...runningState,
        status: wasTimedOut ? "failed" : "cancelled",
        completed_at: new Date().toISOString(),
        error: wasTimedOut ? "Превышено время ожидания анализа" : "Анализ остановлен",
      });
      return;
    }

    await saveSummaryJobStateIfCurrent(jobId, {
      ...runningState,
      status: "failed",
      completed_at: new Date().toISOString(),
      error: error instanceof Error ? error.message : "Неизвестная ошибка",
    });
  } finally {
    clearTimeout(timeoutId);
    activeSummaryJob = null;
    activeSummaryAbortController = null;
    activeSummaryAbortReason = null;
  }
}

async function startSummaryJob(request) {
  const currentState = await getSummaryJobState();
  if (currentState?.status === "running" && activeSummaryJob) {
    return currentState;
  }

  activeSummaryJob = runSummaryJob(request);
  return getSummaryJobState();
}

async function stopSummaryJob() {
  const currentState = await getSummaryJobState();
  if (activeSummaryAbortController && currentState?.status === "running") {
    activeSummaryAbortReason = "manual";
    activeSummaryAbortController.abort();
    return currentState;
  }

  await saveSummaryJobState({
    ...(currentState || {}),
    status: "cancelled",
    completed_at: new Date().toISOString(),
    error: "Анализ остановлен",
  });
  return getSummaryJobState();
}

async function restartSummaryJob(request) {
  if (activeSummaryAbortController) {
    activeSummaryAbortReason = "manual";
    activeSummaryAbortController.abort();
  }
  return startSummaryJob(request);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) {
    return undefined;
  }

  if (message.type === "view") {
    if (
      !message.url ||
      IGNORE_URL_PREFIXES.some((prefix) => message.url.startsWith(prefix))
    ) {
      return undefined;
    }

    const payload = buildPayload(message);
    console.log("Полезная нагрузка:", payload);

    sendPayloadToApi(payload).catch((error) => {
      console.error("Ошибка отправки payload в API:", error);
    });
    return undefined;
  }

  if (message.type === "start-summary-job") {
    startSummaryJob(message.payload)
      .then((state) => sendResponse({ ok: true, state }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Неизвестная ошибка",
        }),
      );
    return true;
  }

  if (message.type === "get-summary-job-state") {
    getSummaryJobState()
      .then((state) => sendResponse({ ok: true, state }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Неизвестная ошибка",
        }),
      );
    return true;
  }

  if (message.type === "stop-summary-job") {
    stopSummaryJob()
      .then((state) => sendResponse({ ok: true, state }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Неизвестная ошибка",
        }),
      );
    return true;
  }

  if (message.type === "restart-summary-job") {
    restartSummaryJob(message.payload)
      .then((state) => sendResponse({ ok: true, state }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Неизвестная ошибка",
        }),
      );
    return true;
  }

  return undefined;
});
