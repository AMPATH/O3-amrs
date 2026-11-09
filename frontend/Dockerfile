# syntax=docker/dockerfile:1.3
#--------------------------------------------
# Dev Stage - Assembles and Builds Frontend
#--------------------------------------------
FROM --platform=$BUILDPLATFORM node:22-alpine as dev

ARG APP_SHELL_VERSION=latest

RUN mkdir -p /app
WORKDIR /app

COPY spa-assemble-config.json .
COPY spa-build-config.json .

ARG CACHE_BUST
RUN mkdir -p configuration
COPY ./configuration/*.json configuration
RUN npx --legacy-peer-deps openmrs@${APP_SHELL_VERSION:-latest} assemble --manifest --mode config --config spa-assemble-config.json --config-file configuration/*.json --target ./spa
RUN npx --legacy-peer-deps openmrs@${APP_SHELL_VERSION:-latest} build --build-config spa-build-config.json --target ./spa
# Workaround for a build-toolchain regression (rspack CSS minifier used by the
# openmrs CLI): CSS-module selectors ending in '=' / '==' get over-escaped to
# \\\= instead of \= , producing dead selectors (844 broken rules in the
# top-level app CSS at the time of writing). That silently breaks styling of
# hashed-class components (e.g. the login location picker). Normalize the
# escaping in every built stylesheet; no-op once upstream is fixed.
RUN find ./spa -name '*.css' -exec sed -i 's/\\\\\\/\\/g' {} + \
  && find ./spa -name '*.css.gz' -delete \
  && find ./spa -name '*.css.br' -delete
RUN if [ ! -f ./spa/index.html ]; then echo 'Build failed. Please check the logs above for details. This may have happened because of an update to a library that OpenMRS depends on.'; ls -al ./spa; exit 1; fi

#--------------------------------------------
# Runtime Stage - Published Image
#--------------------------------------------
FROM nginx:1.25-alpine

RUN apk update && \
    apk upgrade && \
    # add more utils for sponge and envsubst
    apk add --no-cache moreutils
RUN apk add --no-cache tzdata
ENV TZ=Africa/Nairobi
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
# clear any default files installed by nginx
RUN rm -rf /usr/share/nginx/html/*

COPY startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh

COPY nginx.conf /etc/nginx/nginx.conf

COPY --from=dev /app/spa /usr/share/nginx/html
COPY *.json /usr/share/nginx/html
COPY ./assets /usr/share/nginx/html

CMD ["/usr/local/bin/startup.sh"]