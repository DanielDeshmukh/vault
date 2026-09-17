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
    const response = await this.request<{ access_token: string; user: User }>("/api/backend/auth/register", {
      method: "POST",
      body: data,
    });
    this.setToken(response.access_token);
    return response;
  }

  async login(data: { email: string; password: string }) {
    const response = await this.request<{ access_token: string; user: User }>("/api/backend/auth/login", {
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
    return this.request<User>("/api/backend/auth/me");
  }

  logout() {
    this.setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("vault_user");
    }
  }

  // Admin endpoints
  async adminListUsers() {
    return this.request<AdminUser[]>("/api/backend/admin/users");
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
    return this.request<{ name: string; access_level: number; description: string }[]>("/api/backend/admin/roles");
  }

  // Query endpoints
  async query(question: string, context?: string) {
    return this.request<QueryResponse>("/api/backend/query", {
      method: "POST",
      body: { question, context },
    });
  }

  // Document endpoints
  async listDocuments() {
    return this.request<Document[]>("/api/backend/documents");
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

export interface Document {
  id: string;
  title: string;
  source: string;
  account_id?: string;
  department?: string;
  access_level: number;
}

export const api = new ApiClient(API_URL);
