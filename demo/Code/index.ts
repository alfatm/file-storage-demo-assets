import express from "express";
import { api } from "./api";
import { config } from "./config";

const app = express();

app.use(express.json());
app.use("/api", api);
app.use(express.static("public"));

app.get("/healthz", (_req, res) => {
  res.json({ ok: true, root: config.root });
});

app.listen(config.port, () => {
  console.log(`cloud demo service listening on http://localhost:${config.port}`);
});
