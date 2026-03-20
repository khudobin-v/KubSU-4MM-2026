from __future__ import annotations

import re
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.models import (
    BrowserPayload,
    ClearResponse,
    ModelProxyRequest,
    ModelProxyResponse,
    PageSummaryRequest,
    PageSummaryResponse,
    PageVisitItem,
    PageVisitsResponse,
    SavePayloadResponse,
    SummaryHistoryItem,
    SummaryHistoryResponse,
)
from app.ollama_client import OllamaClient
from app.repository import PageViewRepository

router = APIRouter()
PAGE_TEXT_CHAR_LIMIT = 4000
PAGE_DIGEST_CHAR_LIMIT = 900


class PageDigest(TypedDict):
    url: str
    title: str
    source_timestamp: str
    digest: str
    is_relevant: bool


def _get_repository(request: Request) -> PageViewRepository:
    return request.app.state.repository


def _get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.ollama_client


def _normalize_topic_tokens(focus_topic: str) -> list[str]:
    normalized = focus_topic.lower().replace("ё", "е")
    return [token for token in re.split(r"[^a-zа-я0-9]+", normalized) if len(token) >= 3]


def _has_explicit_topic_match(page_views: list[dict[str, str]], focus_topic: str | None) -> bool:
    if not focus_topic:
        return True

    tokens = _normalize_topic_tokens(focus_topic)
    if not tokens:
        return True

    searchable_text = "\n".join(
        " ".join(
            (
                page_view["url"],
                page_view["title"],
                page_view["lang"],
                page_view["text"],
            )
        )
        for page_view in page_views
    ).lower()

    return any(token in searchable_text for token in tokens)


def _is_page_relevant(page_view: dict[str, str], focus_topic: str | None) -> bool:
    if not focus_topic:
        return True

    tokens = _normalize_topic_tokens(focus_topic)
    if not tokens:
        return True

    searchable_text = " ".join(
        (
            page_view["url"],
            page_view["title"],
            page_view["lang"],
            page_view["text"],
        )
    ).lower()
    return any(token in searchable_text for token in tokens)


def _truncate_page_text(text: str) -> str:
    if len(text) <= PAGE_TEXT_CHAR_LIMIT:
        return text
    return f"{text[:PAGE_TEXT_CHAR_LIMIT].rstrip()}\n\n[Текст страницы был сокращён]"


