# WebSocket Real-Time Updates

This document describes the WebSocket system for real-time submission updates.

## Overview

The WebSocket API provides real-time updates during submission processing,
eliminating the need for polling.

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Client  │────►│  WebSocket   │────►│   Backend    │
│          │◄────│   Server     │◄────│   Services   │
└──────────┘     └──────────────┘     └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │    Redis     │
                │   Pub/Sub    │
                └──────────────┘
```

## Connection Flow

1. Client submits code via REST API
2. Client receives `submission_id`
3. Client connects to WebSocket: `/ws/submissions/{submission_id}`
4. Server authenticates connection
5. Server pushes updates as they occur
6. Server sends completion message
7. Connection closes

## Endpoint

```
WS /ws/submissions/{submission_id}?token={jwt_token}
```

## Message Protocol

### Server Messages

#### Status Update
```json
{
  "type": "status_update",
  "submission_id": 123,
  "status": "testing",
  "timestamp": "2024-01-15T10:38:00Z"
}
```

#### Test Result
```json
{
  "type": "test_result",
  "submission_id": 123,
  "test_name": "Leader Election",
  "status": "passed",
  "duration_ms": 1250,
  "timestamp": "2024-01-15T10:40:00Z"
}
```

#### Error Analysis
```json
{
  "type": "error_analysis",
  "submission_id": 123,
  "error": "Connection refused",
  "analysis": "The node failed to connect to peer",
  "suggestions": ["Check network configuration", "Verify port bindings"],
  "timestamp": "2024-01-15T10:41:00Z"
}
```

#### Complete
```json
{
  "type": "complete",
  "submission_id": 123,
  "final_status": "passed",
  "summary": {
    "total_tests": 10,
    "passed": 8,
    "failed": 2,
    "duration_ms": 45000
  },
  "timestamp": "2024-01-15T10:45:00Z"
}
```

### Client Messages

#### Ping (Keepalive)
```json
{
  "type": "ping"
}
```

Server responds with `pong` text message.

## Authentication

Include auth token in connection:

```javascript
// Query parameter
const ws = new WebSocket(
  `wss://api.example.com/ws/submissions/${id}?token=${token}`
);
```

In demo mode, authentication is optional.

## Client Implementation

### JavaScript Example

```javascript
class SubmissionWatcher {
  constructor(submissionId, token) {
    this.ws = new WebSocket(
      `wss://api.example.com/ws/submissions/${submissionId}?token=${token}`
    );

    this.ws.onopen = () => {
      console.log('Connected to submission updates');
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = (event) => {
      console.log(`Connection closed: ${event.code} ${event.reason}`);
    };

    // Send heartbeat every 30s
    this.heartbeat = setInterval(() => {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 30000);
  }

  handleMessage(message) {
    switch (message.type) {
      case 'status_update':
        console.log(`Status: ${message.status}`);
        this.onStatusUpdate?.(message);
        break;
      case 'test_result':
        console.log(`Test ${message.test_name}: ${message.status}`);
        this.onTestResult?.(message);
        break;
      case 'error_analysis':
        console.log('Error analysis:', message.analysis);
        this.onErrorAnalysis?.(message);
        break;
      case 'complete':
        console.log('Submission complete!', message.summary);
        this.onComplete?.(message);
        this.close();
        break;
    }
  }

  close() {
    clearInterval(this.heartbeat);
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.close(1000, 'Client closing');
    }
  }
}

// Usage
const watcher = new SubmissionWatcher(123, authToken);
watcher.onStatusUpdate = (msg) => updateUI(msg.status);
watcher.onTestResult = (msg) => addTestResult(msg);
watcher.onComplete = (msg) => showResults(msg.summary);
```

### React Hook Example

```typescript
import { useEffect, useState, useCallback } from 'react';

interface SubmissionUpdate {
  type: string;
  status?: string;
  test_name?: string;
  summary?: object;
}

function useSubmissionUpdates(submissionId: number, token: string) {
  const [updates, setUpdates] = useState<SubmissionUpdate[]>([]);
  const [status, setStatus] = useState<string>('connecting');

  useEffect(() => {
    const ws = new WebSocket(
      `${import.meta.env.VITE_WS_URL}/ws/submissions/${submissionId}?token=${token}`
    );

    ws.onopen = () => setStatus('connected');
    ws.onclose = () => setStatus('disconnected');
    ws.onerror = () => setStatus('error');

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setUpdates(prev => [...prev, message]);

      if (message.type === 'complete') {
        ws.close();
      }
    };

    return () => ws.close();
  }, [submissionId, token]);

  return { updates, status };
}
```

## Error Handling

| Close Code | Reason | Action |
|------------|--------|--------|
| 1000 | Normal closure | None |
| 4003 | Unauthorized | Re-authenticate |
| 4004 | Submission not found | Check ID |
| 4029 | Rate limited | Wait and retry |
| 1011 | Server error | Reconnect with backoff |

## Reconnection Strategy

```javascript
function connectWithRetry(url, maxAttempts = 5) {
  let attempts = 0;

  function connect() {
    const ws = new WebSocket(url);

    ws.onclose = (event) => {
      if (event.code !== 1000 && attempts < maxAttempts) {
        attempts++;
        const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
        console.log(`Reconnecting in ${delay}ms...`);
        setTimeout(connect, delay);
      }
    };

    return ws;
  }

  return connect();
}
```

## Server Configuration

- Connection timeout: 5 minutes
- Heartbeat interval: 30 seconds
- Max connections per submission: 10
- Max message size: 64KB

## Debugging

Enable WebSocket debugging in browser console:
```javascript
localStorage.debug = 'socket:*';
```

Check connection state:
```javascript
console.log('ReadyState:', ws.readyState);
// 0 = CONNECTING, 1 = OPEN, 2 = CLOSING, 3 = CLOSED
```
