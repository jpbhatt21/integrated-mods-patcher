// API client for communicating with Flask backend

const API_BASE_URL = 'http://localhost:5000';

class ApiClient {
  private token: string | null = null;

  constructor() {
    // Try to load token from localStorage
    this.token = localStorage.getItem('auth_token');
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
  }

  private async makeRequest(endpoint: string, options: RequestInit = {}) {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.token) {
      headers['Authorization'] = `${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error(`API request failed: ${response.statusText}`);
    }

    return response.json();
  }

  async login(username: string, password: string) {
    try {
      const response = await this.makeRequest('/api/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });

      if (response.success) {
        this.setToken(response.token);
        return { success: true };
      } else {
        return { success: false, error: response.error };
      }
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : 'Login failed' };
    }
  }
  async stop(){
    return this.makeRequest(`/api/stop`);
  }
  async start(task: string, game: string,threads=4,sleep=2) {
    return this.makeRequest(`/api/start/${task}/${game}/${threads}/${sleep}`);
  }
  async status(){
    return this.makeRequest(`/api/status`);
  }
  async healthCheck() {
    try {
      const response = await this.makeRequest('/api/health');
      return response;
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  }
  async auth() {
    return this.makeRequest(`/api/auth`);
  }
  isAuthenticated() {
    return !!this.token;
  }
}

export const apiClient = new ApiClient();