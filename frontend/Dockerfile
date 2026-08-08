FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY --chown=node:node . .
RUN npm run build
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
