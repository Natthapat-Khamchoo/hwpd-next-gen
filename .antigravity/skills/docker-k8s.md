# 6.1 Docker & Kubernetes Skill
Multi-stage builds & K8s Deployments

### Code Pattern
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
FROM node:20-alpine AS runtime
COPY --from=builder /app/node_modules ./node_modules
COPY . .
CMD ["node", "server.js"]
```