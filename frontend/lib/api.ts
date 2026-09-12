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
  async register(data: { email: string; password: string; full_name: string; department: string }) {
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
    return response;
  }

  async getMe() {
    return this.request<User>("/api/auth/me");
  }

  logout() {
    this.setToken(null);
  }

  // Query endpoints
  async query(question: string, context?: string) {
    return this.request<QueryResponse>("/api/query/", {
      method: "POST",
      body: { question, context },
    });
  }

  // Document endpoints
  async listDocuments() {
    return this.request<Document[]>("/api/documents/");
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
  is_admin: boolean;
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
