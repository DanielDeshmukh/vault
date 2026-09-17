"use client";

import { useEffect, useState } from "react";
import { api, AdminUser } from "@/lib/api";
import { Button } from "@/components/ui/button";

const ROLES = ["Public", "Internal", "Confidential", "Restricted"];

const ROLE_COLORS: Record<string, string> = {
  Public: "bg-surface-3 text-ink-muted",
  Internal: "bg-blue-500/15 text-blue-400",
  Confidential: "bg-amber-500/15 text-amber-400",
  Restricted: "bg-red-500/15 text-red-400",
};

function RoleBadge({ role }: { role: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ROLE_COLORS[role] || "bg-surface-3 text-ink-muted"}`}>
      {role}
    </span>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [assigning, setAssigning] = useState<string | null>(null);

  const loadUsers = async () => {
    try {
      const data = await api.adminListUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleAssignRole = async (userId: string, roleName: string) => {
    setAssigning(userId);
    try {
      await api.adminAssignRole(userId, roleName);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign role");
    } finally {
      setAssigning(null);
    }
  };

  const handleApprove = async (userId: string) => {
    try {
      await api.adminApproveUser(userId);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve user");
    }
  };

  const handleReject = async (userId: string) => {
    try {
      await api.adminRejectUser(userId);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject user");
    }
  };

  const handleDelete = async (userId: string) => {
    if (!confirm("Delete this user?")) return;
    try {
      await api.adminDeleteUser(userId);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete user");
    }
  };

  const pendingUsers = users.filter((u) => !u.is_admin && !u.is_approved);
  const approvedUsers = users.filter((u) => !u.is_admin && u.is_approved);
  const adminUsers = users.filter((u) => u.is_admin);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-ink-muted">
        Loading users...
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl md:text-2xl font-bold font-display">User Management</h1>
        <p className="text-sm text-ink-muted mt-1">Review registrations and assign roles</p>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {/* Pending Approvals */}
      <Section
        title="Pending Approval"
        count={pendingUsers.length}
        countColor="bg-yellow-500/15 text-yellow-400"
        empty="No pending registrations"
      >
        {pendingUsers.map((user) => (
          <UserCard
            key={user.id}
            user={user}
            assigning={assigning}
            onAssignRole={handleAssignRole}
            onApprove={handleApprove}
            onReject={handleReject}
            onDelete={handleDelete}
            showApproval
          />
        ))}
      </Section>

      {/* Active Users */}
      <Section
        title="Active Users"
        count={approvedUsers.length}
        empty="No active users"
      >
        {approvedUsers.map((user) => (
          <UserCard
            key={user.id}
            user={user}
            assigning={assigning}
            onAssignRole={handleAssignRole}
            onApprove={handleApprove}
            onReject={handleReject}
            onDelete={handleDelete}
          />
        ))}
      </Section>

      {/* Admins */}
      {adminUsers.length > 0 && (
        <Section title="Admins" count={adminUsers.length} empty="No admins">
          {adminUsers.map((user) => (
            <div key={user.id} className="flex items-center gap-3 p-3 rounded-lg bg-surface-2 border border-border">
              <Avatar name={user.full_name} />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{user.full_name}</p>
                <p className="text-xs text-ink-muted truncate">{user.email}</p>
              </div>
              <span className="text-xs bg-primary/15 text-primary px-2 py-0.5 rounded font-medium">Admin</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  countColor,
  empty,
  children,
}: {
  title: string;
  count: number;
  countColor?: string;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-1 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold">{title}</h2>
        {count > 0 && (
          <span className={`text-xs px-1.5 py-0.5 rounded ${countColor || "bg-surface-3 text-ink-muted"}`}>
            {count}
          </span>
        )}
      </div>
      <div className="p-4 space-y-2">
        {count === 0 ? (
          <p className="text-sm text-ink-muted">{empty}</p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  return (
    <div className="w-9 h-9 rounded-full bg-surface-3 flex items-center justify-center text-xs font-medium text-ink-muted flex-shrink-0">
      {initials}
    </div>
  );
}

function UserCard({
  user,
  assigning,
  onAssignRole,
  onApprove,
  onReject,
  onDelete,
  showApproval = false,
}: {
  user: AdminUser;
  assigning: string | null;
  onAssignRole: (userId: string, role: string) => void;
  onApprove: (userId: string) => void;
  onReject: (userId: string) => void;
  onDelete: (userId: string) => void;
  showApproval?: boolean;
}) {
  const currentRole = user.roles[0] || "None";

  return (
    <div className="rounded-lg bg-surface-2 border border-border p-3 md:p-4">
      {/* Top row: avatar + info + role badge */}
      <div className="flex items-start gap-3">
        <Avatar name={user.full_name} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium truncate text-sm">{user.full_name}</p>
            {!user.is_approved && (
              <span className="text-xs bg-yellow-500/15 text-yellow-400 px-1.5 py-0.5 rounded">Pending</span>
            )}
            {currentRole !== "None" && <RoleBadge role={currentRole} />}
          </div>
          <p className="text-xs text-ink-muted truncate">{user.email}</p>
          <div className="flex items-center gap-2 mt-1 text-xs text-ink-tertiary">
            <span>{user.department}</span>
            {user.designation && (
              <>
                <span className="text-border">|</span>
                <span>{user.designation}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Bottom row: controls */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50 flex-wrap">
        <select
          value={currentRole}
          onChange={(e) => onAssignRole(user.id, e.target.value)}
          disabled={assigning === user.id}
          className="rounded-md border border-input bg-background px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring min-w-0 flex-1 sm:flex-none sm:w-auto"
        >
          <option value="None">No Role</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        <div className="flex items-center gap-1.5 ml-auto">
          {showApproval && (
            <>
              <Button size="sm" variant="outline" onClick={() => onApprove(user.id)} className="text-green-400 border-green-400/30 hover:bg-green-400/10 h-7 text-xs px-2">
                Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => onReject(user.id)} className="text-yellow-400 border-yellow-400/30 hover:bg-yellow-400/10 h-7 text-xs px-2">
                Reject
              </Button>
            </>
          )}
          <Button size="sm" variant="outline" onClick={() => onDelete(user.id)} className="text-destructive border-destructive/30 hover:bg-destructive/10 h-7 text-xs px-2">
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
