import { promises as fs } from "node:fs";
import { join } from "node:path";
import type { FileEntry } from "./storage";

export interface QueryOptions {
  path?: string;
  content?: boolean;
  limit: number;
}

interface IndexedFile {
  entry: FileEntry;
  text: string;
}

const TOKEN = /[\p{L}\p{N}]{2,}/gu;

export class SearchIndex {
  private readonly files = new Map<string, IndexedFile>();

  async add(entry: FileEntry, root: string): Promise<void> {
    if (entry.isDir) return;
    const text = await readSearchableText(root, entry);
    this.files.set(entry.path, { entry, text: `${entry.name}\n${text}`.toLowerCase() });
  }

  remove(path: string): void {
    this.files.delete(path);
  }

  query(q: string, opts: QueryOptions): FileEntry[] {
    const terms = tokenize(q);
    const hits: Array<{ entry: FileEntry; score: number }> = [];
    for (const file of this.files.values()) {
      if (opts.path && !file.entry.path.startsWith(opts.path)) continue;
      let score = 0;
      for (const term of terms) {
        if (file.entry.name.toLowerCase().includes(term)) score += 4;
        if (opts.content && file.text.includes(term)) score += 2;
      }
      if (score) hits.push({ entry: file.entry, score });
    }
    return hits.sort((a, b) => b.score - a.score).slice(0, opts.limit).map((hit) => hit.entry);
  }
}

function tokenize(text: string): string[] {
  return text.toLowerCase().match(TOKEN) ?? [];
}

async function readSearchableText(root: string, entry: FileEntry): Promise<string> {
  if (!/\.(md|txt|csv|json|ya?ml|html?|ts|py|go|css)$/i.test(entry.name)) return "";
  return fs.readFile(join(root, entry.path), "utf8").catch(() => "");
}
