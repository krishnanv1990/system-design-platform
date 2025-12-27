/**
 * Privacy Policy page
 *
 * Covers data collection, usage, storage, and user rights
 * GDPR and CCPA compliant
 */

import { Link } from "react-router-dom"
import { ArrowLeft, Shield, Database, Eye, Lock, Trash2, Globe, Cookie } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export default function PrivacyPolicy() {
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
          <Shield className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Privacy Policy</h1>
        </div>
        <p className="text-muted-foreground">Last updated: {lastUpdated}</p>
      </div>

      {/* Introduction */}
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground">
            Your privacy is important to us. This Privacy Policy explains how we collect, use,
            store, and protect your personal information when you use the System Design Interview
            Platform.
          </p>
        </CardContent>
      </Card>

      {/* Information We Collect */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Information We Collect
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">Account Information</h4>
            <p className="text-muted-foreground text-sm">
              When you sign in using OAuth providers (Google, Facebook, LinkedIn, or GitHub),
              we receive:
            </p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-4 mt-2">
              <li>Email address</li>
              <li>Display name</li>
              <li>Profile picture URL</li>
              <li>OAuth provider identifier</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium mb-2">Design and Submission Data</h4>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-4">
              <li>System design diagrams you create</li>
              <li>Database schema definitions</li>
              <li>API specifications</li>
              <li>Design text and descriptions</li>
              <li>Chat conversations with the AI coach</li>
              <li>Submission results and scores</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium mb-2">Technical Data</h4>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-4">
              <li>Browser type and version</li>
              <li>Device information</li>
              <li>IP address (anonymized for analytics)</li>
              <li>Pages visited and features used</li>
              <li>Session duration and timestamps</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* How We Use Your Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-primary" />
            How We Use Your Information
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">We use your information to:</p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              <strong>Provide the Service:</strong> Process your design submissions, run tests,
              and provide AI coaching
            </li>
            <li>
              <strong>Personalize Experience:</strong> Remember your preferences and provide
              relevant content
            </li>
            <li>
              <strong>Improve the Platform:</strong> Analyze usage patterns to enhance features
              and fix issues
            </li>
            <li>
              <strong>Communication:</strong> Send important service updates and respond to
              support requests
            </li>
            <li>
              <strong>Security:</strong> Detect and prevent fraud, abuse, and security threats
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Data Storage and Security */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-primary" />
            Data Storage and Security
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">We implement industry-standard security measures:</p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>All data is encrypted in transit using TLS/HTTPS</li>
            <li>Sensitive data is encrypted at rest</li>
            <li>Access to user data is restricted to authorized personnel only</li>
            <li>Regular security audits and vulnerability assessments</li>
            <li>Secure OAuth authentication - we never store your OAuth provider passwords</li>
          </ul>
          <p className="text-muted-foreground mt-4">
            Your data is stored on secure cloud infrastructure. We retain your data for as long
            as your account is active. You may delete your data at any time (see below).
          </p>
        </CardContent>
      </Card>

      {/* Third-Party Services */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-primary" />
            Third-Party Services
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">We use the following third-party services:</p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              <strong>Anthropic (Claude AI):</strong> Powers our AI coaching feature. Your
              conversation data is sent to Anthropic's API for processing.
            </li>
            <li>
              <strong>OAuth Providers:</strong> Google, Facebook, LinkedIn, and GitHub for
              authentication. Subject to their respective privacy policies.
            </li>
            <li>
              <strong>Google Cloud Platform:</strong> For infrastructure and hosting services.
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            Each third-party service has its own privacy policy governing their use of your data.
          </p>
        </CardContent>
      </Card>

      {/* Cookies */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cookie className="h-5 w-5 text-primary" />
            Cookies and Tracking
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">We use cookies and similar technologies for:</p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              <strong>Essential Cookies:</strong> Required for authentication and session
              management
            </li>
            <li>
              <strong>Preference Cookies:</strong> Remember your settings (e.g., theme preference)
            </li>
            <li>
              <strong>Analytics Cookies:</strong> Help us understand how the platform is used
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            You can control cookie preferences through your browser settings. Disabling essential
            cookies may affect platform functionality.
          </p>
        </CardContent>
      </Card>

      {/* Your Rights */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trash2 className="h-5 w-5 text-primary" />
            Your Rights
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">You have the right to:</p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>
              <strong>Access:</strong> Request a copy of the personal data we hold about you
            </li>
            <li>
              <strong>Correction:</strong> Request correction of inaccurate personal data
            </li>
            <li>
              <strong>Deletion:</strong> Request deletion of your account and all associated data
            </li>
            <li>
              <strong>Portability:</strong> Request your data in a machine-readable format
            </li>
            <li>
              <strong>Objection:</strong> Object to certain processing of your data
            </li>
            <li>
              <strong>Withdraw Consent:</strong> Withdraw consent for optional data processing
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            To exercise these rights, visit your{" "}
            <Link to="/settings" className="text-primary hover:underline">
              Account Settings
            </Link>{" "}
            or contact us at{" "}
            <a href="mailto:privacy@systemdesignplatform.com" className="text-primary hover:underline">
              privacy@systemdesignplatform.com
            </a>
          </p>
        </CardContent>
      </Card>

      {/* Data Deletion */}
      <Card className="border-destructive/30 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            Data Deletion
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            You can delete your account and all associated data at any time. When you delete
            your account:
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>Your user profile and account information will be permanently deleted</li>
            <li>All your submissions, diagrams, and designs will be removed</li>
            <li>Your chat history and AI coaching conversations will be deleted</li>
            <li>Test results and scores will be erased</li>
            <li>This action is irreversible</li>
          </ul>
          <p className="text-muted-foreground mt-4">
            To delete your account, go to{" "}
            <Link to="/settings" className="text-primary hover:underline">
              Account Settings
            </Link>{" "}
            and click "Delete Account".
          </p>
        </CardContent>
      </Card>

      {/* GDPR/CCPA */}
      <Card>
        <CardHeader>
          <CardTitle>Regional Privacy Rights</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">European Users (GDPR)</h4>
            <p className="text-muted-foreground text-sm">
              If you are located in the European Economic Area, you have additional rights under
              the General Data Protection Regulation (GDPR). We process your data based on
              legitimate interests for providing the service and your consent for optional
              features.
            </p>
          </div>
          <div>
            <h4 className="font-medium mb-2">California Residents (CCPA)</h4>
            <p className="text-muted-foreground text-sm">
              If you are a California resident, you have rights under the California Consumer
              Privacy Act (CCPA). We do not sell your personal information. You may request
              disclosure of the categories of personal information we collect and the purposes
              for which it is used.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Changes */}
      <Card>
        <CardHeader>
          <CardTitle>Changes to This Policy</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            We may update this Privacy Policy from time to time. We will notify you of
            significant changes by posting a notice on the platform or sending you an email.
            Your continued use of the platform after changes take effect constitutes acceptance
            of the updated policy.
          </p>
        </CardContent>
      </Card>

      {/* Contact */}
      <Card>
        <CardHeader>
          <CardTitle>Contact Us</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            If you have any questions about this Privacy Policy or our data practices, please
            contact us at{" "}
            <a href="mailto:privacy@systemdesignplatform.com" className="text-primary hover:underline">
              privacy@systemdesignplatform.com
            </a>
          </p>
        </CardContent>
      </Card>

      {/* Footer links */}
      <div className="flex justify-center gap-4 text-sm text-muted-foreground pb-8">
        <Link to="/terms" className="hover:text-primary hover:underline">
          Terms of Service
        </Link>
        <span>|</span>
        <Link to="/settings" className="hover:text-primary hover:underline">
          Account Settings
        </Link>
      </div>
    </div>
  )
}
