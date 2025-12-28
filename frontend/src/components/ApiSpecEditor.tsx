/**
 * API specification editor component
 * Provides a Monaco-based editor for defining API endpoints
 */

import { Suspense, lazy } from 'react'
import { Loader2 } from 'lucide-react'

// Lazy load Monaco editor to prevent blocking initial render
const Editor = lazy(() => import('@monaco-editor/react').then(mod => ({ default: mod.default })))

interface ApiSpecEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

// Loading fallback for Monaco editor
function EditorLoading() {
  return (
    <div className="h-[300px] flex items-center justify-center bg-muted/50">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading editor...</span>
      </div>
    </div>
  )
}

// Default API spec template
const defaultApiSpec = `{
  "endpoints": [
    {
      "method": "POST",
      "path": "/api/v1/urls",
      "description": "Create a shortened URL",
      "request_body": {
        "original_url": "string",
        "custom_alias": "string (optional)"
      },
      "responses": {
        "201": { "short_url": "string", "expires_at": "timestamp" },
        "400": { "error": "string" }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/urls/{short_code}",
      "description": "Redirect to original URL",
      "responses": {
        "302": "Redirect to original URL",
        "404": { "error": "URL not found" }
      }
    }
  ],
  "security": {
    "type": "api_key",
    "header": "X-API-Key"
  }
}`

export default function ApiSpecEditor({
  value,
  onChange,
  readOnly = false,
}: ApiSpecEditorProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-100 dark:bg-gray-800 px-4 py-2 border-b">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">API Specification</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Define your API endpoints, request/response schemas, and authentication
        </p>
      </div>
      <Suspense fallback={<EditorLoading />}>
        <Editor
          height="300px"
          defaultLanguage="json"
          defaultValue={value || defaultApiSpec}
          value={value || defaultApiSpec}
          onChange={(v) => onChange(v || '')}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            readOnly,
            scrollBeyondLastLine: false,
            automaticLayout: true,
          }}
          theme="vs-light"
        />
      </Suspense>
    </div>
  )
}
