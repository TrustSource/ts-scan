# Use Case #04 - Fail a Pipeline on Upload Failures

When you upload a scan to TrustSource with `ts-scan upload`, the command **exits
with code `0` even if the transfer fails**. This is intentional: an upload is
usually one of the last steps in a CI/CD pipeline, and a temporary platform
hiccup, a network glitch or a misconfigured endpoint should not necessarily break
an otherwise green build. Treating every upload problem as a hard failure would
make pipelines flaky for reasons outside the developer's control.

However, there are situations where you *do* want the opposite — where a missing
SBOM in TrustSource is a compliance gap that must stop the pipeline. This use case
shows how to react to a failed transfer.

## Why you would want to do this?

If your release process relies on every published artefact having an up-to-date
SBOM in TrustSource (for example to gate a deployment on a successful compliance
declaration), a silently failed upload would leave you with a false sense of
safety: the pipeline is green, but the SBOM never arrived.

## How an upload failure looks

On a failed transfer `ts-scan upload` prints a marker to the console but still
returns `0`:

```text
ℹ Uploading dependencies scan...
✘ Transfer failed
Missing Authentication Token
```

> [!NOTE]
>
> `Missing Authentication Token` is the response AWS API Gateway returns for an
> **unknown route** — it does not necessarily mean the API key is missing. The
> most common cause is a wrong `--base-url`. `ts-scan` appends the version and
> resource path itself (it posts to `<base-url>/v2/core/scans`), so the base URL
> must be the host only, e.g. `https://api.trustsource.io` — **not**
> `https://api.trustsource.io/v2`. Adding the version yields `/v2/v2/...` and the
> gateway rejects it.

## Steps to Success

Because the exit code stays `0` by design, capture the command output and inspect
it for the failure marker, then exit explicitly. Use `pipefail` so a failure in
`ts-scan` itself is still caught:

```shell
set -o pipefail

ts-scan upload \
  --base-url https://api.trustsource.io \
  --api-key "$TS_API_KEY" \
  --project-name "YOUR_PROJECT" \
  -f ts \
  scan.json 2>&1 | tee upload.log

# ts-scan upload exits 0 even when the transfer fails — fail explicitly.
if grep -qiE "Transfer failed|Missing Authentication" upload.log; then
  echo "TrustSource upload failed" >&2
  exit 1
fi
```

The same pattern works in any CI system. As a GitHub Actions step:

```yaml
- name: Upload SBOM to TrustSource
  run: |
    set -o pipefail
    ts-scan upload \
      --base-url "$TS_API_BASE_URL" \
      --api-key "$TS_API_KEY" \
      --project-name "$TS_PROJECT_NAME" \
      -f ts \
      scan.json 2>&1 | tee upload.log
    if grep -qiE "Transfer failed|Missing Authentication" upload.log; then
      echo "::error::TrustSource upload failed"
      exit 1
    fi
  env:
    TS_API_BASE_URL: https://api.trustsource.io
    TS_API_KEY: ${{ secrets.TS_API_KEY }}
    TS_PROJECT_NAME: YOUR_PROJECT
```

> [!NOTE]
>
> Please note the `TS_API_KEY`. This requires a TrustSource API key. See the
> [online help](https://support.trustsource.io/hc/en-us/articles/8624792507922-How-to-manage-API-keys)
> to learn how to create one. We recommend not to store the API key in the config.
> Use [github secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
> or a [local vault](https://github.com/mylofi/local-vault) to keep the key secret.

## Further Considerations

Keep the upload tolerant by default and only make it strict where a missing SBOM
is a real compliance gap — for example on release branches or before a deployment
gate, not on every feature-branch push. That way transient platform issues do not
turn every developer's build red, while your governed releases still guarantee a
successful declaration.

Given you are using TrustSource as a standalone version, you may need to point
`--base-url` at your own endpoint instead of the public one.
