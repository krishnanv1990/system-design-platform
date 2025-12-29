/**
 * Test Scenario Details Component
 * Shows detailed information about what each test type covers
 */

import { useState } from "react"
import {
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Zap,
  Shield,
  Database,
  Server,
  Cloud,
  Activity,
  Timer,
  Users,
  AlertTriangle,
  HardDrive,
  Wifi,
  RefreshCw,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface TestScenario {
  name: string
  description: string
  icon: React.ElementType
  iconColor: string
  tests: string[]
}

const functionalScenarios: TestScenario[] = [
  {
    name: "Core CRUD Operations",
    description: "Tests basic Create, Read, Update, Delete operations on URLs",
    icon: Database,
    iconColor: "text-blue-500",
    tests: [
      "Create short URL with valid input",
      "Create short URL with custom code",
      "Retrieve URL by short code",
      "Handle non-existent URLs (404)",
      "Delete URL functionality",
    ],
  },
  {
    name: "URL Validation",
    description: "Ensures proper validation of input URLs",
    icon: Shield,
    iconColor: "text-green-500",
    tests: [
      "Reject invalid URLs",
      "Reject empty URLs",
      "Reject missing URL field",
      "Handle malicious URLs (XSS, injection)",
      "Handle special characters in URLs",
    ],
  },
  {
    name: "URL Expiration",
    description: "Verifies URL TTL and expiration behavior",
    icon: Timer,
    iconColor: "text-orange-500",
    tests: [
      "URL expires after TTL",
      "URL accessible before expiry",
      "Expiry time returned in response",
    ],
  },
  {
    name: "Data Integrity",
    description: "Ensures data is stored and retrieved correctly",
    icon: HardDrive,
    iconColor: "text-purple-500",
    tests: [
      "Original URL preserved correctly",
      "Short code uniqueness",
      "Click count increments",
    ],
  },
  {
    name: "Edge Cases",
    description: "Tests unusual but valid scenarios",
    icon: AlertTriangle,
    iconColor: "text-yellow-500",
    tests: [
      "Very long URLs (2000+ chars)",
      "URLs with unicode characters",
      "Concurrent requests handling",
      "Rate limiting behavior",
    ],
  },
]

const performanceScenarios: TestScenario[] = [
  {
    name: "Load Testing",
    description: "Simulates realistic user traffic patterns",
    icon: Users,
    iconColor: "text-blue-500",
    tests: [
      "80% read / 20% write ratio",
      "Variable wait times (0.5-2s)",
      "Concurrent user simulation",
      "Sustained load for 60 seconds",
    ],
  },
  {
    name: "Latency Benchmarks",
    description: "Measures response time under load",
    icon: Zap,
    iconColor: "text-yellow-500",
    tests: [
      "P50 latency < 100ms",
      "P95 latency < 500ms",
      "P99 latency < 1000ms",
      "Create URL < 2000ms avg",
    ],
  },
  {
    name: "Throughput Testing",
    description: "Measures requests per second capacity",
    icon: Activity,
    iconColor: "text-green-500",
    tests: [
      "Target RPS measurement",
      "Error rate under load",
      "Successful request ratio",
      "Response time distribution",
    ],
  },
  {
    name: "Traffic Patterns",
    description: "Tests various traffic scenarios",
    icon: RefreshCw,
    iconColor: "text-purple-500",
    tests: [
      "URL creation (high frequency)",
      "URL access/redirect (highest frequency)",
      "Analytics retrieval (medium frequency)",
      "Health checks (low frequency)",
    ],
  },
]

const chaosScenarios: TestScenario[] = [
  {
    name: "Network Failures",
    description: "Tests resilience to network issues",
    icon: Wifi,
    iconColor: "text-red-500",
    tests: [
      "Network partition handling",
      "High latency (500ms+) injection",
      "Packet loss simulation",
      "Cross-region latency",
    ],
  },
  {
    name: "Database Failures",
    description: "Tests behavior when database is degraded",
    icon: Database,
    iconColor: "text-orange-500",
    tests: [
      "Database latency injection (5s+)",
      "Connection failure handling",
      "Partial write failures",
      "Graceful error responses",
    ],
  },
  {
    name: "Cache Failures",
    description: "Tests fallback when cache is unavailable",
    icon: Server,
    iconColor: "text-yellow-500",
    tests: [
      "Cache unavailable fallback",
      "Cache corruption handling",
      "Cache miss handling",
      "Write-through behavior",
    ],
  },
  {
    name: "Infrastructure Failures",
    description: "Tests zonal and instance failures",
    icon: Cloud,
    iconColor: "text-purple-500",
    tests: [
      "Zonal outage simulation",
      "Instance crash recovery",
      "Cold start handling",
      "Autoscaling behavior",
    ],
  },
]

interface TestScenarioDetailsProps {
  type: "functional" | "performance" | "chaos"
  passedTests?: string[]
  failedTests?: string[]
}

export default function TestScenarioDetails({
  type,
  passedTests = [],
  failedTests = [],
}: TestScenarioDetailsProps) {
  const [expanded, setExpanded] = useState(false)

  const scenarios =
    type === "functional"
      ? functionalScenarios
      : type === "performance"
      ? performanceScenarios
      : chaosScenarios

  const title =
    type === "functional"
      ? "Functional Test Scenarios"
      : type === "performance"
      ? "Performance Test Scenarios"
      : "Chaos Test Scenarios"

  const description =
    type === "functional"
      ? "Tests core API functionality, validation, and data integrity"
      : type === "performance"
      ? "Tests system performance under various load conditions"
      : "Tests system resilience to failures and degraded conditions"

  const totalTests = passedTests.length + failedTests.length
  const passRate = totalTests > 0 ? Math.round((passedTests.length / totalTests) * 100) : 0

  return (
    <Card className="mb-4">
      <CardHeader
        className="cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm flex items-center gap-2">
              {type === "functional" && <Shield className="h-4 w-4 text-blue-500" />}
              {type === "performance" && <Zap className="h-4 w-4 text-yellow-500" />}
              {type === "chaos" && <AlertTriangle className="h-4 w-4 text-red-500" />}
              {title}
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Pass/Fail Summary */}
            {totalTests > 0 && (
              <div className="flex items-center gap-2 text-xs">
                <span className="flex items-center gap-1 text-green-600">
                  <CheckCircle className="h-3.5 w-3.5" />
                  {passedTests.length}
                </span>
                <span className="flex items-center gap-1 text-red-600">
                  <XCircle className="h-3.5 w-3.5" />
                  {failedTests.length}
                </span>
                <span className={cn(
                  "font-medium",
                  passRate === 100 ? "text-green-600" :
                  passRate >= 50 ? "text-yellow-600" : "text-red-600"
                )}>
                  ({passRate}%)
                </span>
              </div>
            )}
            {expanded ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0">
          {/* Actual Test Results List */}
          {totalTests > 0 && (
            <div className="mb-4 p-3 bg-muted/50 rounded-lg border">
              <h4 className="text-sm font-medium mb-3">Actual Test Results</h4>
              <div className="grid gap-4 md:grid-cols-2">
                {/* Passed Tests */}
                {passedTests.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-green-600 mb-2 flex items-center gap-1">
                      <CheckCircle className="h-3.5 w-3.5" />
                      Passed ({passedTests.length})
                    </p>
                    <ul className="space-y-1 max-h-32 overflow-y-auto">
                      {passedTests.map((test, idx) => (
                        <li key={idx} className="text-xs flex items-start gap-1.5 text-green-600">
                          <CheckCircle className="h-3 w-3 mt-0.5 shrink-0" />
                          <span>{test}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {/* Failed Tests */}
                {failedTests.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-600 mb-2 flex items-center gap-1">
                      <XCircle className="h-3.5 w-3.5" />
                      Failed ({failedTests.length})
                    </p>
                    <ul className="space-y-1 max-h-32 overflow-y-auto">
                      {failedTests.map((test, idx) => (
                        <li key={idx} className="text-xs flex items-start gap-1.5 text-red-600">
                          <XCircle className="h-3 w-3 mt-0.5 shrink-0" />
                          <span>{test}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Scenario Descriptions */}
          <h4 className="text-sm font-medium mb-3">Test Scenarios Covered</h4>
          <div className="grid gap-4 md:grid-cols-2">
            {scenarios.map((scenario) => {
              const Icon = scenario.icon
              return (
                <div
                  key={scenario.name}
                  className="p-3 bg-muted/30 rounded-lg border"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className={cn("h-4 w-4", scenario.iconColor)} />
                    <span className="text-sm font-medium">{scenario.name}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">
                    {scenario.description}
                  </p>
                  <ul className="space-y-1">
                    {scenario.tests.map((test) => {
                      const isPassed = passedTests.some((t) =>
                        t.toLowerCase().includes(test.toLowerCase().slice(0, 10))
                      )
                      const isFailed = failedTests.some((t) =>
                        t.toLowerCase().includes(test.toLowerCase().slice(0, 10))
                      )
                      return (
                        <li
                          key={test}
                          className="text-xs flex items-start gap-1.5"
                        >
                          {isPassed ? (
                            <CheckCircle className="h-3 w-3 text-success mt-0.5 shrink-0" />
                          ) : isFailed ? (
                            <XCircle className="h-3 w-3 text-destructive mt-0.5 shrink-0" />
                          ) : (
                            <div className="h-3 w-3 rounded-full border mt-0.5 shrink-0" />
                          )}
                          <span
                            className={cn(
                              isPassed && "text-success",
                              isFailed && "text-destructive"
                            )}
                          >
                            {test}
                          </span>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )
            })}
          </div>
        </CardContent>
      )}
    </Card>
  )
}
