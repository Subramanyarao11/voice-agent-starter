from fastapi import APIRouter, UploadFile, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.services.voice import STT_PROVIDERS, get_or_synthesize
from app.agents.graph import agent_graph, AgentState

router = APIRouter()


@router.post("/turn/{session_id}")
async def take_turn(
    session_id: str,
    audio: UploadFile,
    state_code: str,
    language_code: str,
    db: Session = Depends(get_session),
):
    """
    One conversational turn: audio in -> transcribe -> run agent graph ->
    synthesize response -> audio out. This is the endpoint telephony
    (Exotel webhook) or the browser-mic demo both call.
    """
    audio_bytes = await audio.read()

    transcript = await STT_PROVIDERS["openai_whisper"].transcribe(audio_bytes, language_code)

    state = AgentState(
        session_id=session_id,
        state_code=state_code,
        language_code=language_code,
        transcript=transcript,
    )
    result_state = agent_graph.invoke(state)

    # TODO: pass a real redis client here instead of None once wired up
    # response_audio = await get_or_synthesize(
    #     result_state["response_text"], language_code, voice_id="meera", redis_client=redis
    # )

    return {
        "transcript": transcript,
        "response_text": result_state["response_text"],
        "needs_escalation": result_state["needs_escalation"],
        # "response_audio": response_audio,  # base64 or URL once wired
    }
