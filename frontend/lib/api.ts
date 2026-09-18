const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("vault_token", token);
    } else {
      localStorage.removeItem("vault_token");
    }
  }

  getToken(): string | null {
    if (typeof window !== "undefined") {
      return this.token || localStorage.getItem("vault_token");
    }
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, headers = {} } = options;
    
    const token = this.getToken();
    const requestHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      ...headers,
    };

    if (token) {
      requestHeaders["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers: requestHeaders,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An error occurred" }));
      throw new Error(error.detail || "An error occurred");
    }

    return response.json();
  }

  // Auth endpoints
  async register(data: { email: string; password: string; full_name: string; department: string; designation: string }) {
    const response = await this.request<{ access_token: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: data,
    });
    this.setToken(response.access_token);
    return response;
  }

  async login(data: { email: string; password: string }) {
    const response = await this.request<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: data,
    });
    this.setToken(response.access_token);
    if (typeof window !== "undefined") {
      localStorage.setItem("vault_user", JSON.stringify(response.user));
    }
    return response;
  }

  async getMe() {
    return this.request<User>("/api/auth/me");
  }

  logout() {
    this.setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("vault_user");
    }
  }

  // Admin endpoints
  async adminListUsers() {
    return this.request<AdminUser[]>("/api/admin/users");
  }

  async adminAssignRole(userId: string, roleName: string) {
    return this.request(`/api/admin/users/${userId}/role`, {
      method: "PUT",
      body: { role_name: roleName },
    });
  }

  async adminApproveUser(userId: string) {
    return this.request(`/api/admin/users/${userId}/approve`, { method: "PUT" });
  }

  async adminRejectUser(userId: string) {
    return this.request(`/api/admin/users/${userId}/reject`, { method: "PUT" });
  }

  async adminDeleteUser(userId: string) {
    return this.request(`/api/admin/users/${userId}`, { method: "DELETE" });
  }

  async adminListRoles() {
    return this.request<{ name: string; access_level: number; description: string }[]>("/api/admin/roles");
  }

  // Query endpoints
  async query(question: string, context?: string) {
    return this.request<QueryResponse>("/api/query", {
      method: "POST",
      body: { question, context },
    });
  }

  async *queryStream(question: string): AsyncGenerator<StreamEvent, void, unknown> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/api/query/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An error occurred" }));
      throw new Error(error.detail || "An error occurred");
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6));
            yield event as StreamEvent;
          } catch {}
        }
      }
    }
  }

  // Document endpoints
  async listDocuments() {
    return this.request<Document[]>("/api/documents");
  }

  async getDocument(id: string) {
    return this.request<Document>(`/api/documents/${id}`);
  }

  async deleteDocument(id: string) {
    return this.request(`/api/documents/${id}`, { method: "DELETE" });
  }
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  department: string;
  designation?: string;
  is_admin: boolean;
  is_approved?: boolean;
}

export interface AdminUser extends User {
  roles: string[];
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  trace_id: string;
}

export interface Citation {
  document_id: string;
  title: string;
  source: string;
  score: number;
}

export type StreamEvent =
  | { type: "sources"; sources: Citation[] }
  | { type: "delta"; content: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "done"; trace_id: string }
  | { type: "error"; detail: string };

export interface Document {
  id: string;
  title: string;
  source: string;
  account_id?: string;
  department?: string;
  access_level: number;
  content?: string;
  can_access?: boolean;
}

export const api = new ApiClient(API_URL);
