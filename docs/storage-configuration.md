# Storage configuration: local, AWS S3 and Alibaba Cloud OSS

**Nothing needs uploading to a cloud account to develop or demonstrate C5.**
The default is private local files. AWS's object storage is called **S3**;
Alibaba Cloud's is **OSS**. Select one with `STORAGE_BACKEND` in `backend/.env`.

## Configuration reference

Environment values override `.env`. Start through `scripts/start.sh` so relative
paths resolve from `backend/`. Never commit keys or `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local`, `s3`, or `oss` |
| `STORAGE_LOCAL_ROOT` | `.data/objects` | Local object directory, relative to backend working directory |
| `STORAGE_BUCKET` | empty | Existing bucket name; required for cloud |
| `STORAGE_REGION` | empty | Required for S3; OSS region enables V4 signing, e.g. `ap-southeast-1` |
| `STORAGE_ENDPOINT` | empty | Leave empty for ordinary AWS S3; required HTTPS endpoint for OSS |
| `STORAGE_OSS_IS_CNAME` | `false` | Set `true` only when OSS endpoint is a bound custom domain |
| `STORAGE_PREFIX` | `c5` | Cloud object prefix; relative path without `.`/`..`/empty segments |
| `STORAGE_ACCESS_KEY_ID` | empty | Server-side key ID; optional for S3 default credential chain, required for OSS |
| `STORAGE_ACCESS_KEY_SECRET` | empty | Matching secret; always provide key ID and secret together |
| `STORAGE_SESSION_TOKEN` | empty | Optional temporary AWS session / Alibaba STS token with its matching key pair |
| `STORAGE_TIMEOUT_SECONDS` | `10` | SDK network timeout (1–120 seconds); not a total request deadline |
| `DOCUMENT_API_TOKEN` | empty | Shared integration bearer token; **required for cloud**, optional locally |
| `DOCUMENT_MAX_BYTES` | `10485760` | Upload limit, 10 MiB by default; maximum configurable value is 20 MiB |
| `DOCUMENT_MAX_PDF_PAGES` | `50` | Maximum PDF pages processed |
| `DOCUMENT_MAX_TEXT_CHARS` | `200000` | Maximum extracted text characters |
| `DOCUMENT_MAX_IMAGE_PIXELS` | `20000000` | Image/rendered-page pixel limit |
| `DOCUMENT_OCR_ENABLED` | `false` | Opt into Tesseract OCR |
| `DOCUMENT_OCR_LANGUAGE` | `eng` | Installed Tesseract language(s), e.g. `eng+chi_sim` |
| `DOCUMENT_OCR_TIMEOUT_SECONDS` | `20` | Per-image/per-page OCR timeout |
| `C5_PDF_FONT_PATH` | empty | Optional local TrueType font path for PDF rendering; font must cover needed glyphs |

`STORAGE_PREFIX` is included once by `DocumentService` in the canonical object
key. Document `storage_key` is an opaque application key; use the download API
rather than construct provider URLs.
`DATABASE_URL` and the LLM-related keys do not enable persistence or a live LLM in
this implementation. FakeLLM remains wired in `app/api/deps.py`.

## Local development

```dotenv
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=.data/objects
DOCUMENT_OCR_ENABLED=false
DOCUMENT_API_TOKEN=
```

