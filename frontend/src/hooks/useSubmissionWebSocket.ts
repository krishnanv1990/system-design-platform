import { useEffect, useRef, useState, useCallback } from "react"

type MessageType = "connected" | "status_update" | "test_result" | "error_analysis"

interface WebSocketMessage {
  type: MessageType
  submission_id: number
  timestamp: string
  [key: string]: any
}

interface UseSubmissionWebSocketOptions {
  onStatusUpdate?: (status: string, progress?: number, detail?: string) => void
  onTestResult?: (result: {
    test_id: number
    test_name: string
    test_type: string
    status: string
    duration_ms?: number
    error_category?: string
  }) => void
  onErrorAnalysis?: (testId: number, analysis: any) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  enabled?: boolean
}

interface UseSubmissionWebSocketReturn {
  isConnected: boolean
  lastMessage: WebSocketMessage | null
  error: Event | null
  reconnect: () => void
}

export function useSubmissionWebSocket(
  submissionId: number | null,
  options: UseSubmissionWebSocketOptions = {}
): UseSubmissionWebSocketReturn {
  const {
    onStatusUpdate,
    onTestResult,
    onErrorAnalysis,
    onConnect,
    onDisconnect,
    onError,
    enabled = true,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [error, setError] = useState<Event | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const getWebSocketUrl = useCallback((subId: number) => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const host = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : window.location.host
    return `${protocol}//${host}/ws/submissions/${subId}`
  }, [])

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!submissionId || !enabled) return

    cleanup()

    const ws = new WebSocket(getWebSocketUrl(submissionId))
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
      onConnect?.()

      // Set up ping interval to keep connection alive
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping")
        }
      }, 30000) // Ping every 30 seconds
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        setLastMessage(message)

        switch (message.type) {
          case "status_update":
            onStatusUpdate?.(message.status, message.progress, message.detail)
            break
          case "test_result":
            onTestResult?.({
              test_id: message.test_id,
              test_name: message.test_name,
              test_type: message.test_type,
              status: message.status,
              duration_ms: message.duration_ms,
              error_category: message.error_category,
            })
            break
          case "error_analysis":
            onErrorAnalysis?.(message.test_id, message.analysis)
            break
        }
      } catch (e) {
        // Handle pong or other non-JSON messages
        if (event.data !== "pong") {
          console.warn("Failed to parse WebSocket message:", event.data)
        }
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      onDisconnect?.()

      // Clear ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }

      // Attempt to reconnect after 3 seconds if still enabled
      if (enabled && submissionId) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 3000)
      }
    }

    ws.onerror = (event) => {
      setError(event)
      onError?.(event)
    }
  }, [
    submissionId,
    enabled,
    getWebSocketUrl,
    cleanup,
    onConnect,
    onDisconnect,
    onError,
    onStatusUpdate,
    onTestResult,
    onErrorAnalysis,
  ])

  // Connect when submissionId changes or enabled state changes
  useEffect(() => {
    if (submissionId && enabled) {
      connect()
    } else {
      cleanup()
      setIsConnected(false)
    }

    return cleanup
  }, [submissionId, enabled, connect, cleanup])

  const reconnect = useCallback(() => {
    cleanup()
    connect()
  }, [cleanup, connect])

  return {
    isConnected,
    lastMessage,
    error,
    reconnect,
  }
}
