"use client";

import { useEffect, useState } from "react";
import { api, AdminUser } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const ROLES = ["Public", "Internal", "Confidential", "Restricted"];

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
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold font-display">User Management</h1>
        <p className="text-sm text-ink-muted mt-1">Review registrations and assign roles</p>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {/* Pending Approvals */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Pending Approval
            {pendingUsers.length > 0 && (
              <span className="ml-2 text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded-full">
                {pendingUsers.length}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {pendingUsers.length === 0 ? (
            <p className="text-sm text-ink-muted">No pending registrations</p>
          ) : (
            <div className="space-y-3">
              {pendingUsers.map((user) => (
                <UserRow
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
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active Users */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Active Users ({approvedUsers.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {approvedUsers.length === 0 ? (
            <p className="text-sm text-ink-muted">No active users</p>
          ) : (
            <div className="space-y-3">
              {approvedUsers.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  assigning={assigning}
                  onAssignRole={handleAssignRole}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Admin Users */}
      {adminUsers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Admins</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {adminUsers.map((user) => (
                <div key={user.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                  <div>
                    <p className="font-medium">{user.full_name}</p>
                    <p className="text-sm text-ink-muted">{user.email}</p>
                  </div>
                  <span className="text-xs bg-primary/20 text-primary px-2 py-1 rounded-full">Admin</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function UserRow({
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
    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2 border border-border">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium truncate">{user.full_name}</p>
          {!user.is_approved && (
            <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded-full">Pending</span>
          )}
        </div>
        <p className="text-sm text-ink-muted">{user.email}</p>
        <div className="flex items-center gap-3 mt-1 text-xs text-ink-muted">
          <span>{user.department}</span>
          {user.designation && (
            <>
              <span>·</span>
              <span className="text-primary">{user.designation}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 ml-4">
        {/* Role selector */}
        <select
          value={currentRole}
          onChange={(e) => onAssignRole(user.id, e.target.value)}
          disabled={assigning === user.id}
          className="rounded-md border border-input bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="None">No Role</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        {showApproval && (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onApprove(user.id)}
              className="text-green-400 border-green-400/30 hover:bg-green-400/10"
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onReject(user.id)}
              className="text-yellow-400 border-yellow-400/30 hover:bg-yellow-400/10"
            >
              Reject
            </Button>
          </>
        )}

        <Button
          size="sm"
          variant="outline"
          onClick={() => onDelete(user.id)}
          className="text-destructive border-destructive/30 hover:bg-destructive/10"
        >
          Delete
        </Button>
      </div>
    </div>
  );
}
