/**
 * System design editor with both canvas and text modes
 * Allows drawing diagrams or describing the design in text
 */

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PenLine, FileText, Lightbulb } from "lucide-react"
import DesignCanvas from "./DesignCanvas"

interface DesignEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

interface DesignData {
  mode: "canvas" | "text"
  canvas?: string
  text?: string
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
  // Parse the value to determine mode and data
  const parseValue = (): DesignData => {
    if (!value) {
      return { mode: "canvas", canvas: "", text: "" }
    }
    try {
      const parsed = JSON.parse(value)
      if (parsed.mode) {
        return parsed
      }
      // Legacy: if it has elements, it's canvas data
      if (parsed.elements) {
        return { mode: "canvas", canvas: value, text: "" }
      }
    } catch {
      // Plain text
      return { mode: "text", canvas: "", text: value }
    }
    return { mode: "canvas", canvas: "", text: "" }
  }

  const data = parseValue()
  const [mode, setMode] = useState<"canvas" | "text">(data.mode)

  const handleCanvasChange = (canvasValue: string) => {
    const newData: DesignData = {
      mode: "canvas",
      canvas: canvasValue,
      text: data.text,
    }
    onChange(JSON.stringify(newData))
  }

  const handleTextChange = (textValue: string) => {
    const newData: DesignData = {
      mode: "text",
      canvas: data.canvas,
      text: textValue,
    }
    onChange(JSON.stringify(newData))
  }

  const handleModeChange = (newMode: string) => {
    setMode(newMode as "canvas" | "text")
    const newData: DesignData = {
      mode: newMode as "canvas" | "text",
      canvas: data.canvas,
      text: data.text,
    }
    onChange(JSON.stringify(newData))
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-muted/50 px-4 py-2 border-b">
        <h3 className="text-sm font-medium flex items-center gap-2">
          <PenLine className="h-4 w-4 text-primary" />
          System Design
        </h3>
        <p className="text-xs text-muted-foreground">
          Draw your architecture diagram or describe it in text
        </p>
      </div>

      <Tabs value={mode} onValueChange={handleModeChange} className="w-full">
        <div className="border-b bg-background px-2">
          <TabsList className="h-10 bg-transparent">
            <TabsTrigger
              value="canvas"
              className="data-[state=active]:bg-muted gap-1.5"
              disabled={readOnly}
            >
              <PenLine className="h-3.5 w-3.5" />
              Draw Diagram
            </TabsTrigger>
            <TabsTrigger
              value="text"
              className="data-[state=active]:bg-muted gap-1.5"
              disabled={readOnly}
            >
              <FileText className="h-3.5 w-3.5" />
              Text Description
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="canvas" className="m-0">
          <DesignCanvas
            value={data.canvas}
            onChange={handleCanvasChange}
            readOnly={readOnly}
          />
        </TabsContent>

        <TabsContent value="text" className="m-0">
          <textarea
            value={data.text || ""}
            onChange={(e) => handleTextChange(e.target.value)}
            placeholder={placeholder}
            readOnly={readOnly}
            className="w-full h-96 p-4 font-mono text-sm resize-none focus:outline-none bg-background"
            style={{ minHeight: "500px" }}
          />
        </TabsContent>
      </Tabs>

      {/* Tips section */}
      {!readOnly && (
        <div className="border-t bg-muted/30 p-3">
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <Lightbulb className="h-4 w-4 shrink-0 text-yellow-500" />
            <div>
              <strong>Tips:</strong>
              {mode === "canvas" ? (
                <span>
                  {" "}Use the toolbar to add shapes, icons, and arrows. Click to select, drag to move.
                  Double-click text or icons to edit labels.
                </span>
              ) : (
                <span>
                  {" "}Describe your architecture, data flow, and design decisions. Use markdown
                  formatting for better structure.
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
