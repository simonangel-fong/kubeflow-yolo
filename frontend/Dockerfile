# Static UI for the YOLO predictor.
#   docker build -f frontend/Dockerfile -t simonangelfong/kubeflow-yolo-frontend:v0.1.0 .
#
# Nginx serves the page and proxies /v1/ to the inference container, so the
# browser only ever talks to one origin.

FROM nginx:1.27-alpine

COPY frontend/app/nginx.conf /etc/nginx/conf.d/default.conf

# index.html references css/ and js/ relatively, so copy the tree as-is.
# nginx.conf rides along in app/; drop it rather than serve it to the browser.
COPY frontend/app/ /usr/share/nginx/html/
RUN rm /usr/share/nginx/html/nginx.conf

EXPOSE 80
