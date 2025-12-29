"""
Content moderation service for chat messages.
Filters inappropriate content, off-topic messages, and potential abuse attempts.
"""

import re
from typing import Tuple, List
from enum import Enum


class ModerationResult(Enum):
    """Result of content moderation check."""
    ALLOWED = "allowed"
    BLOCKED_OFF_TOPIC = "blocked_off_topic"
    BLOCKED_JAILBREAK = "blocked_jailbreak"
    BLOCKED_CODE_EXECUTION = "blocked_code_execution"
    BLOCKED_OBSCENE = "blocked_obscene"
    BLOCKED_ABUSE = "blocked_abuse"


# Keywords related to system design and software engineering
ALLOWED_TOPICS = [
    # Architecture & Design
    "architecture", "design", "system", "scale", "scalability", "distributed",
    "microservices", "monolith", "service", "api", "rest", "graphql", "grpc",
    "latency", "throughput", "availability", "reliability", "consistency",
    "partition", "replication", "sharding", "load balancer", "cdn", "dns",
    "gateway", "proxy", "reverse proxy", "nginx", "haproxy",

    # Databases
    "database", "sql", "nosql", "postgres", "mysql", "mongodb", "redis",
    "cassandra", "dynamodb", "elasticsearch", "index", "query", "schema",
    "table", "primary key", "foreign key", "join", "transaction", "acid",
    "eventual consistency", "cap theorem", "data model", "orm",

    # Caching
    "cache", "caching", "redis", "memcached", "ttl", "eviction", "lru",
    "write-through", "write-back", "cache-aside", "invalidation",

    # Messaging & Queues
    "queue", "message", "kafka", "rabbitmq", "sqs", "pub/sub", "event",
    "async", "asynchronous", "stream", "consumer", "producer", "broker",

    # Cloud & Infrastructure
    "cloud", "aws", "gcp", "azure", "kubernetes", "docker", "container",
    "serverless", "lambda", "function", "ec2", "s3", "storage", "blob",
    "compute", "instance", "cluster", "node", "pod", "deployment",

    # Networking
    "network", "http", "https", "tcp", "udp", "websocket", "protocol",
    "endpoint", "url", "request", "response", "header", "body",

    # Performance & Monitoring
    "performance", "optimize", "bottleneck", "profiling", "metrics",
    "monitoring", "logging", "tracing", "observability", "alert",

    # Security
    "security", "authentication", "authorization", "oauth", "jwt", "token",
    "encryption", "ssl", "tls", "certificate", "firewall", "rate limit",

    # General Software Engineering
    "algorithm", "data structure", "complexity", "big o", "hash",
    "tree", "graph", "array", "linked list", "stack", "heap",
    "design pattern", "solid", "dry", "kiss", "yagni",

    # Problem-specific
    "url shortener", "short code", "redirect", "kgs", "key generation",
    "base62", "encode", "decode", "analytics", "click", "count",

    # General conversation
    "help", "explain", "what", "how", "why", "when", "where", "can",
    "should", "would", "could", "will", "need", "want", "think",
    "understand", "clarify", "example", "question", "answer",
    "feedback", "review", "evaluate", "improve", "suggest", "recommend",
    "diagram", "component", "element", "connection", "flow", "user",
    "client", "server", "backend", "frontend", "mobile", "web",
]

# Patterns that indicate jailbreak or prompt injection attempts
JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"ignore\s+all\s+previous\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+all\s+prior\s+rules",
    r"forget\s+(everything|all|previous|prior)",
    r"you\s+are\s+(now|actually|really)\s+a",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a)",
    r"roleplay\s+as",
    r"simulate\s+being",
    r"bypass\s+.*?(safety|restrictions?|filters?|rules?)",
    r"override\s+.*?(safety|restrictions?|filters?|rules?)",
    r"unlock\s+.*?(developer|admin|special)\s+mode",
    r"enable\s+(developer|admin|special)\s+mode",
    r"dan\s+mode",
    r"jailbreak",
    r"prompt\s+injection",
    r"system\s*:\s*you\s+are",
    r"\[system\]",
    r"\[assistant\]",
    r"\[user\]",
    r"<\|.*\|>",  # Special tokens
    r"```system",
    r"###\s*instruction",
]

# Patterns that indicate code execution attempts
CODE_EXECUTION_PATTERNS = [
    r"eval\s*\(",
    r"exec\s*\(",
    r"import\s+os",
    r"import\s+subprocess",
    r"import\s+sys",
    r"__import__",
    r"os\.system",
    r"subprocess\.",
    r"shell\s*=\s*true",
    r"rm\s+-rf",
    r"sudo\s+",
    r"chmod\s+",
    r"curl\s+.*\|\s*(bash|sh)",
    r"wget\s+.*\|\s*(bash|sh)",
    r"<script",
    r"javascript:",
    r"onclick\s*=",
    r"onerror\s*=",
]

# Obscene/inappropriate content patterns (basic list - would be more comprehensive in production)
OBSCENE_PATTERNS = [
    r"\b(fuck|fucking|fucked|fucker)\b",
    r"\b(shit|shitty|shitting)\b",
    r"\b(asshole|assholes)\b",
    r"\b(bitch|bitches)\b",
    r"\b(dick|cock|pussy|porn|xxx)\b",
    # Add more patterns as needed - keeping this basic for the example
]


