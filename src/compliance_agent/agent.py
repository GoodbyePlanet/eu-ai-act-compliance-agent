import logging
import os
import time
import uuid

from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.events import Event, EventActions
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from compliance_agent.config import (
    AGENT_DESCRIPTION,
    AGENT_INSTRUCTION,
    APP_NAME,
    MAX_SEARCHES,
)
from compliance_agent.billing import BillingService, InsufficientCreditsError
from compliance_agent.guardrails import (
    validate_input_guardrail,
    output_validation_guardrail,
    tool_input_guardrail,
)
from compliance_agent.tools import compliance_search_tool

load_dotenv()
logger = logging.getLogger(__name__)

root_agent = Agent(
    model=LiteLlm(model="anthropic/claude-sonnet-4-5-20250929"),
    name=APP_NAME,
    description=AGENT_DESCRIPTION,
    instruction=AGENT_INSTRUCTION,
    tools=[compliance_search_tool],
    # Guardrails
    before_agent_callback=validate_input_guardrail,
    after_agent_callback=output_validation_guardrail,
    before_tool_callback=tool_input_guardrail,
)

db_url = os.getenv("DATABASE_URL")

if not db_url:
    raise ValueError("DATABASE_URL environment variable not set.")

session_service = DatabaseSessionService(db_url=db_url)
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
billing_service = BillingService()


async def execute(request):
    """
    Execute a compliance assessment for the given AI tool.

    Args:
        request: Request object containing ai_tool name and optional session_id.

    Returns:
        Dictionary with 'summary' (the compliance report) and 'session_id',
        or None if execution fails.
    """
    logger.info(
        f"Request received with message: {request.ai_tool} - with session ID {request.session_id}"
    )

    if request.user_email:
        user_email = request.user_email
    else:
        user_email = f"Guest_{uuid.uuid4()}"  # TODO: Later on we want to allow guest users to use the app

    current_session = request.session_id if request.session_id else f"session_{uuid.uuid4()}"
    request_id = request.request_id if request.request_id else str(uuid.uuid4())

    if billing_service.is_enabled():
        if not request.user_sub:
            raise InsufficientCreditsError("Missing authenticated billing user")
        await billing_service.consume_daily_credit_for_request(
            user_id=request.user_sub,
            request_id=request_id,
            session_id=current_session,
            ai_tool=request.ai_tool,
        )

    existing_session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_email, session_id=current_session
    )

    is_follow_up = False

    if existing_session is None:
        logger.info(f"No session found. Initializing new session with ID: {current_session}")
        session_obj = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_email,
            state={"ai_tool": request.ai_tool},
            session_id=current_session
        )
    else:
        logger.info(f"Session {current_session} retrieved successfully.")
        session_obj = existing_session

        if session_obj.state and session_obj.state.get("ai_tool"):
            is_follow_up = True
        else:
            # Fallback just in case the state was lost but session existed
            update_event = Event(
                invocation_id=str(uuid.uuid4()),
                author="system",
                actions=EventActions(state_delta={"ai_tool": request.ai_tool}),
                timestamp=time.time()
            )
            await session_service.append_event(session=session_obj, event=update_event)

    if is_follow_up:
        prompt = request.ai_tool
        logger.info(f"Executing Human-in-the-Loop follow-up: {prompt}")
    else:
        prompt = f"Assess AI tool - {request.ai_tool}"
        logger.info(f"Executing Initial Assessment for: {request.ai_tool}")

    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    search_count = 0

    try:
        async for event in runner.run_async(
                user_id=user_email, session_id=current_session, new_message=message
        ):
            if event.content and any(
                    part.function_call for part in event.content.parts
            ):
                search_count += 1
                logger.info(f"Agent is using tool (Search {search_count}/{MAX_SEARCHES})")

                if search_count > MAX_SEARCHES:
                    logger.warning(
                        "Max search limit reached! Forcing agent to synthesize results."
                    )
                    error_summary = "### Search Limit Reached\nThe agent exceeded the maximum search limit while researching. Please refine your query or check specific tool documentation manually."
                    session_obj = await session_service.get_session(
                        app_name=APP_NAME, user_id=user_email, session_id=current_session
                    )
                    sys_event = Event(
                        invocation_id=str(uuid.uuid4()),
                        author="system",
                        actions=EventActions(state_delta={"summary": error_summary}),
                        timestamp=time.time()
                    )
                    await session_service.append_event(session=session_obj, event=sys_event)
                    return {
                        "summary": "### Search Limit Reached\nThe agent exceeded the maximum search limit while researching. Please refine your query or check specific tool documentation manually.",
                        "session_id": current_session,
                    }

            if event.is_final_response():
                final_summary = event.content.parts[0].text

                session_obj = await session_service.get_session(
                    app_name=APP_NAME, user_id=user_email, session_id=current_session
                )
                sys_event = Event(
                    invocation_id=str(uuid.uuid4()),
                    author="system",
                    actions=EventActions(state_delta={"summary": final_summary}),
                    timestamp=time.time()
                )
                await session_service.append_event(session=session_obj, event=sys_event)

                return {
                    "summary": final_summary,
                    "session_id": current_session,
                }
    except Exception as e:
        logger.error(f"Error during execution: {e}")

    return None
