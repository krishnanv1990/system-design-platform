/**
 * Deployed Components Card
 * Shows detailed information about what was deployed to GCP
 */

import { useState } from "react"
import {
  ChevronDown,
  ChevronUp,
  Server,
  Database,
  HardDrive,
  Globe,
  Lock,
  Cpu,
  MemoryStick,
  Container,
  GitBranch,
  Clock,
  ExternalLink,
  Cloud,
  Layers,
  Network,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface DeployedComponent {
  name: string
  type: string
  icon: React.ElementType
  iconColor: string
  description: string
  specs?: { label: string; value: string }[]
  consoleUrl?: string
}

interface DeployedComponentsCardProps {
  serviceName?: string
  region?: string
  endpointUrl?: string
  containerImage?: string
  consoleLinks?: {
    cloud_run_service?: string
    cloud_run_logs?: string
    cloud_run_revisions?: string
    cloud_build_history?: string
    container_registry?: string
  }
}

export default function DeployedComponentsCard({
  serviceName,
  region = "us-central1",
  endpointUrl,
  containerImage,
  consoleLinks = {},
}: DeployedComponentsCardProps) {
  const [expanded, setExpanded] = useState(false)

  const components: DeployedComponent[] = [
    {
      name: "Cloud Run Service",
      type: "Serverless Container",
      icon: Server,
      iconColor: "text-blue-500",
      description:
        "Fully managed serverless platform that automatically scales your containerized application",
      specs: [
        { label: "Service Name", value: serviceName || "url-shortener" },
        { label: "Region", value: region },
        { label: "CPU", value: "1 vCPU" },
        { label: "Memory", value: "512 MB" },
        { label: "Min Instances", value: "0 (scale to zero)" },
        { label: "Max Instances", value: "100" },
        { label: "Concurrency", value: "80 requests/instance" },
      ],
      consoleUrl: consoleLinks.cloud_run_service,
    },
    {
      name: "Container Image",
      type: "Artifact Registry",
      icon: Container,
      iconColor: "text-purple-500",
      description:
        "Docker container image built from your code and stored in Google Artifact Registry",
      specs: [
        { label: "Image", value: containerImage?.split("/").pop() || "sdp-backend:latest" },
        { label: "Base Image", value: "python:3.11-slim" },
        { label: "Registry", value: "us-central1-docker.pkg.dev" },
        { label: "Build Tool", value: "Cloud Build" },
      ],
      consoleUrl: consoleLinks.container_registry,
    },
    {
      name: "Load Balancer",
      type: "HTTPS Endpoint",
      icon: Globe,
      iconColor: "text-green-500",
      description:
        "Google-managed HTTPS load balancer with automatic SSL certificate provisioning",
      specs: [
        { label: "Protocol", value: "HTTPS" },
        { label: "SSL Certificate", value: "Managed by Google" },
        { label: "Domain", value: endpointUrl?.replace("https://", "").split("/")[0] || "*.run.app" },
        { label: "CDN", value: "Available" },
      ],
    },
    {
      name: "Cloud Build",
      type: "CI/CD Pipeline",
      icon: GitBranch,
      iconColor: "text-orange-500",
      description:
        "Automated build service that compiled your code and created the container image",
      specs: [
        { label: "Build Type", value: "Docker" },
        { label: "Trigger", value: "Manual submission" },
        { label: "Timeout", value: "10 minutes" },
      ],
      consoleUrl: consoleLinks.cloud_build_history,
    },
    {
      name: "VPC Network",
      type: "Networking",
      icon: Network,
      iconColor: "text-cyan-500",
      description:
        "Virtual Private Cloud network with automatic security and routing",
      specs: [
        { label: "Ingress", value: "All traffic allowed" },
        { label: "Egress", value: "All traffic allowed" },
        { label: "Internal Only", value: "No (public endpoint)" },
      ],
    },
    {
      name: "IAM & Security",
      type: "Access Control",
      icon: Lock,
      iconColor: "text-red-500",
      description:
        "Identity and Access Management for service authentication and authorization",
      specs: [
        { label: "Authentication", value: "Allow unauthenticated" },
        { label: "Service Account", value: "Compute default" },
        { label: "Invoker Role", value: "allUsers" },
      ],
    },
  ]

  return (
    <Card className="mb-4">
      <CardHeader
        className="cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              Deployed Infrastructure
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              {components.length} components deployed to Google Cloud Platform
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {region}
            </Badge>
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
          {/* Architecture Overview */}
          <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/20 dark:to-purple-950/20 rounded-lg border">
            <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
              <Cloud className="h-4 w-4 text-blue-500" />
              Architecture Overview
            </h4>
            <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground overflow-x-auto py-2">
              <div className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/30 rounded border border-green-300 dark:border-green-700">
                <Globe className="h-3 w-3" />
                <span>HTTPS Request</span>
              </div>
              <span className="text-lg">→</span>
              <div className="flex items-center gap-1 px-2 py-1 bg-blue-100 dark:bg-blue-900/30 rounded border border-blue-300 dark:border-blue-700">
                <Server className="h-3 w-3" />
                <span>Cloud Run</span>
              </div>
              <span className="text-lg">→</span>
              <div className="flex items-center gap-1 px-2 py-1 bg-purple-100 dark:bg-purple-900/30 rounded border border-purple-300 dark:border-purple-700">
                <Container className="h-3 w-3" />
                <span>Container</span>
              </div>
              <span className="text-lg">→</span>
              <div className="flex items-center gap-1 px-2 py-1 bg-orange-100 dark:bg-orange-900/30 rounded border border-orange-300 dark:border-orange-700">
                <Database className="h-3 w-3" />
                <span>Your App</span>
              </div>
            </div>
          </div>

          {/* Component Grid */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {components.map((component) => {
              const Icon = component.icon
              return (
                <div
                  key={component.name}
                  className="p-3 bg-muted/30 rounded-lg border hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={cn("p-1.5 rounded-md bg-background", component.iconColor)}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <span className="text-sm font-medium">{component.name}</span>
                        <p className="text-xs text-muted-foreground">{component.type}</p>
                      </div>
                    </div>
                    {component.consoleUrl && (
                      <a
                        href={component.consoleUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-primary"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mb-3">
                    {component.description}
                  </p>
                  {component.specs && (
                    <div className="space-y-1">
                      {component.specs.map((spec) => (
                        <div
                          key={spec.label}
                          className="flex justify-between text-xs"
                        >
                          <span className="text-muted-foreground">{spec.label}:</span>
                          <span className="font-mono truncate ml-2 max-w-[120px]" title={spec.value}>
                            {spec.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Resource Summary */}
          <div className="mt-4 p-3 bg-muted/30 rounded-lg border">
            <h4 className="text-sm font-medium mb-2">Resource Summary</h4>
            <div className="grid gap-2 md:grid-cols-4 text-xs">
              <div className="flex items-center gap-2">
                <Cpu className="h-3.5 w-3.5 text-blue-500" />
                <span>Max 100 vCPU</span>
              </div>
              <div className="flex items-center gap-2">
                <MemoryStick className="h-3.5 w-3.5 text-green-500" />
                <span>Max 51.2 GB RAM</span>
              </div>
              <div className="flex items-center gap-2">
                <HardDrive className="h-3.5 w-3.5 text-purple-500" />
                <span>Ephemeral Storage</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-orange-500" />
                <span>Auto-cleanup enabled</span>
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
