FROM nodered/node-red:4.1.5

USER root
WORKDIR /opt/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN chown -R node-red:node-red /opt/dashboard

USER node-red
RUN npm ci --omit=dev \
    && mkdir -p public/vendor/leaflet \
    && cp -R node_modules/leaflet/dist/. public/vendor/leaflet/ \
    && cp node_modules/leaflet/LICENSE public/vendor/leaflet/LICENSE

COPY --chown=node-red:node-red dashboard/public/ public/

WORKDIR /usr/src/node-red
