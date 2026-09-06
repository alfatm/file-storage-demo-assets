import { createHash, timingSafeEqual } from "node:crypto";
import type { NextFunction, Request, Response } from "express";
import { config } from "./config";

export interface AuthenticatedRequest extends Request {
  userId: string;
}

export function authenticate(req: Request, res: Response, next: NextFunction): void {
  const header = req.headers.authorization ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";

  if (!sameToken(token, config.apiToken)) {
    res.status(401).json({ error: "invalid API token" });
    return;
  }

  (req as AuthenticatedRequest).userId = "demo-user";
  next();
}

function sameToken(a: string, b: string): boolean {
  const left = Buffer.from(hash(a));
  const right = Buffer.from(hash(b));
  return left.length === right.length && timingSafeEqual(left, right);
}

function hash(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}
