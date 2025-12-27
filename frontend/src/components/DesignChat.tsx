/**
 * Design Chat Component
 * Claude-powered chatbot for system design guidance
 */

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2, Sparkles, AlertCircle, CheckCircle, Lightbulb } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { chatApi, ChatMessage, ChatResponse, DiagramFeedback } from "@/api/client"

interface DesignChatProps {
  problemId: number
  currentSchema?: any
  currentApiSpec?: any
  currentDiagram?: any
  readOnly?: boolean
}

interface Message extends ChatMessage {
  id: string
  timestamp: Date
  diagramFeedback?: DiagramFeedback
  suggestedImprovements?: string[]
  isOnTrack?: boolean
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
}: DesignChatProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Convert messages to conversation history format
  const getConversationHistory = (): ChatMessage[] => {
    return messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))
  }

  const sendMessage = async (messageText?: string) => {
    const text = messageText || inputValue.trim()
    if (!text || isLoading) return

    setError(null)
    setInputValue("")

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date(),
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
      })

      // Add assistant message
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
        diagramFeedback: response.diagram_feedback,
        suggestedImprovements: response.suggested_improvements,
        isOnTrack: response.is_on_track,
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      setError(err.message || "Failed to send message")
      // Remove the user message on error
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id))
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const evaluateDiagram = () => {
    if (!currentDiagram) {
      setError("Please create a diagram first before requesting feedback")
      return
    }
    sendMessage("Please evaluate my current diagram and provide detailed feedback on my architecture.")
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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b bg-gradient-to-r from-violet-500/10 to-purple-500/10">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-medium">Design Coach</h3>
            <p className="text-xs text-muted-foreground">
              Powered by Claude AI
            </p>
          </div>
        </div>
        {!readOnly && (
          <Button
            variant="outline"
            size="sm"
            onClick={evaluateDiagram}
            disabled={isLoading || !currentDiagram}
            className="text-xs"
          >
            <Sparkles className="h-3 w-3 mr-1" />
            Evaluate My Diagram
          </Button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
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
        <div className="p-3 border-t bg-muted/30">
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
