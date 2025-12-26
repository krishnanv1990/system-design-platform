/**
 * API specification editor component
 * Provides a Monaco-based editor for defining API endpoints
 */

import Editor from '@monaco-editor/react'

interface ApiSpecEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
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
      <div className="bg-gray-100 px-4 py-2 border-b">
        <h3 className="text-sm font-medium text-gray-700">API Specification</h3>
        <p className="text-xs text-gray-500">
          Define your API endpoints, request/response schemas, and authentication
        </p>
      </div>
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
    </div>
  )
}
