const env = process.env;

export const config = {
  port: Number(env.PORT ?? 5212),
  root: env.CLOUD_ROOT ?? "../demo",
  apiToken: env.CLOUD_API_TOKEN ?? "demo-token",
  maxUploadBytes: Number(env.CLOUD_MAX_UPLOAD ?? 200 * 1024 * 1024),
  thumbnails: {
    sizes: [128, 256, 512],
    quality: Number(env.CLOUD_THUMBNAIL_QUALITY ?? 82),
  },
} as const;

export type Config = typeof config;
