/**
 * System design description editor
 * Free-form text editor for describing the overall system design
 */

interface DesignEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

const placeholder = `Describe your system design here. Consider including:

1. **High-Level Architecture**
   - What are the main components?
   - How do they interact?

2. **Data Flow**
   - How does data move through the system?
   - What happens on read vs write?

3. **Scalability**
   - How does the system handle increased load?
   - What components can be scaled horizontally?

4. **Reliability**
   - How does the system handle failures?
   - What redundancy is built in?

5. **Data Storage**
   - Why did you choose this database?
   - How is data partitioned/sharded?

6. **Caching Strategy**
   - What caching layers exist?
   - What is the cache invalidation strategy?

7. **Trade-offs**
   - What trade-offs did you make?
   - What would you change with more time?`

export default function DesignEditor({
  value,
  onChange,
  readOnly = false,
}: DesignEditorProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-100 px-4 py-2 border-b">
        <h3 className="text-sm font-medium text-gray-700">System Design Description</h3>
        <p className="text-xs text-gray-500">
          Describe your overall system architecture, components, and design decisions
        </p>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        className="w-full h-96 p-4 font-mono text-sm resize-none focus:outline-none"
        style={{ minHeight: '400px' }}
      />
    </div>
  )
}
