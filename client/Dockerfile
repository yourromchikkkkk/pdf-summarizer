# Stage 1: Build the React Application
FROM node:20-alpine AS build

WORKDIR /app

# Copy package descriptors and lockfile (if present)
COPY package*.json ./
RUN npm ci

# Copy the rest of the application
COPY . .

# Build the app to target folder (dist)
RUN npm run build

# Stage 2: Serve the application using Nginx
FROM nginx:alpine

# Copy built files from build stage to Nginx directory
COPY --from=build /app/dist /usr/share/nginx/html

# Copy our custom Nginx config for routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