No storage SDK, bucket, access key, or browser CORS policy is needed. Files live
under `backend/.data/objects`; metadata is in memory. See [safe reset](setup.md#state-lifetime-and-safe-reset).

## AWS S3

1. Create a dedicated general-purpose test bucket in the chosen region. Keep all
   S3 Block Public Access settings enabled; this service accesses private objects
   through the backend. [AWS public-access controls](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)
2. Use a restricted IAM identity for the application's bucket/prefix. An AWS
   role/default credential chain works when explicit key fields are empty; local
   temporary credentials can use all three `STORAGE_*` credential fields.
3. Install SDKs with `./scripts/setup.sh --cloud`.
4. Set the fields below in local `.env` and restart the backend.

```dotenv
STORAGE_BACKEND=s3
STORAGE_BUCKET=YOUR_PRIVATE_TEST_BUCKET
STORAGE_REGION=ap-southeast-2
STORAGE_ENDPOINT=
STORAGE_PREFIX=group9-dev
DOCUMENT_API_TOKEN=REPLACE_WITH_A_RANDOM_INTEGRATION_TOKEN
# Leave all three blank to use the AWS default credential chain.
STORAGE_ACCESS_KEY_ID=
STORAGE_ACCESS_KEY_SECRET=
STORAGE_SESSION_TOKEN=
```

Example IAM policy for this implementation (replace the bucket and prefix):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::YOUR_PRIVATE_TEST_BUCKET/group9-dev/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::YOUR_PRIVATE_TEST_BUCKET"
    }
  ]
}
```

The object permissions cover upload/download/deletion. The separate bucket-level
`s3:ListBucket` permission supports the explicit `HeadBucket` readiness check;
`HeadBucket` has no prefix argument. Application document listings use metadata,
not S3 enumeration. [AWS policy resource reference](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-policy-language-overview.html),
[AWS HeadBucket permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadBucket.html)

This application does not create buckets or alter ACLs. Extra permissions may be
needed for account-specific bucket encryption policies, such as customer-managed
KMS keys; configure those with the bucket owner. SDK timeout/retries are bounded,
but cloud reachability and identity policies must be verified in your account.

## Alibaba Cloud OSS

1. Create a private test bucket and a RAM user/role scoped to its test prefix.
2. Record its exact region and matching endpoint. Use a public HTTPS endpoint
   from a development laptop; internal endpoints are for the matching cloud
   network. Example below uses Singapore, not a mainland China bucket.
3. Install SDKs with `./scripts/setup.sh --cloud`.
4. Configure the following fields, add your RAM/STS credentials locally and
   restart the backend.

```dotenv
STORAGE_BACKEND=oss
STORAGE_BUCKET=YOUR_PRIVATE_TEST_BUCKET
STORAGE_REGION=ap-southeast-1
STORAGE_ENDPOINT=https://oss-ap-southeast-1.aliyuncs.com
STORAGE_OSS_IS_CNAME=false
STORAGE_PREFIX=group9-dev
STORAGE_ACCESS_KEY_ID=YOUR_RAM_ACCESS_KEY_ID
STORAGE_ACCESS_KEY_SECRET=YOUR_RAM_ACCESS_KEY_SECRET
STORAGE_SESSION_TOKEN=
DOCUMENT_API_TOKEN=REPLACE_WITH_A_RANDOM_INTEGRATION_TOKEN
```

Alibaba's current documentation says new OSS users from 20 March 2025 must use a
custom domain for affected data APIs on mainland China buckets. If applicable,
bind the domain/certificate as required, set `STORAGE_ENDPOINT=https://your-bound-domain`
and `STORAGE_OSS_IS_CNAME=true`. Region/account rules should be checked against
[OSS regions and endpoints](https://www.alibabacloud.com/help/en/oss/user-guide/regions-and-endpoints)
and [custom-domain setup](https://www.alibabacloud.com/help/en/oss/user-guide/access-buckets-via-custom-domain-names).
The code supports the CNAME flag; account-specific live access is not validated by
unit tests.

Example RAM policy (replace the bucket and prefix):

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["oss:PutObject", "oss:GetObject", "oss:DeleteObject"],
      "Resource": "acs:oss:*:*:YOUR_PRIVATE_TEST_BUCKET/group9-dev/*"
    },
    {
      "Effect": "Allow",
      "Action": "oss:GetBucketInfo",
      "Resource": "acs:oss:*:*:YOUR_PRIVATE_TEST_BUCKET"
    }
  ]
}
```

The second statement enables the explicit bucket-readiness check. Routine
list-document requests use application metadata and do not need `oss:ListObjects`.
The service does not need bucket creation or public-ACL permissions.
[OSS SDK permissions guide](https://www.alibabacloud.com/help/en/oss/user-guide/oss-sdk-quick-start),
[RAM policy examples](https://www.alibabacloud.com/help/en/oss/user-guide/ram-policy/)

## Access, verification and cleanup

Generate a local shared token, for example using
`backend/.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`,
and put it in `.env`. Clients send `Authorization: Bearer <token>` on document,
export, approval and document-health requests. This is a shared integration key,
**not patient authentication or session ownership enforcement**. Existing intake
and summary-retrieval routes remain unauthenticated. Keep the service on loopback
for synthetic integration; C3/C6 need real identity, ownership and durable records
before remote deployment.

The backend proxies uploads and downloads, so browsers need neither provider
SDKs nor storage access keys nor a bucket CORS policy. FastAPI's `FRONTEND_ORIGIN`
controls the browser-to-backend CORS boundary. Do not put storage secrets or the
shared integration token in a publicly shipped frontend bundle.

After deliberately configuring cloud access, call `/api/documents/health` with
the bearer token, then run the loopback live smoke command in [setup](setup.md).
It verifies read/write/delete using synthetic files and removes those objects.
Cloud SDK adapters are tested with fakes; no live bucket is created or checked by
normal pytest or offline smoke. A health success alone does not prove that
object-level write/delete permissions work.

Delete files through the API before stopping the process when possible. Restart
loses document metadata while remote objects remain; choose an owner-managed
lifecycle/cleanup policy for a dedicated synthetic test prefix. The local reset
script never deletes cloud data. In a versioned bucket, normal deletion may leave
older object versions; manage retained versions under the bucket's lifecycle
policy rather than assuming API deletion permanently erases every copy.
