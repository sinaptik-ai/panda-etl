# Use Node.js as the base image
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package.json and install dependencies
COPY package.json package-lock.json ./
RUN npm install --frozen-lockfile

# Copy the entire frontend code
COPY . .

# Build Next.js application
RUN npm run build

# Use a minimal base image for production
FROM node:18-alpine

WORKDIR /app

# Copy built files from builder
COPY --from=builder /app ./

# Expose frontend port
EXPOSE 3000

# Start Next.js
CMD ["npm", "run", "start"]
