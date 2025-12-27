/**
 * Terms of Service page
 *
 * Covers:
 * - AI Disclaimer
 * - No Employment Guarantee
 * - Data Usage
 * - Account Terms
 * - IP Rights
 * - Service Availability
 */

import { Link } from "react-router-dom"
import { ArrowLeft, FileText, Bot, Briefcase, Database, User, Scale, Server } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export default function TermsOfService() {
  const lastUpdated = "December 27, 2024"

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/problems">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>
        <div className="flex items-center gap-3 mb-2">
          <FileText className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Terms of Service</h1>
        </div>
        <p className="text-muted-foreground">Last updated: {lastUpdated}</p>
      </div>

      {/* Introduction */}
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground">
            Welcome to the System Design Interview Platform. By using this service, you agree to
            these Terms of Service. Please read them carefully before using the platform.
          </p>
        </CardContent>
      </Card>

      {/* AI Disclaimer */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            AI Disclaimer
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            This platform uses artificial intelligence (Claude by Anthropic) to provide design
            feedback, coaching, and scoring. You acknowledge and agree that:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              All feedback, scores, and evaluations are <strong>AI-generated</strong> and do not
              represent human expert opinions
            </li>
            <li>
              AI responses may contain inaccuracies, hallucinations, or outdated information
            </li>
            <li>
              Scores are indicative only and may not reflect actual interview performance
            </li>
            <li>
              The AI coach provides general guidance and should not be considered definitive
              system design advice
            </li>
            <li>
              We do not guarantee the accuracy, completeness, or reliability of AI-generated
              content
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* No Employment Guarantee */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" />
            No Employment Guarantee
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            This platform is designed for <strong>educational and practice purposes only</strong>.
            You understand and agree that:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              Using this platform does not guarantee success in any job interview or hiring process
            </li>
            <li>
              High scores on this platform do not correlate to or predict actual interview
              performance
            </li>
            <li>
              We make no representations about employment outcomes based on platform usage
            </li>
            <li>
              This platform is not affiliated with any company's hiring process
            </li>
            <li>
              The difficulty levels (L5/L6/L7) are for practice purposes and may not reflect
              actual company leveling standards
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Data Usage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Data Usage
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            When you use our platform, we collect and process certain data. By using our service,
            you consent to:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              <strong>Account Data:</strong> Email address, name, and profile picture from your
              OAuth provider (Google, Facebook, LinkedIn, or GitHub)
            </li>
            <li>
              <strong>Design Data:</strong> Your system design diagrams, API specifications,
              schema definitions, and design text
            </li>
            <li>
              <strong>Conversation History:</strong> Chat messages exchanged with the AI coach
              during design sessions
            </li>
            <li>
              <strong>Submission Data:</strong> All submissions, test results, and evaluation
              scores
            </li>
            <li>
              <strong>Usage Data:</strong> How you interact with the platform for improvement
              purposes
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            For more details, please see our{" "}
            <Link to="/privacy" className="text-primary hover:underline">
              Privacy Policy
            </Link>
            .
          </p>
        </CardContent>
      </Card>

      {/* Account Terms */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Account Terms
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            By creating an account and using this platform, you agree to:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              Provide accurate information when creating your account
            </li>
            <li>
              Keep your account credentials secure and not share access with others
            </li>
            <li>
              Use the platform for lawful purposes only
            </li>
            <li>
              Not attempt to reverse engineer, hack, or disrupt the service
            </li>
            <li>
              Not use automated tools or bots to access the service
            </li>
            <li>
              Not upload malicious content, malware, or harmful code
            </li>
            <li>
              Not abuse the AI coaching system or attempt to manipulate scores
            </li>
            <li>
              Accept that we may terminate accounts that violate these terms
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            You may delete your account and all associated data at any time from your{" "}
            <Link to="/settings" className="text-primary hover:underline">
              Account Settings
            </Link>
            .
          </p>
        </CardContent>
      </Card>

      {/* IP Rights */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Scale className="h-5 w-5 text-primary" />
            Intellectual Property Rights
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            Regarding intellectual property and content ownership:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              <strong>Your Content:</strong> You retain ownership of your original design
              submissions, diagrams, and ideas
            </li>
            <li>
              <strong>Platform License:</strong> You grant us a non-exclusive license to store,
              process, and display your content to provide the service
            </li>
            <li>
              <strong>AI-Generated Content:</strong> Feedback and suggestions generated by the AI
              are provided for your use but may be generated for other users as well
            </li>
            <li>
              <strong>Platform Content:</strong> The platform interface, problems, and
              documentation are owned by us and protected by copyright
            </li>
            <li>
              <strong>No Commercial Use:</strong> You may not use platform content for commercial
              purposes without permission
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Service Availability */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            Service Availability
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            Regarding the availability and operation of our service:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              We provide the service on an "as is" and "as available" basis
            </li>
            <li>
              We do not guarantee 100% uptime or uninterrupted access
            </li>
            <li>
              We may modify, suspend, or discontinue features at any time
            </li>
            <li>
              Scheduled maintenance may cause temporary service interruptions
            </li>
            <li>
              We are not liable for any losses due to service unavailability
            </li>
            <li>
              We may update these terms with notice provided through the platform
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Limitation of Liability */}
      <Card>
        <CardHeader>
          <CardTitle>Limitation of Liability</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            To the maximum extent permitted by law:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              We are not liable for any indirect, incidental, special, or consequential damages
            </li>
            <li>
              Our total liability is limited to the amount you paid for the service (if any)
            </li>
            <li>
              We are not responsible for third-party services or content accessed through links
            </li>
            <li>
              You use the platform at your own risk
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Contact */}
      <Card>
        <CardHeader>
          <CardTitle>Contact Us</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            If you have any questions about these Terms of Service, please contact us at{" "}
            <a href="mailto:support@systemdesignplatform.com" className="text-primary hover:underline">
              support@systemdesignplatform.com
            </a>
          </p>
        </CardContent>
      </Card>

      {/* Footer links */}
      <div className="flex justify-center gap-4 text-sm text-muted-foreground pb-8">
        <Link to="/privacy" className="hover:text-primary hover:underline">
          Privacy Policy
        </Link>
        <span>|</span>
        <Link to="/settings" className="hover:text-primary hover:underline">
          Account Settings
        </Link>
      </div>
    </div>
  )
}
