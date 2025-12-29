"""
Design chat API - Claude-based chatbot for system design guidance.
Provides real-time feedback and coaching for candidates.

Supports three difficulty levels:
- Easy (L5): Senior SWE - Core functionality with basic scalability
- Medium (L6): Staff Engineer - Production-ready with high availability
- Hard (L7): Principal Engineer - Global-scale with advanced optimizations

Includes content moderation to ensure appropriate usage.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.services.ai_service import AIService
from backend.services.moderation_service import get_moderation_service, ModerationResult
from backend.database import get_db
from backend.models.problem import Problem, DIFFICULTY_LEVELS
from backend.models.user import User
from backend.auth.jwt_handler import get_current_user_optional

router = APIRouter()
ai_service = AIService()
moderation_service = get_moderation_service()

# Track user violations in memory (in production, use Redis or database)
_user_violations: Dict[int, List[ModerationResult]] = {}


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Request to chat about a system design."""
    problem_id: int
    message: str
    conversation_history: List[ChatMessage] = []
    current_schema: Optional[Dict[str, Any]] = None
    current_api_spec: Optional[Dict[str, Any]] = None
    current_diagram: Optional[Dict[str, Any]] = None
    difficulty_level: Optional[str] = None  # easy/medium/hard


class DiagramFeedback(BaseModel):
    """Structured feedback about a diagram."""
    strengths: List[str] = []
    weaknesses: List[str] = []
    suggested_improvements: List[str] = []
    is_on_track: bool = True
    score: Optional[int] = None


class ChatResponse(BaseModel):
    """Response from the design chat."""
    response: str
    diagram_feedback: Optional[DiagramFeedback] = None
    suggested_improvements: List[str] = []
    is_on_track: bool = True
    demo_mode: bool = False


class DesignSummaryRequest(BaseModel):
    """Request to generate a design summary."""
    problem_id: int
    difficulty_level: str = "medium"  # easy/medium/hard
    conversation_history: List[ChatMessage] = []
    current_schema: Optional[Dict[str, Any]] = None
    current_api_spec: Optional[Dict[str, Any]] = None
    current_diagram: Optional[Dict[str, Any]] = None


class DesignSummaryResponse(BaseModel):
    """Response containing the final design summary."""
    summary: str
    key_components: List[str]
    strengths: List[str]
    areas_for_improvement: List[str]
    overall_score: Optional[int] = None
    difficulty_level: str
    level_info: Dict[str, str]
    demo_mode: bool = False


