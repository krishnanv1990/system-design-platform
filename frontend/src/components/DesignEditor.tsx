/**
 * System design editor with canvas, chat, and optional text modes
 * Allows drawing diagrams and chatting with AI coach
 */

import { useState, useMemo } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PenLine, Lightbulb, Bot, Minimize2, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import DesignCanvas from "./DesignCanvas"
import DesignChat from "./DesignChat"
import DesignSummary from "./DesignSummary"
import DesignTextSummary from "./DesignTextSummary"

import { DifficultyLevel, DesignSummaryResponse } from "@/api/client"

interface DesignEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
  problemId?: number
  currentSchema?: string
  currentApiSpec?: string
  difficultyLevel?: DifficultyLevel
  onSummaryChange?: (summary: DesignSummaryResponse | null) => void
  initialSummary?: DesignSummaryResponse | null
}

interface DesignData {
  mode: "canvas" | "text"
  canvas?: string
  text?: string
}

export default function DesignEditor({
  value,
  onChange,
  readOnly = false,
  problemId,
  currentSchema,
  currentApiSpec,
  difficultyLevel = "medium",
  onSummaryChange,
  initialSummary = null,
}: DesignEditorProps) {
  const [chatExpanded, setChatExpanded] = useState(true)
  const [designSummary, setDesignSummary] = useState<DesignSummaryResponse | null>(initialSummary)
  const [showSummaryBox, setShowSummaryBox] = useState(!!initialSummary)

  // Handle summary generated from chat
  const handleSummaryGenerated = (summary: DesignSummaryResponse) => {
    setDesignSummary(summary)
    setShowSummaryBox(true)
    if (onSummaryChange) {
      onSummaryChange(summary)
    }
  }

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

  // Parse and sanitize current diagram data for chat context
  // Remove large data URLs from image elements to avoid payload size issues
  const currentDiagram = useMemo(() => {
    if (!data.canvas) return null
    try {
      const parsed = JSON.parse(data.canvas)
      // Sanitize elements to remove large data URLs
      if (parsed.elements && Array.isArray(parsed.elements)) {
        parsed.elements = parsed.elements.map((el: Record<string, unknown>) => {
          if (el.type === 'image' && el.dataUrl) {
            // Replace data URL with placeholder to reduce payload size
            return {
              ...el,
              dataUrl: '[image data removed for API call]',
              hasImage: true,
            }
          }
          return el
        })
      }
      return parsed
    } catch {
      return null
    }
  }, [data.canvas])

  // Parse schema and API spec for chat context
  const parsedSchema = useMemo(() => {
    if (!currentSchema) return null
    try {
      return JSON.parse(currentSchema)
    } catch {
      return null
    }
  }, [currentSchema])

  const parsedApiSpec = useMemo(() => {
    if (!currentApiSpec) return null
    try {
      return JSON.parse(currentApiSpec)
    } catch {
      return null
    }
  }, [currentApiSpec])

  const handleCanvasChange = (canvasValue: string) => {
    const newData: DesignData = {
      mode: "canvas",
      canvas: canvasValue,
      text: data.text,
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

  // If no problem ID, show simplified view without chat
  if (!problemId || readOnly) {
    return (
      <div className="border rounded-lg overflow-hidden">
        <div className="bg-muted/50 px-4 py-2 border-b">
          <h3 className="text-sm font-medium flex items-center gap-2">
            <PenLine className="h-4 w-4 text-primary" />
            System Design
          </h3>
          <p className="text-xs text-muted-foreground">
            {readOnly ? "View your architecture diagram" : "Draw your architecture diagram"}
          </p>
        </div>

        <DesignCanvas
          value={data.canvas}
          onChange={handleCanvasChange}
          readOnly={readOnly}
        />

        {/* Design Summary */}
        <DesignTextSummary
          canvasData={data.canvas || null}
          textData={data.text || null}
          className="m-4"
        />

        {!readOnly && (
          <div className="border-t bg-muted/30 p-3">
            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <Lightbulb className="h-4 w-4 shrink-0 text-yellow-500" />
              <div>
                <strong>Tips:</strong>
                <span>
                  {" "}Use the toolbar to add shapes, icons, and arrows. Click to select, drag to move.
                  Double-click text or icons to edit labels.
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-muted/50 px-4 py-2 border-b flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium flex items-center gap-2">
            <PenLine className="h-4 w-4 text-primary" />
            System Design
          </h3>
          <p className="text-xs text-muted-foreground">
            Draw your diagram and chat with the AI coach for guidance
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setChatExpanded(!chatExpanded)}
          className="gap-1.5"
        >
          {chatExpanded ? (
            <>
              <Minimize2 className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Hide Coach</span>
            </>
          ) : (
            <>
              <Bot className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Show Coach</span>
            </>
          )}
        </Button>
      </div>

      {/* Main content - split view */}
      <div className="flex">
        {/* Canvas section */}
        <div className={chatExpanded ? "w-1/2 border-r" : "w-full"}>
          <Tabs value={mode} onValueChange={handleModeChange} className="w-full">
            <div className="border-b bg-background px-2">
              <TabsList className="h-10 bg-transparent">
                <TabsTrigger
                  value="canvas"
                  className="data-[state=active]:bg-muted gap-1.5"
                >
                  <PenLine className="h-3.5 w-3.5" />
                  Draw Diagram
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
          </Tabs>
        </div>

        {/* Chat section */}
        {chatExpanded && (
          <div className="w-1/2 flex flex-col" style={{ height: "600px" }}>
            <DesignChat
              problemId={problemId}
              currentSchema={parsedSchema}
              currentApiSpec={parsedApiSpec}
              currentDiagram={currentDiagram}
              readOnly={readOnly}
              difficultyLevel={difficultyLevel}
              onSummaryGenerated={handleSummaryGenerated}
            />
          </div>
        )}
      </div>

      {/* Design Summary Box (AI-generated) */}
      {designSummary && showSummaryBox && (
        <div className="border-t">
          <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-green-600" />
              <span className="text-sm font-medium">Design Summary</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSummaryBox(false)}
              className="text-xs"
            >
              Hide
            </Button>
          </div>
          <div className="p-4 max-h-80 overflow-y-auto">
            <DesignSummary
              summary={designSummary}
              diagramData={data.canvas}
            />
          </div>
        </div>
      )}

      {/* Design Components Summary */}
      <DesignTextSummary
        canvasData={data.canvas || null}
        textData={data.text || null}
        className="mx-4 mb-4"
      />

      {/* Tips section */}
      <div className="border-t bg-muted/30 p-3">
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <Lightbulb className="h-4 w-4 shrink-0 text-yellow-500" />
          <div>
            <strong>Tips:</strong>
            <span>
              {" "}Use the toolbar to add components to your diagram. The AI coach can help review your
              design and suggest improvements. Ask about architecture patterns, scalability, or trade-offs!
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
