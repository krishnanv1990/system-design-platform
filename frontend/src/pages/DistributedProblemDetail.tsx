/**
 * Distributed Consensus Problem Detail Page
 *
 * Shows problem details, gRPC proto, language selector, and code editor
 * for implementing distributed consensus algorithms.
 */

import { useState, useEffect, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  AlertCircle,
  RefreshCw,
  Server,
  FileCode,
  Play,
  Save,
  Loader2,
  CheckCircle,
  Code,
  BookOpen,
  RotateCcw,
  History,
} from "lucide-react"
import { distributedProblemsApi, distributedSubmissionsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/hooks/useToast"
import { useConfirm } from "@/components/ui/confirm-dialog"
import CodeEditor from "@/components/CodeEditor"
import type { DistributedProblem, SupportedLanguage } from "@/types"

// Language display info
const languageInfo: Record<SupportedLanguage, { label: string; icon: string }> = {
  python: { label: "Python", icon: "🐍" },
  go: { label: "Go", icon: "🐹" },
  java: { label: "Java", icon: "☕" },
  cpp: { label: "C++", icon: "⚡" },
  rust: { label: "Rust", icon: "🦀" },
}

// Difficulty variants
const difficultyVariant: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <Skeleton className="h-8 w-64" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-[500px]" />
        <Skeleton className="h-[500px]" />
      </div>
    </div>
  )
}