# Level-specific requirements for URL Shortener using KGS
URL_SHORTENER_REQUIREMENTS = {
    "easy": {
        "level": "L5",
        "title": "Senior Software Engineer",
        "focus": "Core functionality with basic scalability",
        "requirements": """
**L5 (Senior SWE) URL Shortener Requirements:**

Focus on building a working URL shortener with KGS (Key Generation Service).

**Required Components:**
1. **Key Generation Service (KGS)**:
   - Pre-generate unique short codes using base62 encoding
   - Store unused keys in a simple queue or database table
   - Basic key allocation with collision avoidance

2. **Database Design**:
   - urls table: id, short_code, original_url, created_at
   - Basic indexing on short_code

3. **Core API Endpoints**:
   - POST /api/v1/urls - Create short URL using KGS
   - GET /{code} - Redirect to original URL
   - GET /health - Health check

4. **Basic Reliability**:
   - Simple error handling
   - Input validation

**Evaluation Criteria:**
- KGS generates unique codes without collisions
- Redirection works correctly
- Basic error handling in place
- Clean, readable code
""",
    },
    "medium": {
        "level": "L6",
        "title": "Staff Engineer",
        "focus": "Production-ready design with high availability",
        "requirements": """
**L6 (Staff SWE) URL Shortener Requirements:**

Build a production-ready URL shortener with KGS, caching, and analytics.

**Required Components:**
1. **Key Generation Service (KGS)**:
   - Pre-generate unique short codes using base62 encoding
   - Redis-based key pool with SPOP for O(1) allocation
   - Automatic pool replenishment
   - Key length optimization (6-7 characters)

2. **Database Design**:
   - urls table: id, short_code (unique indexed), original_url, created_at, expires_at, click_count
   - kgs_keys table for key management
   - Proper indexing strategy

3. **API Endpoints**:
   - POST /api/v1/urls - Create short URL (with optional expiration)
   - GET /api/v1/urls/{code} - Get URL info
   - GET /{code} - Redirect with analytics tracking
   - GET /api/v1/urls/{code}/stats - Click statistics
   - DELETE /api/v1/urls/{code} - Delete URL
   - GET /health - Health check

4. **Caching Layer**:
   - Redis cache for URL lookups (1-hour TTL)
   - Cache-aside pattern
   - Graceful fallback to database

5. **Reliability**:
   - Horizontal scalability (stateless API)
   - Cache miss handling
   - Rate limiting basics

**Evaluation Criteria:**
- All L5 requirements plus:
- Efficient KGS with auto-replenishment
- Proper caching strategy
- Analytics tracking
- Expiration handling
- Clean API design
""",
    },
    "hard": {
        "level": "L7",
        "title": "Principal Engineer",
        "focus": "Global-scale architecture with advanced optimizations",
        "requirements": """
**L7 (Principal SWE) URL Shortener Requirements:**

Design a globally-distributed, highly-available URL shortener at massive scale.

**Required Components:**
1. **Distributed Key Generation Service (KGS)**:
   - Pre-generate unique short codes using base62 encoding
   - Range-based key allocation for distributed KGS instances
   - Zero-collision guarantee across regions
   - Hot standby for KGS failover
   - Key recycling for expired URLs

2. **Database Architecture**:
   - Primary-replica setup with read replicas per region
   - Sharding strategy (by short_code hash or range)
   - urls table: id, short_code, original_url, user_id, created_at, expires_at, click_count, metadata
   - Separate analytics table for high-volume writes
   - TTL-based cleanup jobs

3. **Global API Design**:
   - POST /api/v1/urls - Create with custom alias support
   - GET /api/v1/urls/{code} - Get URL info with full metadata
   - GET /{code} - Redirect (geo-optimized)
   - GET /api/v1/urls/{code}/stats - Detailed analytics
   - GET /api/v1/urls/{code}/analytics - Time-series data
   - DELETE /api/v1/urls/{code} - Soft delete
   - PATCH /api/v1/urls/{code} - Update expiration/metadata
   - GET /health - Deep health check

4. **Multi-tier Caching**:
   - Edge caching with CDN for redirects
   - Regional Redis clusters
   - Local in-memory cache (L1)
   - Write-through for analytics

5. **High Availability**:
   - Multi-region deployment
   - Auto-failover for all components
   - Circuit breakers
   - Bulkhead pattern

6. **Performance & Scale**:
   - 100K+ redirects/second capacity
   - P99 latency < 50ms for redirects
   - Async analytics processing
   - Batch key pre-generation

7. **Advanced Features**:
   - Custom short URLs/vanity codes
   - Link preview/unfurling
   - Abuse detection
   - A/B testing support

**Evaluation Criteria:**
- All L5 and L6 requirements plus:
- Global distribution strategy
- Zero-downtime deployment plan
- Capacity planning discussion
- Cost optimization considerations
- Security best practices
- Monitoring and observability
""",
    },
}

