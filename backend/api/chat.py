"""
Design chat API - Claude-based chatbot for system design guidance.
Provides real-time feedback and coaching for candidates.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from backend.services.ai_service import AIService
from backend.database import get_db_session
from backend.models.problem import Problem

router = APIRouter()
ai_service = AIService()


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request to chat about a system design."""
    problem_id: int = Field(..., description="ID of the problem being worked on")
    message: str = Field(..., min_length=1, max_length=4000, description="User's message")
    conversation_history: List[ChatMessage] = Field(
        default=[],
        description="Previous messages in the conversation"
    )
    current_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current database schema design"
    )
    current_api_spec: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current API specification"
    )
    current_diagram: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current diagram data (from canvas)"
    )


class DiagramFeedback(BaseModel):
    """Structured feedback about a diagram."""
    strengths: List[str] = []
    weaknesses: List[str] = []
    suggested_improvements: List[str] = []
    is_on_track: bool = True
    score: Optional[int] = None


class ChatResponse(BaseModel):
    """Response from the design chat."""
    response: str = Field(..., description="AI's response message")
    diagram_feedback: Optional[DiagramFeedback] = Field(
        default=None,
        description="Structured feedback about the diagram if provided"
    )
    suggested_improvements: List[str] = Field(
        default=[],
        description="List of suggested improvements"
    )
    is_on_track: bool = Field(
        default=True,
        description="Whether the candidate is heading in the right direction"
    )
    demo_mode: bool = Field(
        default=False,
        description="Whether this is a demo mode response"
    )


# Reference solutions for different problem types
SOLUTION_REFERENCES = {
    "url shortener": """
Key components for a URL Shortener solution:

1. **Key Generation Service (KGS)**: Pre-generate unique short codes using base62 encoding (a-z, A-Z, 0-9).
   Store unused keys in a Redis SET and use SPOP for O(1) key allocation.

2. **Database Schema**:
   - urls table: id, short_code (unique indexed), original_url, created_at, expires_at, click_count
   - Optional: kgs_keys table to track key status

3. **API Endpoints**:
   - POST /api/v1/urls - Create short URL
   - GET /api/v1/urls/{code} - Get URL info
   - GET /{code} - Redirect to original URL
   - GET /api/v1/urls/{code}/stats - Get click statistics
   - DELETE /api/v1/urls/{code} - Delete URL
   - GET /health - Health check

4. **Caching**: Redis cache for URL mappings (1-hour TTL)

5. **Scalability**:
   - Stateless API servers (horizontally scalable)
   - Key space: 62^7 = 3.5 trillion unique codes
   - Read-heavy optimization with cache

6. **Reliability**:
   - Cache miss falls back to database
   - KGS pool auto-replenishes
   - Graceful degradation if Redis unavailable

Tests validate: health endpoint, URL CRUD, expiration, click counting, KGS uniqueness, concurrent requests.
""",
}


def get_solution_reference(problem_title: str) -> str:
    """Get the reference solution for a problem type."""
    title_lower = problem_title.lower()
    for key, solution in SOLUTION_REFERENCES.items():
        if key in title_lower:
            return solution
    return ""


@router.post("/", response_model=ChatResponse)
async def chat_about_design(request: ChatRequest):
    """
    Chat with AI about system design.

    The AI will:
    - Guide candidates toward a correct solution
    - Evaluate their current diagram and provide feedback
    - Answer questions about system design concepts
    - Provide constructive criticism and suggestions
    """
    # Get the problem details
    with get_db_session() as session:
        problem = session.query(Problem).filter(Problem.id == request.problem_id).first()
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")

        problem_description = problem.description
        problem_title = problem.title

    # Get reference solution
    solution_reference = get_solution_reference(problem_title)

    # Convert conversation history to the format expected by the AI service
    history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]

    # Call the AI service
    result = await ai_service.chat_about_design(
        problem_description=problem_description,
        problem_title=problem_title,
        candidate_message=request.message,
        conversation_history=history,
        current_schema=request.current_schema,
        current_api_spec=request.current_api_spec,
        current_diagram=request.current_diagram,
        solution_reference=solution_reference,
    )

    # Build response
    diagram_feedback = None
    if result.get("diagram_feedback"):
        df = result["diagram_feedback"]
        diagram_feedback = DiagramFeedback(
            strengths=df.get("strengths", []),
            weaknesses=df.get("weaknesses", []),
            suggested_improvements=df.get("suggested_improvements", []),
            is_on_track=df.get("is_on_track", True),
            score=df.get("score"),
        )

    return ChatResponse(
        response=result["response"],
        diagram_feedback=diagram_feedback,
        suggested_improvements=result.get("suggested_improvements", []),
        is_on_track=result.get("is_on_track", True),
        demo_mode=result.get("demo_mode", False),
    )


@router.post("/evaluate-diagram")
async def evaluate_diagram(
    problem_id: int,
    diagram_data: Dict[str, Any],
):
    """
    Evaluate a diagram and provide structured feedback.

    This is a focused endpoint just for diagram evaluation,
    separate from the conversational chat.
    """
    # Get the problem details
    with get_db_session() as session:
        problem = session.query(Problem).filter(Problem.id == problem_id).first()
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")

        problem_title = problem.title

    # Get reference solution
    solution_reference = get_solution_reference(problem_title)

    # Call the AI service with just the diagram
    result = await ai_service.chat_about_design(
        problem_description=problem.description,
        problem_title=problem_title,
        candidate_message="Please evaluate my diagram and provide detailed feedback.",
        conversation_history=[],
        current_diagram=diagram_data,
        solution_reference=solution_reference,
    )

    return {
        "feedback": result.get("response"),
        "diagram_feedback": result.get("diagram_feedback"),
        "suggested_improvements": result.get("suggested_improvements", []),
        "is_on_track": result.get("is_on_track", True),
    }