def _clean_text_for_digest(text: str) -> str:
    normalized = text.replace("\n", " ").replace("\r", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _build_page_digest(page_view: dict[str, str]) -> str:
    text = _clean_text_for_digest(_truncate_page_text(page_view["text"]))
    if not text:
        return "На странице мало полезного текста для анализа."

    sentences = [
        sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()
    ]
    chunks: list[str] = []
    total_length = 0

    for sentence in sentences:
        if len(sentence) < 50:
            continue
        if len(re.findall(r"[^\w\s.,!?():;\"'/-]", sentence)) > 6:
            continue
        next_length = total_length + len(sentence) + (1 if chunks else 0)
        if next_length > PAGE_DIGEST_CHAR_LIMIT:
            break
        chunks.append(sentence)
        total_length = next_length
        if len(chunks) >= 3:
            break

    if not chunks:
        fallback = text[:PAGE_DIGEST_CHAR_LIMIT].strip()
        return fallback or "На странице мало полезного текста для анализа."

    return " ".join(chunks)


def _build_summary_prompt(
    page_digests: list[PageDigest],
    focus_topic: str | None,
    relevant_count: int,
    irrelevant_count: int,
) -> str:
    topic_line = (
        f"Целевая тема пользователя: {focus_topic}."
        if focus_topic
        else "Целевая тема пользователя не указана. Сфокусируйся на ключевых технических идеях."
    )
    page_chunks = [
        (
            f"Статус: {'РЕЛЕВАНТНО' if page_digest['is_relevant'] else 'ОТВЛЕЧЕНИЕ'}\n"
            f"URL: {page_digest['url']}\n"
            f"Заголовок: {page_digest['title']}\n"
            f"Время просмотра: {page_digest['source_timestamp']}\n"
            f"Выжимка страницы:\n{page_digest['digest']}"
        )
        for page_digest in page_digests
    ]
    joined_pages = "\n\n---\n\n".join(page_chunks)
    return (
        "Ниже передана история просмотренных страниц пользователя. "
        "Ты анализируешь только содержимое этих страниц. "
        "Это не диалог, не обсуждение промптов и не запрос на советы. "
        "Обращайся к человеку напрямую на 'ты'. Не используй формулировки в третьем лице "
        "вроде 'пользователь изучил', 'пользователь продемонстрировал' и подобные. "
        "Запрещено хвалить сам запрос, запрещено писать 'отлично', 'вот улучшения', "
        "'вот несколько советов', 'надеюсь, это поможет', 'я готов помочь' и любые похожие "
        "мета-комментарии. "
        "Запрещено обсуждать промпт, модель, формат задачи и способы использования результата. "
        "Запрещено выдумывать детали, которых нет в выжимках страниц. "
        "Если в просмотренных страницах нет точного шага, технологии или команды, "
        "не добавляй это от себя. "
        "Опирайся только на явно присутствующие факты из выжимок и заголовков. "
        f"{topic_line} "
        f"Релевантных страниц: {relevant_count}. Нерелевантных страниц: {irrelevant_count}. "
        "Сначала определи, относится ли основная масса просмотренного контента к целевой теме. "
        "Считай контент относящимся к теме только если тема действительно и явно раскрывается в "
        "самих просмотренных страницах. Общая техническая направленность не считается достаточной. "
        "Например, если целевая тема Flutter, то контент про Python, FastAPI, Docker, GitHub, "
        "LLM, новости, браузерные расширения или общую разработку не считается релевантным, "
        "если в нём нет существенного и прямого материала именно про Flutter. "
        "Если целевая тема явно не упоминается и не раскрывается, ты обязан считать контент "
        "нерелевантным. В таком случае запрещено хвалить пользователя за фокус на теме. "
        "Если релевантных страниц больше нуля, ты обязан признать, что пользователь действительно "
        "изучал целевую тему. В этом случае нельзя писать, что весь контент не относится к теме. "
        "Если есть и релевантные страницы, и отвлечения, сначала подробно суммируй "
        "релевантную часть, "
        "а затем кратко и жёстко отметь, что были отвлекающие страницы. "
        "После этого отвечай строго в одном из двух человеческих форматов.\n\n"
        "Если есть релевантный контент:\n"
        "Сначала 1-2 предложения с похвалой за правильный фокус. "
        "Потом дай подробную, глубокую и структурированную сводку релевантного контента "
        "обычным человеческим текстом. После основной сводки выдели ключевые идеи "
        "и практические выводы, "
        "но без служебных меток в квадратных скобках. Если были отвлечения, "
        "в конце добавь 1-2 предложения "
        "с холодным осуждением за эти отвлечения, "
        "но не перечёркивай основную релевантную работу.\n\n"
        "Если контент не относится к теме:\n"
        "Сначала коротко, в 1-2 предложениях, перескажи суть. "
        "Потом одним естественным предложением прямо скажи, "
        "что этот контент не относится к целевой теме. "
        "После этого дай жёсткий, холодный выговор за отвлечение "
        "и заверши коротким человеческим указанием, "
        "к чему именно нужно вернуться по теме. "
        "Не используй служебные заголовки вроде '[ОЦЕНКА]', '[КРАТКО]', '[ВЫГОВОР]' и подобные. "
        "Текст должен выглядеть как естественный, но дисциплинированный ответ человека.\n\n"
        "Говори только о просмотренных страницах. "
        "Не придумывай новых советов, если их нет в самих страницах.\n\n"
        "Контент для анализа:\n"
        f"{joined_pages}"
    )


def _build_off_topic_response(page_views: list[dict[str, str]], focus_topic: str) -> str:
    unique_titles = []
    for page_view in page_views:
        title = page_view["title"].strip() or page_view["url"].strip()
        if title and title not in unique_titles:
            unique_titles.append(title)

    titles_preview = ", ".join(unique_titles[:3]) if unique_titles else "разрозненные страницы"
    factual_part = f"Вы просматривали материалы вроде: {titles_preview}."

    return (
        f"{factual_part} "
        f"Но это не относится к теме {focus_topic}. "
        "Вы снова распыляетесь на посторонний материал и теряете темп. "
        f"Немедленно вернитесь к изучению {focus_topic} "
        "и перестаньте подменять фокус случайным контентом."
    )


@router.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Hello World"}


@router.get("/items/{item_id}")
async def read_item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


@router.post("/api/payloads")
async def create_payload(payload: BrowserPayload, request: Request) -> SavePayloadResponse:
    repository = _get_repository(request)
    record_id = repository.save_payload(payload)
    request.app.state.logger.info("Saved payload id=%s url=%s", record_id, payload.url)
    return SavePayloadResponse(status="saved", id=record_id)


@router.post("/api/model/generate")
async def generate_model_response(
    payload: ModelProxyRequest, request: Request
) -> ModelProxyResponse:
    ollama_client = _get_ollama_client(request)

    try:
        model_response = await ollama_client.generate(
            payload.prompt,
            focus_topic=payload.focus_topic,
        )
    except httpx.HTTPError as exc:
        request.app.state.logger.exception("Ollama proxy request failed")
        raise HTTPException(status_code=502, detail="Failed to reach model backend") from exc

    return ModelProxyResponse(model=ollama_client.model, response=model_response)


@router.post("/api/pages/summary")
async def summarize_pages(payload: PageSummaryRequest, request: Request) -> PageSummaryResponse:
    if payload.start_at > payload.end_at:
        raise HTTPException(status_code=400, detail="start_at must be less than or equal to end_at")

    repository = _get_repository(request)
    ollama_client = _get_ollama_client(request)
    page_views = repository.get_page_views_for_period(payload.start_at, payload.end_at)

    if not page_views:
        raise HTTPException(status_code=404, detail="No pages found for selected period")

    has_explicit_topic_match = _has_explicit_topic_match(page_views, payload.focus_topic)
    if not has_explicit_topic_match:
        summary = _build_off_topic_response(page_views, payload.focus_topic or "Без темы")
        repository.save_summary(
            focus_topic=payload.focus_topic or "Без темы",
            start_at=payload.start_at,
            end_at=payload.end_at,
            page_count=len(page_views),
            summary=summary,
        )
        return PageSummaryResponse(
            model="rule-based",
            page_count=len(page_views),
            summary=summary,
        )

    try:
        page_digests: list[PageDigest] = []
        relevant_count = 0
        irrelevant_count = 0
        for page_view in page_views:
            is_relevant = _is_page_relevant(page_view, payload.focus_topic)
            if is_relevant:
                relevant_count += 1
            else:
                irrelevant_count += 1
            page_digests.append(
                {
                    "url": page_view["url"],
                    "title": page_view["title"],
                    "source_timestamp": page_view["source_timestamp"],
                    "digest": _build_page_digest(page_view),
                    "is_relevant": is_relevant,
                }
            )

        prompt = _build_summary_prompt(
            page_digests,
            payload.focus_topic,
            relevant_count,
            irrelevant_count,
        )
        summary = await ollama_client.generate(prompt, focus_topic=payload.focus_topic)
    except httpx.HTTPError as exc:
        request.app.state.logger.exception("Ollama summary request failed")
        raise HTTPException(status_code=502, detail="Failed to reach model backend") from exc

    repository.save_summary(
        focus_topic=payload.focus_topic or "Без темы",
        start_at=payload.start_at,
        end_at=payload.end_at,
        page_count=len(page_views),
        summary=summary,
    )

    return PageSummaryResponse(
        model=ollama_client.model,
        page_count=len(page_views),
        summary=summary,
    )


@router.post("/api/pages/list")
async def list_pages(payload: PageSummaryRequest, request: Request) -> PageVisitsResponse:
    if payload.start_at > payload.end_at:
        raise HTTPException(status_code=400, detail="start_at must be less than or equal to end_at")

    repository = _get_repository(request)
    page_views = repository.get_page_views_for_period(payload.start_at, payload.end_at)

    return PageVisitsResponse(
        page_count=len(page_views),
        items=[
            PageVisitItem(
                url=page_view["url"],
                title=page_view["title"],
                lang=page_view["lang"],
                source_timestamp=page_view["source_timestamp"],
            )
            for page_view in page_views
        ],
    )


@router.get("/api/summaries/history")
async def get_summary_history(request: Request) -> SummaryHistoryResponse:
    repository = _get_repository(request)
    history_items = repository.get_summary_history()

    return SummaryHistoryResponse(
        items=[
            SummaryHistoryItem(
                id=int(item["id"]),
                focus_topic=str(item["focus_topic"]),
                start_at=str(item["start_at"]),
                end_at=str(item["end_at"]),
                page_count=int(item["page_count"]),
                summary=str(item["summary"]),
                created_at=str(item["created_at"]),
            )
            for item in history_items
        ]
    )


@router.delete("/api/summaries/history")
async def clear_summary_history(request: Request) -> ClearResponse:
    repository = _get_repository(request)
    repository.clear_summary_history()
    return ClearResponse(status="cleared")


@router.delete("/api/pages")
async def clear_page_views(request: Request) -> ClearResponse:
    repository = _get_repository(request)
    repository.clear_page_views()
    return ClearResponse(status="cleared")
