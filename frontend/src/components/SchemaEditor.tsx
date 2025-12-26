/**
 * Database schema editor component
 * Provides a Monaco-based editor for defining database schemas
 */

import Editor from '@monaco-editor/react'

interface SchemaEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

// Default schema template
const defaultSchema = `{
  "tables": {
    "users": {
      "columns": {
        "id": { "type": "uuid", "primary_key": true },
        "email": { "type": "varchar(255)", "unique": true },
        "name": { "type": "varchar(255)" },
        "created_at": { "type": "timestamp", "default": "now()" }
      },
      "indexes": ["email"]
    }
  }
}`

export default function SchemaEditor({
  value,
  onChange,
  readOnly = false,
}: SchemaEditorProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-100 px-4 py-2 border-b">
        <h3 className="text-sm font-medium text-gray-700">Database Schema</h3>
        <p className="text-xs text-gray-500">
          Define your database tables, columns, and indexes in JSON format
        </p>
      </div>
      <Editor
        height="300px"
        defaultLanguage="json"
        defaultValue={value || defaultSchema}
        value={value || defaultSchema}
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
