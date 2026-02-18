FROM trustsource/ts-deepscan
LABEL maintainer="Grigory Markin <gmn@eacg.de>"

RUN apt-get update && \
    apt-get install -y curl gpg

# Setup Microsoft repository with modern signing
RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list

# Install package managers: Maven, NPM, Gradle, .NET Core & Mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    maven \
    npm \
    gradle \
    dotnet-sdk-8.0 \
    mono-complete \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Syft
RUN curl -sSfL https://get.anchore.io/syft | sh -s -- -b /usr/local/bin

# Fetch NuGet and create a wrapper script disabling JIT, due to issues when running in emulation mode
RUN curl -fsSL -o /usr/local/bin/nuget.exe https://dist.nuget.org/win-x86-commandline/latest/nuget.exe \
    && printf '#!/bin/sh\nMONO_ENV_OPTIONS="--interp" exec mono /usr/local/bin/nuget.exe "$@"\n' > /usr/local/bin/nuget \
    && chmod +x /usr/local/bin/nuget

# Sync CA certificates with Mono
RUN MONO_ENV_OPTIONS="--interp" cert-sync /etc/ssl/certs/ca-certificates.crt


RUN mkdir -p /tmp/ts-scan
WORKDIR /tmp/ts-scan

COPY ./src ./src
COPY ./pyproject.toml ./LICENSE ./

RUN pip install ./

ENTRYPOINT ["ts-scan"]
CMD []