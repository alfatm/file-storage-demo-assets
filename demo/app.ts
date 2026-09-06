export interface FileEntry {
  path: string;
  name: string;
  size: number;
  isDir: boolean;
  modifiedAt: string;
  mime?: string;
}

export interface SearchOptions {
  path?: string;
  type?: "file" | "folder";
  limit?: number;
  content?: boolean;
}

export interface UploadOptions {
  overwrite?: boolean;
  onProgress?: (sent: number, total: number) => void;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly path?: string) {
    super(message);
    this.name = "ApiError";
  }
}

export class StorageClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string, private readonly token: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async listFolder(path = "/"): Promise<FileEntry[]> {
    const data = await this.request<{ entries: FileEntry[] }>("GET", `/files?path=${encodeURIComponent(path)}`);
    return data.entries;
  }

  async createFolder(path: string): Promise<FileEntry> {
    return this.request<FileEntry>("POST", "/folders", { path });
  }

  async uploadFile(path: string, file: Blob, options: UploadOptions = {}): Promise<FileEntry> {
    const form = new FormData();
    form.append("path", path);
    form.append("overwrite", String(options.overwrite ?? false));
    form.append("file", file);
    options.onProgress?.(0, file.size);
    const entry = await this.request<FileEntry>("POST", "/upload", form);
    options.onProgress?.(file.size, file.size);
    return entry;
  }

  async downloadFile(path: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/download?path=${encodeURIComponent(path)}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    if (!res.ok) throw new ApiError(res.status, `download failed: ${res.statusText}`, path);
    return res.blob();
  }

  async searchFiles(query: string, options: SearchOptions = {}): Promise<FileEntry[]> {
    const params = new URLSearchParams({ q: query, limit: String(options.limit ?? 50) });
    if (options.path) params.set("path", options.path);
    if (options.type) params.set("type", options.type);
    if (options.content) params.set("content", "1");
    const data = await this.request<{ results: FileEntry[] }>("GET", `/search?${params}`);
    return data.results;
  }

  async deleteFile(path: string): Promise<void> {
    await this.request<void>("DELETE", `/files?path=${encodeURIComponent(path)}`);
  }

  private async request<T>(method: string, url: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Authorization: `Bearer ${this.token}` };
    let payload: BodyInit | undefined;
    if (body instanceof FormData) {
      payload = body;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const res = await fetch(this.baseUrl + url, { method, headers, body: payload });
    if (res.status === 204) return undefined as T;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, data.error ?? res.statusText, data.path);
    return data as T;
  }
}

export function formatSize(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) value /= 1024, i += 1;
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
