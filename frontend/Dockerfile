# syntax=docker/dockerfile:1.3
#--------------------------------------------
# Dev Stage - Assembles and Builds Frontend
#--------------------------------------------
FROM --platform=$BUILDPLATFORM node:22-alpine as dev

ARG APP_SHELL_VERSION=next
# Root-cause pin for the CSS escaping regression: postcss-selector-parser
# 7.2.0 (published 2026-11-08) adds one extra backslash when re-serializing
# CSS-module class names whose hashes end in '+' / '=', producing dead
# selectors (.class\\\+ instead of .class\+) and broken styling. 7.1.8 is
# the last known-good release; drop this override once the css-loader ->
# postcss-modules chain ships a release that handles 7.2.x correctly.
ARG POSTCSS_SELECTOR_PARSER_VERSION=7.1.8

RUN mkdir -p /app
WORKDIR /app

COPY spa-assemble-config.json .
COPY spa-build-config.json .

ARG CACHE_BUST
RUN mkdir -p configuration
COPY ./configuration/*.json configuration
# Install the CLI locally (instead of npx) so the npm override reliably
# pins the transitive postcss-selector-parser version used by the build.
RUN printf '{"name":"frontend-build","private":true,"dependencies":{"openmrs":"%s"},"overrides":{"postcss-selector-parser":"%s"}}\n' "${APP_SHELL_VERSION}" "${POSTCSS_SELECTOR_PARSER_VERSION}" > package.json \
  && npm install --legacy-peer-deps --no-audit --no-fund
RUN ./node_modules/.bin/openmrs assemble --manifest --mode config --config spa-assemble-config.json --config-file configuration/*.json --target ./spa
RUN ./node_modules/.bin/openmrs build --build-config spa-build-config.json --target ./spa
# Guardrail (no-op while the override above is in effect): normalize any
# over-escaped selector backslashes in the built stylesheets and drop the
# stale precompressed variants.
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