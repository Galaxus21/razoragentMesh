FROM node:22-alpine
WORKDIR /app
COPY package*.json tsconfig.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 4001
CMD ["node", "dist/mcpServerMain.js"]
