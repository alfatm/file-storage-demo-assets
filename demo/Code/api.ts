import { Readable } from "node:stream";
import { Router } from "express";
import multer from "multer";
import { authenticate } from "./auth";
import { config } from "./config";
import { SearchIndex } from "./search";
import { LocalStorage } from "./storage";

export const api = Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: config.maxUploadBytes } });
const storage = new LocalStorage(config.root);
const search = new SearchIndex();

api.use(authenticate);

api.get("/files", async (req, res) => {
  try {
    res.json({ entries: await storage.list(String(req.query.path ?? "/")) });
  } catch (error) {
    res.status(404).json({ error: String(error) });
  }
});

api.post("/folders", async (req, res) => {
  res.status(201).json(await storage.createFolder(String(req.body.path)));
});

api.post("/upload", upload.single("file"), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ error: "file is required" });
    return;
  }
  const path = String(req.body.path ?? `/${req.file.originalname}`);
  const entry = await storage.write(path, Readable.from(req.file.buffer), req.body.overwrite === "true");
  await search.add(entry, config.root);
  res.status(201).json(entry);
});

api.get("/download", async (req, res) => {
  const file = await storage.read(String(req.query.path));
  res.setHeader("Content-Length", file.size);
  res.setHeader("Content-Type", file.mime);
  file.stream.pipe(res);
});

api.get("/search", async (req, res) => {
  const results = search.query(String(req.query.q ?? ""), {
    path: req.query.path ? String(req.query.path) : undefined,
    content: req.query.content === "1",
    limit: Number(req.query.limit ?? 50),
  });
  res.json({ results });
});

api.delete("/files", async (req, res) => {
  const path = String(req.query.path);
  await storage.remove(path);
  search.remove(path);
  res.status(204).end();
});