class ModerationService:
    """
    Service for moderating chat content.
    Checks for off-topic content, jailbreak attempts, and inappropriate content.
    """

    def __init__(self):
        """Initialize the moderation service."""
        self.allowed_topics_lower = [t.lower() for t in ALLOWED_TOPICS]
        self.jailbreak_patterns = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]
        self.code_execution_patterns = [re.compile(p, re.IGNORECASE) for p in CODE_EXECUTION_PATTERNS]
        self.obscene_patterns = [re.compile(p, re.IGNORECASE) for p in OBSCENE_PATTERNS]

    def check_message(self, message: str) -> Tuple[ModerationResult, str]:
        """
        Check a message for inappropriate content.

        Args:
            message: The user's message to check

        Returns:
            Tuple of (ModerationResult, explanation message)
        """
        if not message or not message.strip():
            return ModerationResult.ALLOWED, ""

        message_lower = message.lower()

        # Check for jailbreak attempts first (highest priority)
        for pattern in self.jailbreak_patterns:
            if pattern.search(message):
                return (
                    ModerationResult.BLOCKED_JAILBREAK,
                    "Your message appears to contain a prompt manipulation attempt. "
                    "Please focus on system design discussions."
                )

        # Check for code execution attempts
        for pattern in self.code_execution_patterns:
            if pattern.search(message):
                return (
                    ModerationResult.BLOCKED_CODE_EXECUTION,
                    "Your message appears to contain code execution commands. "
                    "Please focus on discussing system design concepts instead."
                )

        # Check for obscene content
        for pattern in self.obscene_patterns:
            if pattern.search(message):
                return (
                    ModerationResult.BLOCKED_OBSCENE,
                    "Your message contains inappropriate content. "
                    "Please keep the conversation professional and focused on system design."
                )

        # Check if message is related to system design topics
        if not self._is_relevant_topic(message_lower):
            return (
                ModerationResult.BLOCKED_OFF_TOPIC,
                "Your message doesn't appear to be related to system design or software engineering. "
                "This chat is designed to help you with system design concepts, architecture patterns, "
                "databases, caching, scalability, and related topics. "
                "Please ask questions related to your system design work."
            )

        return ModerationResult.ALLOWED, ""

    def _is_relevant_topic(self, message_lower: str) -> bool:
        """
        Check if a message is related to system design/software engineering.

        Args:
            message_lower: Lowercased message text

        Returns:
            True if the message is relevant to system design
        """
        # Short messages (greetings, acknowledgments) are usually fine
        if len(message_lower.split()) <= 5:
            return True

        # Check if any allowed topic keywords are present
        for topic in self.allowed_topics_lower:
            if topic in message_lower:
                return True

        # Check for question patterns that are typically relevant
        question_patterns = [
            r"\bhow\s+(do|does|can|should|would)\b",
            r"\bwhat\s+(is|are|if|about)\b",
            r"\bwhy\s+(do|does|is|are|should|would)\b",
            r"\bcan\s+(you|i|we)\b",
            r"\bshould\s+(i|we)\b",
            r"\bis\s+(this|it|there)\b",
            r"\bplease\s+(help|explain|review|evaluate)\b",
        ]
        for pattern in question_patterns:
            if re.search(pattern, message_lower):
                return True

        # Default to allowing if uncertain (avoid false positives)
        # This is a conservative approach - we don't want to block legitimate questions
        word_count = len(message_lower.split())
        if word_count < 20:
            return True

        return False

    def should_ban_user(self, violations: List[ModerationResult]) -> Tuple[bool, str]:
        """
        Determine if a user should be banned based on their violations.

        Args:
            violations: List of moderation violations

        Returns:
            Tuple of (should_ban, ban_reason)
        """
        # Count serious violations
        jailbreak_count = sum(1 for v in violations if v == ModerationResult.BLOCKED_JAILBREAK)
        code_exec_count = sum(1 for v in violations if v == ModerationResult.BLOCKED_CODE_EXECUTION)
        obscene_count = sum(1 for v in violations if v == ModerationResult.BLOCKED_OBSCENE)

        # Immediate ban for multiple jailbreak attempts
        if jailbreak_count >= 2:
            return True, "Multiple prompt manipulation/jailbreak attempts detected"

        # Immediate ban for code execution attempts
        if code_exec_count >= 1:
            return True, "Code execution attempt detected"

        # Ban for multiple obscene content violations
        if obscene_count >= 3:
            return True, "Repeated use of inappropriate/obscene content"

        # Ban for combined violations
        serious_violations = jailbreak_count + code_exec_count + obscene_count
        if serious_violations >= 3:
            return True, "Multiple policy violations detected"

        return False, ""


# Singleton instance
_moderation_service = None


def get_moderation_service() -> ModerationService:
    """Get the singleton moderation service instance."""
    global _moderation_service
    if _moderation_service is None:
        _moderation_service = ModerationService()
    return _moderation_service
