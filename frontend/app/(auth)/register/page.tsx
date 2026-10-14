"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Roles an applicant may request. Excludes "admin" by design: that is granted
// by an existing admin only, and requesting one here would grant nothing.
const REQUESTABLE_ROLES = [
  { value: "intern", label: "Intern — general documents" },
  { value: "employee", label: "Employee — general, sales" },
  { value: "engineer", label: "Engineer — engineering, IT security" },
  { value: "manager", label: "Manager — sales, engineering, HR" },
  { value: "hr", label: "HR — human resources" },
  { value: "legal", label: "Legal — legal" },
  { value: "finance", label: "Finance — finance" },
];

export default function RegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    full_name: "",
    department: "",
    requested_role: "intern",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.register(formData);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <main className="min-h-screen flex bg-background">
      {/* Left panel - branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-surface-1 items-center justify-center p-12">
        <div className="max-w-md">
          <div className="mb-8">
            <span className="text-3xl font-bold font-display tracking-tight">Vault</span>
          </div>
          <h1 className="text-3xl font-bold font-display mb-4 text-foreground">
            Join your team<br />on Vault
          </h1>
          <p className="text-ink-muted leading-relaxed">
            Create an account and get access to your organization's knowledge base.
            An admin will review your request and assign appropriate permissions.
          </p>
          <div className="mt-8 space-y-3 text-sm text-ink-tertiary">
            <div className="flex items-center gap-3">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              Secure by design
            </div>
            <div className="flex items-center gap-3">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              Team collaboration
            </div>
            <div className="flex items-center gap-3">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              Admin-managed access
            </div>
          </div>
        </div>
      </div>

      {/* Right panel - form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-8">
            <span className="text-2xl font-bold font-display tracking-tight">Vault</span>
          </div>

          <h2 className="text-2xl font-bold font-display mb-1 text-foreground">Create account</h2>
          <p className="text-sm text-ink-muted mb-6">Join your team on Vault</p>

          <div className="p-3 rounded-lg bg-surface-2 border border-border text-sm text-ink-muted mb-6">
            Your account will be reviewed by an admin before you can access the system.
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="full_name" className="text-sm font-medium text-foreground">
                Full Name
              </label>
              <Input
                id="full_name"
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                required
                placeholder="John Doe"
                className="h-11"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-foreground">
                Email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                required
                placeholder="you@company.com"
                className="h-11"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label htmlFor="department" className="text-sm font-medium text-foreground">
                  Department
                </label>
                <Input
                  id="department"
                  name="department"
                  value={formData.department}
                  onChange={handleChange}
                  required
                  placeholder="Engineering"
                  className="h-11"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="requested_role" className="text-sm font-medium text-foreground">
                  Requested role
                </label>
                <select
                  id="requested_role"
                  name="requested_role"
                  value={formData.requested_role}
                  onChange={handleChange}
                  className="w-full h-11 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {REQUESTABLE_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-surface-2 border border-border text-xs text-ink-tertiary">
              Your choice is a request only. You start with public documents, and
              an admin grants your actual role after review.
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-foreground">
                Password
              </label>
              <Input
                id="password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                required
                placeholder="Enter password"
                minLength={8}
                className="h-11"
              />
            </div>

            <Button type="submit" className="w-full h-11" disabled={loading}>
              {loading ? "Creating account..." : "Create Account"}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-ink-muted">
            Already have an account?{" "}
            <Link href="/login" className="text-primary hover:text-primary-hover font-medium">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
