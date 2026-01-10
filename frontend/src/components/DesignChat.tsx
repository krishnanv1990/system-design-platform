/**
 * Design Chat Component
 * Claude-powered chatbot for system design guidance
 *
 * Supports difficulty levels:
 * - Easy (L5): Senior Software Engineer
 * - Medium (L6): Staff Engineer
 * - Hard (L7): Principal Engineer
 */

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2, Sparkles, AlertCircle, CheckCircle, Lightbulb, Flag, GraduationCap, RotateCcw, XCircle, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { chatApi, ChatMessage, ChatResponse, DiagramFeedback, DifficultyLevel, DesignSummaryResponse } from "@/api/client"
import DesignSummary from "./DesignSummary"

interface DesignChatProps {
  problemId: number
  currentSchema?: any
  currentApiSpec?: any
  currentDiagram?: any
  readOnly?: boolean
  difficultyLevel?: DifficultyLevel
  onSummaryGenerated?: (summary: DesignSummaryResponse) => void
}

// Engineering level labels
const levelLabels: Record<DifficultyLevel, { level: string; title: string }> = {
  easy: { level: "L5", title: "Senior SWE" },
  medium: { level: "L6", title: "Staff Engineer" },
  hard: { level: "L7", title: "Principal Engineer" },
}

interface Message extends ChatMessage {
  id: string
  timestamp: Date
  diagramFeedback?: DiagramFeedback
  suggestedImprovements?: string[]
  isOnTrack?: boolean
  status?: 'sending' | 'sent' | 'failed'
  error?: string
}

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content: `**Welcome to the System Design Coach!**

I'm here to help you design a robust, scalable system. Here's how I can help:

- **Ask questions** about architecture, databases, caching, or any system design concept
- **Share your diagram** by clicking "Evaluate My Diagram" for specific feedback
- **Get guidance** on best practices and trade-offs

What would you like to discuss about your design?`,
  timestamp: new Date(),
}

