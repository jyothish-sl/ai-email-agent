FROM node:20-alpine

WORKDIR /app

# Installed here so the image has node_modules baked in; the compose file's
# `- /app/node_modules` volume then keeps this directory from being shadowed
# by the host bind mount, while still bind-mounting your source for hot reload.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
