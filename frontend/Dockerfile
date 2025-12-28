# Frontend Dockerfile - Production Build
FROM node:20-alpine AS builder

WORKDIR /app

# Build argument for API URL (backend service)
ARG VITE_API_URL=https://sdp-backend-zziiwqh26q-uc.a.run.app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source code and build with API URL
COPY . .
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Production stage - use nginx to serve static files
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