# Reference solutions for different problem types
SOLUTION_REFERENCES = {
    "url shortener": """
Key components for a URL Shortener solution (all levels use KGS):

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


def get_level_requirements(problem_title: str, difficulty: str = "medium") -> str:
    """
    Get level-specific requirements for a problem.

    Args:
        problem_title: Problem title to match
        difficulty: Difficulty level (easy/medium/hard)

    Returns:
        Requirements string for the specified difficulty level
    """
    title_lower = problem_title.lower()

    # Check for URL shortener
    if "url shortener" in title_lower:
        level_req = URL_SHORTENER_REQUIREMENTS.get(difficulty, URL_SHORTENER_REQUIREMENTS["medium"])
        return level_req.get("requirements", "")

    # Default fallback - return the general solution reference
    return get_solution_reference(problem_title)


def get_level_info(difficulty: str) -> Dict[str, str]:
    """
    Get level information for a difficulty.

    Args:
        difficulty: Difficulty level (easy/medium/hard)

    Returns:
        Dict with level, title, and description
    """
    if difficulty in DIFFICULTY_LEVELS:
        return DIFFICULTY_LEVELS[difficulty]

    # Check URL_SHORTENER_REQUIREMENTS as fallback
    if difficulty in URL_SHORTENER_REQUIREMENTS:
        req = URL_SHORTENER_REQUIREMENTS[difficulty]
        return {
            "level": req.get("level", ""),
            "title": req.get("title", ""),
            "description": req.get("focus", ""),
        }

    return {"level": "", "title": "", "description": ""}


def _check_and_ban_user(user_id: int, violation: ModerationResult, db: Session) -> bool:
    """
    Check if user should be banned and ban them if necessary.

    Args:
        user_id: User ID to check
        violation: The moderation violation
        db: Database session

    Returns:
        True if user was banned, False otherwise
    """
    if user_id not in _user_violations:
        _user_violations[user_id] = []

    _user_violations[user_id].append(violation)

    should_ban, ban_reason = moderation_service.should_ban_user(_user_violations[user_id])

    if should_ban:
        user = db.query(User).filter(User.id == user_id).first()
        if user and not user.is_banned:
            user.is_banned = True
            user.ban_reason = ban_reason
            user.banned_at = datetime.utcnow()
            db.commit()
            return True

    return False


@router.post("/", response_model=ChatResponse)
async def chat_about_design(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Chat with AI about system design.

    The AI will:
    - Guide candidates toward a correct solution based on their difficulty level
    - Evaluate their current diagram and provide feedback
    - Answer questions about system design concepts
    - Provide constructive criticism and suggestions

    Difficulty levels:
    - easy (L5): Senior SWE - Core functionality
    - medium (L6): Staff Engineer - Production-ready
    - hard (L7): Principal Engineer - Global-scale

    Includes content moderation to block:
    - Off-topic messages unrelated to system design
    - Jailbreak/prompt injection attempts
    - Code execution attempts
    - Inappropriate/obscene content
    """
    # Check if user is banned
    if current_user and current_user.is_banned:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "banned",
                "message": "Your account has been suspended due to policy violations.",
                "reason": current_user.ban_reason,
                "contact": "Please contact support@system-design-platform.com if you believe this is an error."
            }
        )

    # Moderate the user's message - fast regex check
    moderation_result, moderation_message = moderation_service.check_message(request.message)

    if moderation_result != ModerationResult.ALLOWED:
        # Return moderation message immediately - don't block on ban tracking
        response = ChatResponse(
            response=f"⚠️ **Message Blocked**\n\n{moderation_message}",
            diagram_feedback=None,
            suggested_improvements=[],
            is_on_track=True,
            demo_mode=False,
        )

        # Track violation in background if user is logged in (non-blocking)
        if current_user:
            try:
                was_banned = _check_and_ban_user(current_user.id, moderation_result, db)
                if was_banned:
                    # User just got banned - update response
                    response.response = (
                        "⚠️ **Account Suspended**\n\n"
                        "Your account has been suspended due to repeated policy violations.\n\n"
                        "Please contact support@system-design-platform.com to appeal."
                    )
            except Exception:
                # Don't fail the response if ban tracking fails
                pass

        return response

    # Get the problem details
    problem = db.query(Problem).filter(Problem.id == request.problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem_description = problem.description
    problem_title = problem.title

    # Determine difficulty level
    difficulty = request.difficulty_level or problem.difficulty or "medium"

    # Get level-specific reference solution
    solution_reference = get_level_requirements(problem_title, difficulty)

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
    db: Session = Depends(get_db),
):
    """
    Evaluate a diagram and provide structured feedback.

    This is a focused endpoint just for diagram evaluation,
    separate from the conversational chat.
    """
    # Get the problem details
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem_title = problem.title
    problem_description = problem.description

    # Get reference solution
    solution_reference = get_solution_reference(problem_title)

    # Call the AI service with just the diagram
    result = await ai_service.chat_about_design(
        problem_description=problem_description,
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


@router.post("/generate-summary", response_model=DesignSummaryResponse)
async def generate_design_summary(
    request: DesignSummaryRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a final design summary after the chat session.

    This endpoint should be called when the candidate completes their design
    session. It produces a comprehensive summary of their design including:
    - Key components identified
    - Strengths of the design
    - Areas for improvement
    - Overall score based on the difficulty level requirements

    Args:
        request: Summary request with problem_id, difficulty_level, and design data
        db: Database session

    Returns:
        DesignSummaryResponse with complete design summary
    """
    # Get the problem details
    problem = db.query(Problem).filter(Problem.id == request.problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem_title = problem.title
    problem_description = problem.description
    difficulty = request.difficulty_level

    # Get level-specific requirements
    level_requirements = get_level_requirements(problem_title, difficulty)
    level_info = get_level_info(difficulty)

    # Generate summary using AI service
    result = await ai_service.generate_design_summary(
        problem_description=problem_description,
        problem_title=problem_title,
        difficulty_level=difficulty,
        level_requirements=level_requirements,
        conversation_history=[
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ],
        current_schema=request.current_schema,
        current_api_spec=request.current_api_spec,
        current_diagram=request.current_diagram,
    )

    return DesignSummaryResponse(
        summary=result.get("summary", ""),
        key_components=result.get("key_components", []),
        strengths=result.get("strengths", []),
        areas_for_improvement=result.get("areas_for_improvement", []),
        overall_score=result.get("overall_score"),
        difficulty_level=difficulty,
        level_info=level_info,
        demo_mode=result.get("demo_mode", False),
    )


@router.get("/level-requirements/{problem_id}")
async def get_problem_level_requirements(
    problem_id: int,
    difficulty: str = "medium",
    db: Session = Depends(get_db),
):
    """
    Get the requirements for a specific difficulty level for a problem.

    Args:
        problem_id: Problem ID
        difficulty: Difficulty level (easy/medium/hard)
        db: Database session

    Returns:
        Dict with level info and requirements
    """
    # Get the problem details
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Get level-specific requirements
    requirements = get_level_requirements(problem.title, difficulty)
    level_info = get_level_info(difficulty)

    return {
        "problem_id": problem_id,
        "problem_title": problem.title,
        "difficulty": difficulty,
        "level_info": level_info,
        "requirements": requirements,
    }
