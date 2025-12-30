/**
 * Code Editor component using Monaco Editor
 *
 * Supports multiple languages for distributed consensus implementations
 */

import { Suspense, useMemo } from "react"
import { lazyLoadMonaco } from "@/lib/lazyWithRetry"
import { useTheme } from "@/hooks/useTheme"
import { Skeleton } from "@/components/ui/skeleton"
import type { SupportedLanguage } from "@/types"

const Editor = lazyLoadMonaco()

// Map our language types to Monaco language IDs
const languageToMonaco: Record<SupportedLanguage, string> = {
  python: "python",
  go: "go",
  java: "java",
  cpp: "cpp",
  rust: "rust",
}

interface CodeEditorProps {
  value: string
  onChange?: (value: string) => void
  language: SupportedLanguage
  readOnly?: boolean
  height?: string | number
  className?: string
}

function EditorSkeleton({ height = 500 }: { height?: string | number }) {
  return (
    <div style={{ height }} className="border rounded-md overflow-hidden">
      <div className="bg-muted/30 p-4 space-y-3">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
  )
}

export default function CodeEditor({
  value,
  onChange,
  language,
  readOnly = false,
  height = 500,
  className = "",
}: CodeEditorProps) {
  const { resolvedTheme } = useTheme()

  const monacoLanguage = languageToMonaco[language]
  const theme = resolvedTheme === "dark" ? "vs-dark" : "light"

  // Editor options
  const options = useMemo(
    () => ({
      readOnly,
      minimap: { enabled: true },
      fontSize: 14,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
      lineNumbers: "on" as const,
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: language === "python" ? 4 : 4,
      insertSpaces: true,
      wordWrap: "on" as const,
      folding: true,
      bracketPairColorization: { enabled: true },
      guides: {
        bracketPairs: true,
        indentation: true,
      },
    }),
    [readOnly, language]
  )

  return (
    <div className={`border rounded-md overflow-hidden ${className}`}>
      <Suspense fallback={<EditorSkeleton height={height} />}>
        <Editor
          height={height}
          language={monacoLanguage}
          value={value}
          theme={theme}
          options={options}
          onChange={(newValue) => {
            if (onChange && newValue !== undefined) {
              onChange(newValue)
            }
          }}
        />
      </Suspense>
    </div>
  )
}
