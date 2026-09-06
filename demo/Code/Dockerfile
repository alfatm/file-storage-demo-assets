FROM node:22-alpine
WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
ENV NODE_ENV=production
ENV PORT=5212
ENV CLOUD_ROOT=/data

VOLUME ["/data"]
EXPOSE 5212

HEALTHCHECK --interval=30s CMD wget -qO- http://localhost:5212/healthz || exit 1
CMD ["npm", "run", "dev"]