export default function DistributedProblemDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [problem, setProblem] = useState<DistributedProblem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedLanguage, setSelectedLanguage] = useState<SupportedLanguage>("python")
  const [code, setCode] = useState<string>("")
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [lastSavedCode, setLastSavedCode] = useState<string | null>(null)

  // Load problem details
  const loadProblem = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const data = await distributedProblemsApi.get(parseInt(id))
      setProblem(data)
      // Set initial language if available
      if (data.supported_languages.length > 0) {
        setSelectedLanguage(data.supported_languages[0])
      }
    } catch (err: any) {
      console.error("Failed to load problem:", err)
      const message = err.response?.data?.detail || err.message || "Failed to load problem"
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [id])

  // Load template or saved code when language changes
  const loadCode = useCallback(async () => {
    if (!id || !problem) return
    try {
      // First try to load saved code
      const savedCode = await distributedProblemsApi.getSavedCode(parseInt(id), selectedLanguage)
      if (savedCode) {
        setCode(savedCode)
        setLastSavedCode(savedCode) // Track last saved version
      } else {
        // Fall back to template
        const template = await distributedProblemsApi.getTemplate(parseInt(id), selectedLanguage)
        setCode(template)
        setLastSavedCode(null) // No saved version exists
      }
      setHasUnsavedChanges(false)
    } catch (err: any) {
      // If no saved code or template, use the one from problem
      const langTemplate = problem.language_templates[selectedLanguage]
      if (langTemplate) {
        setCode(langTemplate.template)
      } else {
        setCode("// Template not available for this language")
      }
      setLastSavedCode(null)
      setHasUnsavedChanges(false)
    }
  }, [id, problem, selectedLanguage])

  useEffect(() => {
    loadProblem()
  }, [loadProblem])

  useEffect(() => {
    if (problem) {
      loadCode()
    }
  }, [problem, selectedLanguage, loadCode])

  // Handle code changes
  const handleCodeChange = (newCode: string) => {
    setCode(newCode)
    setHasUnsavedChanges(true)
  }

  // Save code
  const handleSave = async () => {
    if (!id || !code) return
    setSaving(true)
    try {
      await distributedProblemsApi.saveCode(parseInt(id), selectedLanguage, code)
      setLastSavedCode(code) // Track the saved version
      setHasUnsavedChanges(false)
      toast({
        title: "Code saved",
        description: "Your code has been saved successfully.",
      })
    } catch (err: any) {
      toast({
        title: "Save failed",
        description: err.response?.data?.detail || "Failed to save code",
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  // Submit code
  const handleSubmit = async () => {
    if (!id || !code) return
    setSubmitting(true)
    try {
      const submission = await distributedSubmissionsApi.submit({
        problem_id: parseInt(id),
        language: selectedLanguage,
        source_code: code,
      })
      toast({
        title: "Submission created",
        description: "Your code is being compiled and tested.",
      })
      navigate(`/distributed/submissions/${submission.id}`)
    } catch (err: any) {
      toast({
        title: "Submission failed",
        description: err.response?.data?.detail || "Failed to submit code",
        variant: "destructive",
      })
    } finally {
      setSubmitting(false)
    }
  }

  // Reset to template
  const handleResetToTemplate = async () => {
    if (!id) return

    const confirmed = await confirm({
      title: "Reset to Template",
      message: `This will replace your current ${languageInfo[selectedLanguage].label} code with the original template. Any unsaved changes will be lost. Are you sure?`,
      type: "warning",
      confirmLabel: "Reset to Template",
      cancelLabel: "Cancel",
    })

    if (!confirmed) return

    setResetting(true)
    try {
      const template = await distributedProblemsApi.getTemplate(parseInt(id), selectedLanguage)
      setCode(template)
      setHasUnsavedChanges(true)
      toast({
        title: "Code reset",
        description: `Your ${languageInfo[selectedLanguage].label} code has been reset to the template.`,
      })
    } catch (err: any) {
      toast({
        title: "Reset failed",
        description: err.response?.data?.detail || "Failed to reset code",
        variant: "destructive",
      })
    } finally {
      setResetting(false)
    }
  }

  // Reset to last saved version
  const handleResetToSaved = async () => {
    if (!lastSavedCode) {
      toast({
        title: "No saved version",
        description: "There is no saved version to reset to. Try 'Reset to Template' instead.",
        variant: "destructive",
      })
      return
    }

    const confirmed = await confirm({
      title: "Reset to Last Saved",
      message: `This will replace your current ${languageInfo[selectedLanguage].label} code with the last saved version. Any unsaved changes will be lost. Are you sure?`,
      type: "warning",
      confirmLabel: "Reset to Saved",
      cancelLabel: "Cancel",
    })

    if (!confirmed) return

    setCode(lastSavedCode)
    setHasUnsavedChanges(false)
    toast({
      title: "Code reset",
      description: `Your ${languageInfo[selectedLanguage].label} code has been reset to the last saved version.`,
    })
  }

  if (loading) {
    return <DetailSkeleton />
  }

  if (error || !problem) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <p className="text-destructive font-medium mb-2">Failed to load problem</p>
        <p className="text-muted-foreground text-sm mb-4">{error}</p>
        <div className="flex gap-2">
          <Button onClick={() => navigate("/distributed")} variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Problems
          </Button>
          <Button onClick={loadProblem} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/distributed")}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Problems
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`/distributed/history?problem_id=${id}`)}
            >
              <History className="mr-2 h-4 w-4" />
              My Submissions
            </Button>
          </div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Server className="h-6 w-6 text-primary" />
            {problem.title}
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge variant={difficultyVariant[problem.difficulty]}>
              {problem.difficulty}
            </Badge>
            <Badge variant="outline">
              <Server className="h-3 w-3 mr-1" />
              {problem.cluster_size} nodes
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasUnsavedChanges && (
            <span className="text-sm text-muted-foreground">Unsaved changes</span>
          )}
          <Button
            onClick={handleResetToSaved}
            variant="outline"
            disabled={resetting || !lastSavedCode}
            title={!lastSavedCode ? "No saved version available" : "Reset to last saved version"}
          >
            {resetting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="mr-2 h-4 w-4" />
            )}
            Reset to Saved
          </Button>
          <Button onClick={handleResetToTemplate} variant="outline" disabled={resetting}>
            {resetting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="mr-2 h-4 w-4" />
            )}
            Reset to Template
          </Button>
          <Button onClick={handleSave} variant="outline" disabled={saving || !hasUnsavedChanges}>
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            Submit
          </Button>
        </div>
      </div>

      {/* Description */}
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground">{problem.description}</p>
        </CardContent>
      </Card>

      {/* Main content */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Proto and Hints */}
        <div className="space-y-4">
          <Tabs defaultValue="proto">
            <TabsList>
              <TabsTrigger value="proto" className="flex items-center gap-2">
                <FileCode className="h-4 w-4" />
                gRPC Proto
              </TabsTrigger>
              <TabsTrigger value="hints" className="flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                Hints
              </TabsTrigger>
            </TabsList>
            <TabsContent value="proto" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileCode className="h-4 w-4" />
                    gRPC Service Definition
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="bg-muted p-4 rounded-md overflow-auto text-sm max-h-[400px]">
                    <code>{problem.grpc_proto}</code>
                  </pre>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="hints" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <BookOpen className="h-4 w-4" />
                    Implementation Hints
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {problem.hints && problem.hints.length > 0 ? (
                    <ul className="space-y-2">
                      {problem.hints.map((hint, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          <span className="text-sm text-muted-foreground">{hint}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No hints available for this problem.
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {/* Test scenarios */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Test Scenarios</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {problem.test_scenarios.map((scenario, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-2 p-2 rounded-md bg-muted/50"
                  >
                    <Badge
                      variant={
                        scenario.test_type === "functional"
                          ? "default"
                          : scenario.test_type === "performance"
                          ? "secondary"
                          : "destructive"
                      }
                      className="mt-0.5"
                    >
                      {scenario.test_type}
                    </Badge>
                    <div>
                      <p className="font-medium text-sm">{scenario.name}</p>
                      <p className="text-xs text-muted-foreground">{scenario.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Language selector and Code editor */}
        <div className="space-y-4">
          {/* Language selector */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Code className="h-4 w-4" />
                Select Language
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {problem.supported_languages.map((lang) => (
                  <Button
                    key={lang}
                    variant={selectedLanguage === lang ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedLanguage(lang)}
                  >
                    <span className="mr-1">{languageInfo[lang].icon}</span>
                    {languageInfo[lang].label}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Code editor */}
          <div className="relative">
            <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
              <Badge variant="secondary">
                {languageInfo[selectedLanguage].icon} {languageInfo[selectedLanguage].label}
              </Badge>
            </div>
            <CodeEditor
              value={code}
              onChange={handleCodeChange}
              language={selectedLanguage}
              height={500}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
