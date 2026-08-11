# Static UI for the YOLO predictor.
#   docker build -f frontend/Dockerfile -t simonangelfong/kubeflow-yolo-ui:v0.1.1 .
#
# Nginx serves the page and proxies /v1/ to the predictor, so the browser only
# ever talks to one origin and CORS never applies.

FROM nginx:1.27-alpine

# Rendered into conf.d/default.conf at container start with PREDICTOR_UPSTREAM
# substituted, so the same image serves compose and the cluster.
COPY frontend/app/nginx.conf.template /etc/nginx/templates/default.conf.template

# index.html references css/ and js/ relatively, so copy the tree as-is.
# The template rides along in app/; drop it rather than serve it to the browser.
COPY frontend/app/ /usr/share/nginx/html/
RUN rm /usr/share/nginx/html/nginx.conf.template

# Compose default; the cluster manifest points this at the predictor Service.
ENV PREDICTOR_UPSTREAM=inference:8080

# 8080 so the container can run as non-root under PSS restricted.
EXPOSE 8080
