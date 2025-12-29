/**
 * Design Text Summary Component
 * Displays a text summary of the user's design based on canvas elements
 */

import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { FileText, Database, Server, Cloud, Users, Globe, HardDrive, Scale, MessageSquare, Network, Layers, ArrowRight } from "lucide-react"

interface CanvasElement {
  id: string
  type: string
  label?: string
  text?: string
  x?: number
  y?: number
  endX?: number
  endY?: number
}

interface DesignTextSummaryProps {
  canvasData: string | null
  textData?: string | null
  className?: string
}

// Map element types to display names and icons
const elementTypeInfo: Record<string, { name: string; icon: React.ElementType; color: string }> = {
  database: { name: "Database", icon: Database, color: "text-blue-500" },
  server: { name: "Server", icon: Server, color: "text-green-500" },
  cloud: { name: "Cloud Service", icon: Cloud, color: "text-cyan-500" },
  user: { name: "User/Client", icon: Users, color: "text-purple-500" },
  globe: { name: "Internet/CDN", icon: Globe, color: "text-orange-500" },
  cache: { name: "Cache", icon: HardDrive, color: "text-yellow-500" },
  load_balancer: { name: "Load Balancer", icon: Scale, color: "text-indigo-500" },
  queue: { name: "Message Queue", icon: MessageSquare, color: "text-pink-500" },
  blob_storage: { name: "Blob Storage", icon: HardDrive, color: "text-teal-500" },
  dns: { name: "DNS", icon: Network, color: "text-gray-500" },
  client: { name: "Client App", icon: Layers, color: "text-emerald-500" },
  api_gateway: { name: "API Gateway", icon: Server, color: "text-violet-500" },
}

export default function DesignTextSummary({ canvasData, textData, className }: DesignTextSummaryProps) {
  const summary = useMemo(() => {
    // Parse canvas data
    let elements: CanvasElement[] = []
    if (canvasData) {
      try {
        const parsed = JSON.parse(canvasData)
        elements = parsed.elements || []
      } catch {
        // Invalid JSON
      }
    }

    // Count component types
    const componentCounts: Record<string, number> = {}
    const componentLabels: Record<string, string[]> = {}
    let arrowCount = 0
    let textElements: string[] = []

    elements.forEach((el) => {
      if (el.type === "arrow") {
        arrowCount++
      } else if (el.type === "text" && el.text) {
        textElements.push(el.text)
      } else if (elementTypeInfo[el.type]) {
        componentCounts[el.type] = (componentCounts[el.type] || 0) + 1
        if (el.label) {
          if (!componentLabels[el.type]) componentLabels[el.type] = []
          componentLabels[el.type].push(el.label)
        }
      }
    })

    // Sort by count
    const sortedComponents = Object.entries(componentCounts)
      .sort((a, b) => b[1] - a[1])

    return {
      components: sortedComponents,
      componentLabels,
      connections: arrowCount,
      textAnnotations: textElements,
      totalElements: elements.length,
      hasContent: elements.length > 0 || (textData && textData.trim().length > 0),
    }
  }, [canvasData, textData])

  if (!summary.hasContent) {
    return null
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          Design Summary
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Component Summary */}
        {summary.components.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Components ({summary.totalElements} elements)</p>
            <div className="flex flex-wrap gap-2">
              {summary.components.map(([type, count]) => {
                const info = elementTypeInfo[type]
                const Icon = info?.icon || Server
                const labels = summary.componentLabels[type] || []
                return (
                  <Badge
                    key={type}
                    variant="secondary"
                    className="text-xs py-1 flex items-center gap-1"
                    title={labels.length > 0 ? labels.join(", ") : undefined}
                  >
                    <Icon className={`h-3 w-3 ${info?.color || "text-muted-foreground"}`} />
                    {info?.name || type}
                    {count > 1 && <span className="ml-1 text-muted-foreground">×{count}</span>}
                  </Badge>
                )
              })}
              {summary.connections > 0 && (
                <Badge variant="outline" className="text-xs py-1 flex items-center gap-1">
                  <ArrowRight className="h-3 w-3" />
                  {summary.connections} connection{summary.connections !== 1 ? "s" : ""}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Component Labels */}
        {Object.keys(summary.componentLabels).length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Named Components</p>
            <div className="text-xs text-muted-foreground space-y-1">
              {Object.entries(summary.componentLabels).map(([type, labels]) => {
                const info = elementTypeInfo[type]
                return (
                  <div key={type} className="flex items-start gap-2">
                    <span className="font-medium">{info?.name || type}:</span>
                    <span>{labels.join(", ")}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Text Annotations */}
        {summary.textAnnotations.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Annotations</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              {summary.textAnnotations.slice(0, 5).map((text, idx) => (
                <li key={idx} className="truncate">• {text}</li>
              ))}
              {summary.textAnnotations.length > 5 && (
                <li className="text-muted-foreground">...and {summary.textAnnotations.length - 5} more</li>
              )}
            </ul>
          </div>
        )}

        {/* Text Mode Content */}
        {textData && textData.trim() && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Design Notes</p>
            <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-6">
              {textData}
            </p>
          </div>
        )}

        {/* Empty State */}
        {summary.components.length === 0 && !textData?.trim() && (
          <p className="text-xs text-muted-foreground italic">
            No design components added yet. Use the canvas to draw your system architecture.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
