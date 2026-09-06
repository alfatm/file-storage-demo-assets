import { createReadStream, createWriteStream, promises as fs } from "node:fs";
import { basename, dirname, join, resolve, sep } from "node:path";

export interface FileEntry {
  path: string;
  name: string;
  size: number;
  isDir: boolean;
  modifiedAt: string;
  mime: string;
}

export class LocalStorage {
  constructor(private readonly root: string) {}

  async list(path = "/"): Promise<FileEntry[]> {
    const dir = this.resolvePath(path);
    const names = await fs.readdir(dir);
    const entries = await Promise.all(names.map((name) => this.entryFor(join(dir, name), join(path, name))));
    return entries.sort((a, b) => Number(b.isDir) - Number(a.isDir) || a.name.localeCompare(b.name));
  }

  async createFolder(path: string): Promise<FileEntry> {
    const abs = this.resolvePath(path);
    await fs.mkdir(abs, { recursive: true });
    return this.entryFor(abs, path);
  }

  async read(path: string) {
    const abs = this.resolvePath(path);
    const stat = await fs.stat(abs);
    return { stream: createReadStream(abs), size: stat.size, mime: mimeFor(path) };
  }

  async write(path: string, stream: NodeJS.ReadableStream, overwrite = false): Promise<FileEntry> {
    const abs = this.resolvePath(path);
    await fs.mkdir(dirname(abs), { recursive: true });
    if (!overwrite && (await exists(abs))) throw new Error(`file already exists: ${path}`);
    await new Promise<void>((resolveWrite, reject) => {
      stream.pipe(createWriteStream(abs)).on("finish", resolveWrite).on("error", reject);
    });
    return this.entryFor(abs, path);
  }

  async remove(path: string): Promise<void> {
    await fs.rm(this.resolvePath(path), { force: true, recursive: true });
  }

  private resolvePath(path: string): string {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    const full = resolve(this.root, "." + normalized);
    const root = resolve(this.root);
    if (full !== root && !full.startsWith(root + sep)) throw new Error("path escapes storage root");
    return full;
  }

  private async entryFor(abs: string, displayPath: string): Promise<FileEntry> {
    const stat = await fs.stat(abs);
    return {
      path: displayPath.replaceAll("\\", "/"),
      name: basename(displayPath),
      size: stat.isDirectory() ? 0 : stat.size,
      isDir: stat.isDirectory(),
      modifiedAt: stat.mtime.toISOString(),
      mime: stat.isDirectory() ? "inode/directory" : mimeFor(displayPath),
    };
  }
}

async function exists(path: string): Promise<boolean> {
  return fs.access(path).then(() => true, () => false);
}

function mimeFor(path: string): string {
  const ext = path.toLowerCase().split(".").pop();
  const types: Record<string, string> = {
    csv: "text/csv",
    gif: "image/gif",
    html: "text/html",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    json: "application/json",
    md: "text/markdown",
    mp4: "video/mp4",
    pdf: "application/pdf",
    png: "image/png",
    svg: "image/svg+xml",
    txt: "text/plain",
    webp: "image/webp",
  };
  return types[ext ?? ""] ?? "application/octet-stream";
}