export default function DesignChat({
  problemId,
  currentSchema,
  currentApiSpec,
  currentDiagram,
  readOnly = false,
  difficultyLevel = "medium",
  onSummaryGenerated,
}: DesignChatProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [designSummary, setDesignSummary] = useState<DesignSummaryResponse | null>(null)
  const [showSummary, setShowSummary] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Chat history storage key
  const chatStorageKey = `chat_history_${problemId}`

  // Rate limit warning state
  const [rateLimitWarning, setRateLimitWarning] = useState<{
    remaining: number
    limit: number
    resetTime: string | null
  } | null>(null)

  // Listen for rate limit events
  useEffect(() => {
    const handleRateLimitWarning = (e: CustomEvent<{ remaining: number; limit: number; reset: number | null }>) => {
      const { remaining, limit, reset } = e.detail
      setRateLimitWarning({
        remaining,
        limit,
        resetTime: reset ? new Date(reset * 1000).toLocaleTimeString() : null,
      })
      // Clear warning after 10 seconds
      setTimeout(() => setRateLimitWarning(null), 10000)
    }

    const handleRateLimitExceeded = () => {
      setError("Rate limit exceeded. Please wait a moment before sending more messages.")
    }

    window.addEventListener('rate-limit-warning', handleRateLimitWarning as EventListener)
    window.addEventListener('rate-limit-exceeded', handleRateLimitExceeded)

    return () => {
      window.removeEventListener('rate-limit-warning', handleRateLimitWarning as EventListener)
      window.removeEventListener('rate-limit-exceeded', handleRateLimitExceeded)
    }
  }, [])

  // Load chat history from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(chatStorageKey)
      if (saved) {
        const parsed = JSON.parse(saved)
        // Restore messages with proper Date objects
        const restoredMessages = parsed.map((m: Message) => ({
          ...m,
          timestamp: new Date(m.timestamp),
        }))
        if (restoredMessages.length > 0) {
          setMessages([WELCOME_MESSAGE, ...restoredMessages])
        }
      }
    } catch {
      // Invalid stored data, ignore
    }
  }, [chatStorageKey])

  // Save chat history to localStorage when messages change
  useEffect(() => {
    // Filter out welcome message and only save user/assistant messages
    const messagesToSave = messages.filter((m) => m.id !== "welcome")
    if (messagesToSave.length > 0) {
      try {
        localStorage.setItem(chatStorageKey, JSON.stringify(messagesToSave))
      } catch (e) {
        const error = e as DOMException
        if (error.name === 'QuotaExceededError') {
          console.warn("localStorage quota exceeded - chat history not saved")
        }
      }
    }
  }, [messages, chatStorageKey])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Convert messages to conversation history format
  // Limit to last 20 messages to avoid exceeding token limits
  const MAX_CONVERSATION_HISTORY = 20

  const getConversationHistory = (): ChatMessage[] => {
    const history = messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))

    // If history exceeds limit, take the last N messages
    if (history.length > MAX_CONVERSATION_HISTORY) {
      return history.slice(-MAX_CONVERSATION_HISTORY)
    }
    return history
  }

  const sendMessage = async (messageText?: string) => {
    const text = messageText || inputValue.trim()
    if (!text || isLoading) return

    setError(null)
    setInputValue("")

    // Add user message
    const messageId = `user-${Date.now()}`
    const userMessage: Message = {
      id: messageId,
      role: "user",
      content: text,
      timestamp: new Date(),
      status: 'sending',
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response: ChatResponse = await chatApi.sendMessage({
        problem_id: problemId,
        message: text,
        conversation_history: getConversationHistory(),
        current_schema: currentSchema,
        current_api_spec: currentApiSpec,
        current_diagram: currentDiagram,
        difficulty_level: difficultyLevel,
      })

      // Mark user message as sent
      setMessages((prev) => prev.map((m) =>
        m.id === messageId ? { ...m, status: 'sent' as const } : m
      ))

      // Add assistant message
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
        diagramFeedback: response.diagram_feedback,
        suggestedImprovements: response.suggested_improvements,
        isOnTrack: response.is_on_track,
        status: 'sent',
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      const errorMessage = err.message || "Failed to send message"
      setError(errorMessage)
      // Mark message as failed instead of removing it
      setMessages((prev) => prev.map((m) =>
        m.id === messageId ? { ...m, status: 'failed' as const, error: errorMessage } : m
      ))
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  // Retry a failed message
  const retryMessage = (messageId: string) => {
    const failedMessage = messages.find((m) => m.id === messageId)
    if (!failedMessage) return

    // Remove the failed message
    setMessages((prev) => prev.filter((m) => m.id !== messageId))
    setError(null)

    // Resend the message
    sendMessage(failedMessage.content)
  }

  const evaluateDiagram = () => {
    if (!currentDiagram) {
      setError("Please create a diagram first before requesting feedback")
      return
    }
    sendMessage("Please evaluate my current diagram and provide detailed feedback on my architecture.")
  }

  // Clear chat history
  const clearHistory = () => {
    if (window.confirm("Clear all chat history? This cannot be undone.")) {
      setMessages([WELCOME_MESSAGE])
      localStorage.removeItem(chatStorageKey)
      setDesignSummary(null)
      setShowSummary(false)
      setError(null)
    }
  }

  /**
   * Generate a design summary to conclude the session
   */
  const generateDesignSummary = async () => {
    setIsGeneratingSummary(true)
    setError(null)

    try {
      const summary = await chatApi.generateSummary({
        problem_id: problemId,
        difficulty_level: difficultyLevel,
        conversation_history: getConversationHistory(),
        current_schema: currentSchema,
        current_api_spec: currentApiSpec,
        current_diagram: currentDiagram,
      })

      setDesignSummary(summary)
      setShowSummary(true)

      // Notify parent component
      if (onSummaryGenerated) {
        onSummaryGenerated(summary)
      }
    } catch (err: any) {
      setError(err.message || "Failed to generate design summary")
    } finally {
      setIsGeneratingSummary(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const renderMessage = (message: Message) => {
    const isUser = message.role === "user"

    return (
      <div
        key={message.id}
        className={cn(
          "flex gap-3 p-4",
          isUser ? "bg-muted/30" : "bg-background"
        )}
      >
        {/* Avatar */}
        <div
          className={cn(
            "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-gradient-to-br from-violet-500 to-purple-600 text-white"
          )}
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </div>

        {/* Message content */}
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              {isUser ? "You" : "Design Coach"}
            </span>
            <span className="text-xs text-muted-foreground">
              {message.timestamp.toLocaleTimeString()}
            </span>
            {/* Failed message indicator with retry button */}
            {isUser && message.status === 'failed' && (
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-xs">
                  <XCircle className="h-3 w-3 mr-1" />
                  Failed
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => retryMessage(message.id)}
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  Retry
                </Button>
              </div>
            )}
            {/* Sending indicator */}
            {isUser && message.status === 'sending' && (
              <Badge variant="secondary" className="text-xs">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Sending
              </Badge>
            )}
            {!isUser && message.isOnTrack !== undefined && (
              <Badge
                variant={message.isOnTrack ? "success" : "destructive"}
                className="text-xs"
              >
                {message.isOnTrack ? (
                  <>
                    <CheckCircle className="h-3 w-3 mr-1" />
                    On Track
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-3 w-3 mr-1" />
                    Needs Work
                  </>
                )}
              </Badge>
            )}
          </div>

          {/* Message text with markdown-like formatting */}
          <div className="text-sm prose prose-sm dark:prose-invert max-w-none">
            {message.content.split("\n").map((line, i) => {
              // Handle headers
              if (line.startsWith("**") && line.endsWith("**")) {
                return (
                  <p key={i} className="font-semibold mt-2 mb-1">
                    {line.replace(/\*\*/g, "")}
                  </p>
                )
              }
              // Handle bullet points
              if (line.startsWith("- ")) {
                return (
                  <li key={i} className="ml-4 text-muted-foreground">
                    {line.substring(2)}
                  </li>
                )
              }
              // Handle numbered lists
              if (/^\d+\.\s/.test(line)) {
                return (
                  <li key={i} className="ml-4 text-muted-foreground list-decimal">
                    {line.replace(/^\d+\.\s/, "")}
                  </li>
                )
              }
              // Handle inline bold
              if (line.includes("**")) {
                const parts = line.split(/(\*\*[^*]+\*\*)/)
                return (
                  <p key={i} className="mb-1">
                    {parts.map((part, j) =>
                      part.startsWith("**") && part.endsWith("**") ? (
                        <strong key={j}>{part.replace(/\*\*/g, "")}</strong>
                      ) : (
                        <span key={j}>{part}</span>
                      )
                    )}
                  </p>
                )
              }
              // Regular text
              if (line.trim()) {
                return (
                  <p key={i} className="mb-1">
                    {line}
                  </p>
                )
              }
              return <br key={i} />
            })}
          </div>

          {/* Diagram feedback card */}
          {message.diagramFeedback && (
            <Card className="mt-3 border-2 border-purple-500/20 bg-purple-500/5">
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium text-purple-600 dark:text-purple-400">
                  <Sparkles className="h-4 w-4" />
                  Diagram Analysis
                  {message.diagramFeedback.score !== undefined && (
                    <Badge variant="secondary" className="ml-auto">
                      Score: {message.diagramFeedback.score}/100
                    </Badge>
                  )}
                </div>

                {message.diagramFeedback.strengths.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">
                      Strengths
                    </p>
                    <ul className="text-xs text-muted-foreground space-y-1">
                      {message.diagramFeedback.strengths.map((s, i) => (
                        <li key={i} className="flex items-start gap-1">
                          <CheckCircle className="h-3 w-3 text-green-500 mt-0.5 flex-shrink-0" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {message.diagramFeedback.weaknesses.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">
                      Areas for Improvement
                    </p>
                    <ul className="text-xs text-muted-foreground space-y-1">
                      {message.diagramFeedback.weaknesses.map((w, i) => (
                        <li key={i} className="flex items-start gap-1">
                          <AlertCircle className="h-3 w-3 text-red-500 mt-0.5 flex-shrink-0" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Suggested improvements */}
          {message.suggestedImprovements && message.suggestedImprovements.length > 0 && (
            <div className="mt-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <p className="text-xs font-medium text-amber-600 dark:text-amber-400 mb-2 flex items-center gap-1">
                <Lightbulb className="h-3 w-3" />
                Suggested Improvements
              </p>
              <ul className="text-xs text-muted-foreground space-y-1">
                {message.suggestedImprovements.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    )
  }

  // If showing the summary view, render that instead
  if (showSummary && designSummary) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        {/* Summary Header */}
        <div className="flex items-center justify-between p-3 border-b bg-gradient-to-r from-green-500/10 to-emerald-500/10 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-gradient-to-br from-green-500 to-emerald-600">
              <Flag className="h-4 w-4 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-medium">Design Complete</h3>
              <p className="text-xs text-muted-foreground">
                {levelLabels[difficultyLevel].level} - {levelLabels[difficultyLevel].title}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSummary(false)}
            className="text-xs"
          >
            Back to Chat
          </Button>
        </div>

        {/* Summary Content */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          <DesignSummary
            summary={designSummary}
            diagramData={currentDiagram ? JSON.stringify(currentDiagram) : undefined}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b bg-gradient-to-r from-violet-500/10 to-purple-500/10 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-medium">Design Coach</h3>
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <GraduationCap className="h-3 w-3" />
              {levelLabels[difficultyLevel].level} - {levelLabels[difficultyLevel].title}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!readOnly && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={evaluateDiagram}
                disabled={isLoading || !currentDiagram}
                className="text-xs"
              >
                <Sparkles className="h-3 w-3 mr-1" />
                Evaluate Diagram
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={generateDesignSummary}
                disabled={isLoading || isGeneratingSummary || messages.length < 3}
                className="text-xs bg-green-600 hover:bg-green-700"
              >
                {isGeneratingSummary ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <Flag className="h-3 w-3 mr-1" />
                )}
                {isGeneratingSummary ? "Generating..." : "Complete Design"}
              </Button>
              {/* Clear history button - only show if there's history */}
              {messages.length > 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearHistory}
                  disabled={isLoading}
                  className="text-xs text-muted-foreground hover:text-destructive"
                  title="Clear chat history"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {messages.map(renderMessage)}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex gap-3 p-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-gradient-to-br from-violet-500 to-purple-600 text-white">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Thinking...</span>
            </div>
          </div>
        )}

        {/* Rate limit warning */}
        {rateLimitWarning && (
          <div className="p-4">
            <div className="p-3 rounded-lg bg-warning/10 border border-warning/20 text-warning text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              <span>
                Rate limit: {rateLimitWarning.remaining}/{rateLimitWarning.limit} requests remaining
                {rateLimitWarning.resetTime && ` (resets at ${rateLimitWarning.resetTime})`}
              </span>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-4">
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {!readOnly && (
        <div className="p-3 border-t bg-muted/30 flex-shrink-0">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your design, request feedback, or discuss trade-offs..."
              className="flex-1 min-h-[44px] max-h-32 p-3 rounded-lg border bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 text-sm"
              disabled={isLoading}
              rows={1}
            />
            <Button
              onClick={() => sendMessage()}
              disabled={isLoading || !inputValue.trim()}
              size="icon"
              className="h-11 w-11"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      )}
    </div>
  )
}
