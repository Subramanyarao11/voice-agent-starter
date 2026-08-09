"""Source-grounded search over the persistent OpenAI Vector Store."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from sahaayak_agent.retrieval import OpenAIRetrieval, RagOutOfScope, RagUnavailable
from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_api.deps import get_rag
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_request_limits
from sahaayak_common import BudgetError
from sahaayak_contracts import RagAnswerResponse, RagSearchRequest, RagSearchResponse

router = APIRouter(prefix="/api/rag", tags=["retrieval"])


@router.post("/answer", response_model=RagAnswerResponse)
async def answer_from_sources(
    payload: RagSearchRequest,
    request: Request,
    http_response: Response,
    rag: OpenAIRetrieval | None = Depends(get_rag),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> RagAnswerResponse:
    decision = await enforce_request_limits(
        request, session_id=principal.session_id, bucket="rag"
    )
    apply_rate_limit_headers(http_response, decision)
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG is not configured")
    try:
        return await rag.answer(
            payload.query,
            max_results=payload.max_results,
            language_code=payload.language_code or principal.language_code,
            subject=principal.session_id,
            state_code=principal.state_code,
        )
    except RagOutOfScope as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Sahaayak supports government schemes, scholarships, jobs, "
                "eligibility, and applications."
            ),
        ) from exc
    except RagUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BudgetError as exc:
        raise HTTPException(status_code=503, detail="RAG budget is unavailable") from exc


@router.post("/search", response_model=RagSearchResponse)
async def search_sources(
    payload: RagSearchRequest,
    request: Request,
    http_response: Response,
    rag: OpenAIRetrieval | None = Depends(get_rag),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> RagSearchResponse:
    decision = await enforce_request_limits(
        request, session_id=principal.session_id, bucket="rag"
    )
    apply_rate_limit_headers(http_response, decision)
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG is not configured")
    try:
        sources = await rag.search(
            payload.query,
            max_results=payload.max_results,
            subject=principal.session_id,
            language_code=payload.language_code or principal.language_code,
            state_code=principal.state_code,
        )
        return RagSearchResponse(query=payload.query, sources=sources)
    except RagOutOfScope as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Sahaayak supports government schemes, scholarships, jobs, "
                "eligibility, and applications."
            ),
        ) from exc
    except RagUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BudgetError as exc:
        raise HTTPException(status_code=503, detail="RAG budget is unavailable") from exc
