# --- Build stage ---
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json ./
# Use install (no lockfile committed) so the image builds from scratch.
RUN npm install

COPY . .
RUN npm run build

# --- Serve stage ---
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/threat-dashboard/browser /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
