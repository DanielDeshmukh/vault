import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-background">
      <div className="z-10 max-w-5xl w-full items-center justify-center">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold mb-4 font-display tracking-tight">Vault</h1>
          <p className="text-xl text-ink-muted max-w-2xl mx-auto">
            Permission-Aware Enterprise Knowledge System
          </p>
        </div>

        <div className="flex gap-4 justify-center mb-16">
          <Link href="/login">
            <Button size="lg">Sign In</Button>
          </Link>
          <Link href="/register">
            <Button variant="secondary" size="lg">Create Account</Button>
          </Link>
        </div>

        <div className="grid text-center lg:grid-cols-3 gap-6 max-w-4xl mx-auto">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Permission-First</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Pre-retrieval filtering ensures unauthorized content never reaches the model.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Multi-Source</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Connect Zendesk, Jira, Slack, Confluence, and more.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Cited Answers</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Every answer includes source citations for verification.
              </CardDescription>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
