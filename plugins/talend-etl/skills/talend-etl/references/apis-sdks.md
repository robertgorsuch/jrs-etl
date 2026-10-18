# Talend APIs and SDKs: TMC API, TAC MetaServlet, CommandLine, Component Kit, javajet, run-from-Java, other REST surfaces

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Evidence notes specific to this file: the Talend Component Kit section was checked against the real jars
`org.talend.sdk.component:component-api:1.95.3`, `talend-component-maven-plugin:1.95.3` (plugin.xml),
`component-runtime-junit:1.95.3`, `component-runtime-manager:1.95.3` and `component-tools:1.95.3`
downloaded from Maven Central (class lists, `javap` signatures, CLI usage strings). The TMC API, MetaServlet
and CommandLine sections rest on help.qlik.com / talend.qlik.dev search snippets plus memory; exact JSON field
names there are the most likely to drift, so confirm them in the Swagger UI of your region before scripting.

## Contents
- [1. Talend Cloud Management Console (TMC) public API](#1-talend-cloud-management-console-tmc-public-api)
  - [1.1 Hosts, versions, documentation](#11-hosts-versions-documentation)
  - [1.2 Authentication](#12-authentication)
  - [1.3 Resource catalog](#13-resource-catalog)
  - [1.4 Task run-config and triggers](#14-task-run-config-and-triggers)
  - [1.5 Executions and status polling](#15-executions-and-status-polling)
  - [1.6 Pagination, errors, limits](#16-pagination-errors-limits)
  - [1.7 curl cookbook](#17-curl-cookbook)
  - [1.8 Webhooks, API Tester CLI](#18-webhooks-api-tester-cli)
- [2. TAC MetaServlet API](#2-tac-metaservlet-api)
- [3. Studio CommandLine](#3-studio-commandline)
- [4. Talend Component Kit (TCK) SDK](#4-talend-component-kit-tck-sdk)
- [5. Legacy javajet components](#5-legacy-javajet-components)
- [6. Running exported Jobs from Java](#6-running-exported-jobs-from-java)
- [7. Other product APIs](#7-other-product-apis)
- [8. Routines, beans and generated-code API](#8-routines-beans-and-generated-code-api)
- [Gotchas](#gotchas)
- [Sources](#sources)

---

## 1. Talend Cloud Management Console (TMC) public API

### 1.1 Hosts, versions, documentation

| Item | Value | Notes |
|---|---|---|
| Regional API host | `https://api.<region>.cloud.talend.com` | `<region>` = `us`, `eu`, `ap`, `au`, `us-west`. Legacy `https://api.cloud.talend.com` = US. Mixing region and tenant gives 401, not 404. |
| Legacy versioned prefix | `/tmc/v2.6/...` | "Talend Management Console API" numbered releases. v1.0-v1.3 (2018-2019, `/tmc/v1.x/tasks`), v2.0 (R2020-02: `/tasks` moved to `/executables/tasks`), v2.1, v2.2, v2.3, v2.4, v2.5, v2.6 (2021-2022). Release notes state v2.0 and v2.1 deprecated with 18-month removal. Anything older than the current minor is best treated as removable. |
| Current family prefixes (unversioned paths) | `/orchestration/...`, `/processing/...`, `/monitoring/...`, `/account/...`, `/security/...` | Documented on `https://talend.qlik.dev/apis/<family>/2021-03/` as date-versioned API families: Orchestration (tasks, plans, schedules, workspaces, promotions, artifacts, connections), Processing (executions, runtimes/engines), Execution History Search, Service Accounts, OAuth, IAM. `/orchestration/executables/tasks` and `/tmc/v2.6/executables/tasks` address the same objects. |
| Swagger UI (legacy) | `https://api.<region>.cloud.talend.com/tmc/swagger/swagger-ui.html` | Quoted in R2020/R2021 release notes. |
| API docs portal | `https://api.<region>.cloud.talend.com/apis/#!/` | Interactive portal, lists all families; same content as `talend.qlik.dev/apis/`. |
| Content type | `application/json` both ways | Multipart only on the (older) artifact upload endpoint (unverified). |

### 1.2 Authentication

| Mechanism | How | Lifetime / limits |
|---|---|---|
| Personal access token (PAT) | TMC > user menu > Profile preferences > Personal access tokens > Generate. Send `Authorization: Bearer <token>`. | Shown once. Max 5 active tokens per user. No documented expiry; permissions follow the owner's current roles (change roles -> token rights change). Deleting the user kills the token. |
| Service account (recommended for automation) | TMC > Users and security > Service accounts: create, assign roles, copy ID + secret (secret shown once). Exchange for a short-lived token: | Token expires after 30 minutes (docs). Requires role with `Service Account - Manage` (`TMC_SERVICE_ACCOUNT_MANAGEMENT`) to create accounts; to run tasks the account needs `Engines - Use` (`TMC_ENGINE_USE`) or Operations permissions plus workspace `Execute`. |

```bash
# client-credentials exchange (verified shape from help.qlik.com "Generate service account token")
BASIC=$(printf '%s:%s' "$SA_ID" "$SA_SECRET" | base64 -w0)
curl -sS -X POST "https://api.us.cloud.talend.com/security/oauth/token" \
  -H "Authorization: Basic $BASIC" -H "Content-Type: application/json" \
  -d '{"grant_type":"client_credentials","audience":"https://api.us.cloud.talend.com"}'
# -> {"access_token":"eyJ...","token_type":"Bearer","expires_in":1800}   (expires_in approx; 30 min documented)
export TOKEN=...   # then: -H "Authorization: Bearer $TOKEN"
```

Token-related status codes: `401` = missing/expired/malformed token or wrong region host; `403` = token valid but the
user/service account lacks the permission or the workspace/environment is not shared with it (e.g. `TMC_ENGINE_USE`
missing -> 403 on `POST /executions`). Studio also exchanges a token for its own purposes (Preferences > Talend Cloud
> "Cloud access token"), the same PAT works there.

### 1.3 Resource catalog

Paths below are relative to `https://api.<region>.cloud.talend.com`. Where two forms exist, the `/tmc/v2.6/` form is
the legacy numbered API and the family form is current; payloads are the same unless noted. Fields in bold are
confirmed by snippets or release notes; others are from memory (mark as (unverified) when the row says so).

| Resource | Methods and paths | Body / query essentials | Notes |
|---|---|---|---|
| Environments | `GET /orchestration/environments` (`/tmc/v2.6/environments`) | `?query=name==Production` (RSQL-style `query` filter, unverified for every list) | Returns `{id, name, default, workspaces?}`. Environment IDs are needed for task listing. |
| Workspaces | `GET /orchestration/workspaces`, `POST /orchestration/workspaces {name, environmentId, description, owner}` | `?query=environment.id==<envId>` or `?environmentId=` | Each workspace has `environment.id`. Custom workspaces created by API need owner + roles. |
| Artifacts | `GET /orchestration/artifacts?workspaceId=&name=&type=`; `GET /orchestration/artifacts/{artifactId}`; `GET /orchestration/artifacts/{artifactId}/versions` (unverified exact) | `type` in `JOB`, `ROUTE`, `DATA_SERVICE`, `ACTION`, `PLAN`(?) | Artifacts are published from Studio ("Publish to Cloud") or Talend CI Builder; the public API is read-only for artifacts in current versions. Older `/tmc/v2.x/artifacts` multipart upload (`file`, `workspaceId`) existed and is deprecated (unverified). Artifact `versions[]` entries carry `version` strings like `"0.1.0.20240110123000"`; pass that exact string in `artifact.version`. |
| Tasks | **`GET /orchestration/executables/tasks`**, **`POST /orchestration/executables/tasks`**, `GET/PUT/DELETE /orchestration/executables/tasks/{taskId}` | List filters: `environmentId`, `workspaceId`, `name`, `artifactId`, `limit`, `offset`. Create body (fields confirmed in use-case docs): `name`, `description`, `workspaceId`, `artifact:{id, version}`, `parameters:{"ctx_key":"value"}`, `connections:{"connectionParamName":"<connectionId>"}`, `resources:{"resourceParamName":"<resourceId>"}`, `autoUpgradeInfo:{autoUpgradable:true, overrideWithDefaultParameters:false}`, `tags:[]` | `PUT` with the full body replaces the task (send everything, not a delta). Response `id` is the task id (also called `executable` in `/executions`). `environmentId` is derived from the workspace, not sent on create (some docs show it; harmless if present, unverified). |
| Task run-config | **`GET /orchestration/executables/tasks/{taskId}/run-config`**, **`PUT .../run-config`**, `DELETE .../run-config` (unschedule) | See 1.4 | Runtime, trigger, parallel-run, log level live here, not on the task. |
| Task upcoming runs | **`GET /orchestration/executables/tasks/{taskId}/run-config/events?from=&to=&limit=`** | ISO-8601 `from`/`to` | Added R2022-02; CRON triggers only at the time. |
| Task executions (history) | **`GET /processing/executables/tasks/{taskId}/executions`** (`?limit=&offset=&from=&to=`) | | Returns `items[{executionId, status/executionStatus, startTimestamp, ...}]`. This is how you find the execution id of a scheduled run (community: no direct way otherwise). |
| Task webhooks | `GET/POST /orchestration/executables/tasks/{taskId}/webhooks`, `DELETE .../webhooks/{webhookId}` (unverified exact) | create -> returns the callable URL and secret | See 1.8. Webhook trigger type must be set in run-config. |
| Plans | **`GET/POST /orchestration/executables/plans`**, `GET/PUT/DELETE /orchestration/executables/plans/{planId}`, `GET/PUT .../plans/{planId}/run-config`, `GET .../plans/{planId}/run-config/events` | Create body (unverified detail): `name`, `workspaceId`, `description`, `steps:[{name, condition:"ALL_SUCCEEDED"|"ALL_FAILED"|"ALWAYS"?, taskIds:["..."]}]`, `tags`. v2.6 also had `POST /plans/{id}/steps`. | Steps run tasks in parallel inside a step; steps chain by condition. Plan handlers (on failure / on success) exist in UI; API support (unverified). |
| Plan executions | `POST /processing/executions/plans {executable:"<planId>"}`; `GET /processing/executions/plans/{planExecutionId}`; `GET /processing/executables/plans/{planId}/executions` (unverified exact) | | Legacy: `POST /tmc/v2.6/executables/plans/{planId}/executions`? (unverified). Plan execution status strings differ from task ones (`EXECUTION_SUCCESSFUL`/`EXECUTION_FAILED`/`EXECUTING`, unverified). |
| Executions (tasks) | **`POST /processing/executions`**, **`GET /processing/executions/{executionId}`**, `GET /processing/executions/{executionId}/logs` (unverified), `POST /processing/executions/{executionId}/stop` (terminate, unverified path) | `POST` body `{"executable":"<taskId>","parameters":{"ctx":"v"},"logLevel":"INFO"?}` -> `{"executionId":"..."}` | See 1.5. Only one execution per task at a time unless `parallelExecutionAllowed` in run-config. |
| Promotions | **`GET /orchestration/promotions`**, `POST /orchestration/promotions {name, sourceEnvironmentId, targetEnvironmentId, description}`, **`POST /orchestration/promotions/{promotionId}/executions`**, `GET /orchestration/promotions/{promotionId}/executions/{execId}` | Execute body (unverified exact): `{"executable":"<promotionId>","keepTargetResources":true,"artifactType":"ENVIRONMENT"|"WORKSPACE"|"ARTIFACT"|"TASK"|"PLAN","artifactId":"<id>"}` | Promotion = copy env A -> env B; `keepTargetResources` keeps target parameter overrides. Execution report returned on GET (`executionStatus`, `report[]`). |
| Connections | `GET /orchestration/connections?workspaceId=`, `POST /orchestration/connections {name, workspaceId, app, parameters:{...}, engineId?}` (unverified exact), `GET/PUT/DELETE .../connections/{id}` | `app` = connection type label (e.g. `"Database"`, `"Salesforce"`) | Connection schemas depend on the connector; GET an existing one to copy the shape. |
| Resources | `GET /orchestration/resources?workspaceId=`, `POST /orchestration/resources` (multipart `file` + `name`,`workspaceId`), `PUT .../resources/{id}` (unverified) | | Resources = files tasks can read (certs, lookup files). |
| Schedules (decoupled, 2022+) | **`POST /orchestration/schedules`** `{name, workspaceId, triggers:[...]}`, `GET/PUT/DELETE /orchestration/schedules/{id}`, `POST /orchestration/schedules/{id}/triggers` (unverified path), assign with `PUT /orchestration/executables/tasks/{taskId}/schedule {scheduleId}` (unverified) | Doc constraints: max 15 triggers per schedule; two events of the same task at least 5 minutes apart | Replaces the single-trigger run-config model; a schedule is reusable across tasks/plans. |
| Engines / runtimes | `GET /processing/runtimes/remote-engines`, `POST /processing/runtimes/remote-engines {name, workspaceId|environmentId, description}` (returns pre-authorized key), `GET /processing/runtimes/remote-engine-clusters`, `GET /processing/runtimes/cloud-engines` (unverified exact names) | | Legacy `/tmc/v2.6/runtimes/remote-engines`. Remote Engine Gen2 (pipelines) and Dynamic Engines have their own resources (`/processing/dynamic-engines`?, unverified). |
| Execution history search | `POST /monitoring/executions/search` or similar on the "Execution History Search" family (unverified path) | | Event search API added R2022-05 for observability exports. |
| Audit logs | `GET /monitoring/audit/logs?from=&to=&limit=` (unverified) | | "Audit logs" feature in TMC; API exposure limited, verify. |
| Account / IAM | `GET /account/users`, `POST /account/users`, `GET /account/roles`, `GET /account/groups`, `POST /account/service-accounts`, `GET /account/service-accounts/{id}`, `POST .../secret/regenerate`? (unverified) | | Service Accounts API is documented on talend.qlik.dev (2021-03). |
| SCIM | `https://api.<region>.cloud.talend.com/scim/v2/Users`, `/scim/v2/Groups` (unverified base) | SCIM 2.0 with bearer token; used by Okta/Azure AD provisioning | Enabled per account from Security settings. |
| Data Inventory / Datasets | `GET /dataset/...`? `/inventory/datasets`? (unverified) | | Dataset listing + sample/quality for Data Inventory; see data-quality-governance.md. |
| Data Preparation API (cloud) | `/dataprep/api/preparations`, `/dataprep/api/datasets` (unverified) | | On-prem equivalents `/api/preparations`, `/api/datasets` are better known (section 7). |
| Pipeline Designer API | `/pipelines/...` (unverified) | | Pipeline tasks are ordinary `executables/tasks` with `artifact.type=PIPELINE`; pipeline-specific run-config supports CRON via `configuring-cron-trigger-for-pipeline-tasks`. |
| Trust Score API | (unverified) | | Trust Score is exposed in Data Inventory UI; public API presence unverified. |

### 1.4 Task run-config and triggers

`PUT /orchestration/executables/tasks/{taskId}/run-config` (and `/plans/{planId}/run-config`). Shape (CRON example
appears in R2022-02 release notes; other trigger types from memory, field names (unverified)):

```json
{
  "trigger": {
    "type": "CRON",
    "startDate": "2024-05-01",
    "timeZone": "Europe/Paris",
    "cronExpression": "0 0/15 8-18 ? * MON-FRI"
  },
  "runtime": { "type": "REMOTE_ENGINE", "id": "<engineId>" },
  "parallelExecutionAllowed": false,
  "logLevel": "INFO"
}
```

| Field | Values | Notes |
|---|---|---|
| `trigger.type` | `MANUAL`, `ONCE`, `DAILY`, `WEEKLY`, `MONTHLY`, `CRON`, `WEBHOOK` | `MANUAL` = no schedule (equivalent to DELETE run-config trigger). |
| `ONCE` | `startDate` (`YYYY-MM-DD`), `startTime` (`HH:mm`), `timeZone` | Fires once. |
| `DAILY` | `startDate`, `startTime`, `timeZone`, `interval` (every N days), optional `atTimes`/`times` list (unverified) | UI offers "every N hours/minutes between X and Y"; API field names unverified. |
| `WEEKLY` | `daysOfWeek:["MONDAY",...]`, `startTime`, `timeZone` | |
| `MONTHLY` | `dayOfMonth` (1-31 or `LAST`?) , `startTime`, `timeZone` | unverified |
| `CRON` | `cronExpression`, `timeZone` | TMC UI cron (pipeline guide): minute field 0-59, `*/5` is the minimum interval (5 min). Release-note example used Quartz-style with seconds field; accept both? -> verify against Swagger for your account. Keep `timeZone` an IANA id. |
| `WEBHOOK` | none; create webhook via `/webhooks` sub-resource | Then POST the webhook URL to run. |
| `runtime.type` | `CLOUD` (cloud engine, pipelines only now), `REMOTE_ENGINE`, `REMOTE_ENGINE_CLUSTER` | `id` = engine or cluster id. Cloud Engine for Design jobs was retired; Data Integration tasks need a Remote Engine. |
| `runtime.runProfileId` | id of a cluster run profile (unverified name) | For Remote Engine Gen2/Dynamic Engine pipeline tasks ("run profile" selects Spark/local resources). |
| `parallelExecutionAllowed` | bool | Allow overlapping runs; default false -> second run rejected with `EXECUTION_REJECTED`. |
| `logLevel` | `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `OFF`? | Applies to Job log4j level at run. |
| `jvmParameters` / `jvmArguments` (unverified name) | `["-Xmx2g"]` | Task-level JVM args (Studio "JVM settings" equivalent). |

### 1.5 Executions and status polling

```bash
# run
curl -sS -X POST "$API/processing/executions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"executable":"'"$TASK_ID"'","parameters":{"run_date":"2024-05-01","batch_size":"500"}}'
# -> {"executionId":"8f3c1d2e-...."}
# poll
curl -sS "$API/processing/executions/$EXEC_ID" -H "Authorization: Bearer $TOKEN"
# -> {"executionId":"...","executionStatus":"EXECUTING","startTimestamp":"...","finishTimestamp":null,
#     "jobExitCode":null,"userId":"...","taskId":"...","triggerType":"MANUAL" ...}
```

`executionStatus` enum (`JobExecutionStatus` schema on talend.qlik.dev; community reports confirm lower/upper
case variants `execution_successful`, `deploy_failed`; the list is cut off in the snippet, so the exact full
set is partially (unverified)):

| Status | Meaning | Terminal? |
|---|---|---|
| `DISPATCHING` | TMC chose an engine and queued the request | no |
| `DEPLOYING` | Engine downloads artifact + dependencies | no |
| `DEPLOY_FAILED` | Artifact/dependency download or unpack failed on the engine | yes (failure) |
| `EXECUTING` | Job process running | no |
| `EXECUTION_SUCCESS` | Job exit code 0 (task executions, Processing API and Execution History Search) | yes |
| `EXECUTION_FAILED` | Job exit code != 0 or crashed | yes (failure) |
| `EXECUTION_REJECTED` | Run refused: parallel run not allowed, engine unavailable/paused, licence | yes (failure) |
| `TERMINATING` / `EXECUTION_TERMINATED` | Stopped by user/API (`stop`) | yes |
| `TIMEOUT`? | Engine never acknowledged (unverified) | yes |

Task executions (`/processing/executions/{id}` and the Execution History Search API) report `EXECUTION_SUCCESS`;
plan executions (`/processing/executions/plans/{id}`, Orchestration API) report lower-case `execution_successful` /
`execution_failed`. Compare case-insensitively and accept both spellings. Poll every 10-30 s; executions of scheduled runs are listed via
`GET /processing/executables/tasks/{taskId}/executions`. The job's own `--context_param` values are passed as
`parameters` (string values only; TMC casts to the context type). Logs: `GET .../executions/{id}/logs` (unverified)
returns the log tail or a download URL; full logs are in TMC > Operations > Task run history > Logs, and on the engine
under `<engine>/data/...` (see deployment-runtime.md).

### 1.6 Pagination, errors, limits

| Topic | Behaviour |
|---|---|
| Pagination | `limit` (default 20-100, max 100 on most lists) + `offset`; list responses `{ "items": [...], "limit": n, "offset": n, "total": n }`. Some older `/tmc/v2.6` lists return a bare array. |
| Filtering | `query=` RSQL-like (`name==Foo;environment.id==123`) on orchestration lists; explicit params (`environmentId`, `workspaceId`, `name`) elsewhere. |
| Error body | `{"status": 400, "code": "ORCHESTRATION_...", "message": "...", "errors": [{"field": "...", "message": "..."}]}` (approximate; `code`/`message` are stable, `errors` only on validation). 400 validation, 401 auth, 403 permission, 404 unknown id or wrong region, 409 conflict (duplicate task name in workspace, parallel run), 429 throttled, 5xx engine/service. |
| Rate limits | Not published (unverified). Expect 429 with `Retry-After` under bursts; keep polling >= 5 s intervals. |
| Idempotency | None; `POST /executions` twice = two runs (or second `EXECUTION_REJECTED`). |
| Timeouts | Token exchange and lists are fast; execution start is asynchronous (returns in < 1 s), do not wait on the POST. |

### 1.7 curl cookbook

```bash
API=https://api.eu.cloud.talend.com; H="Authorization: Bearer $TOKEN"; J="Content-Type: application/json"

# 1. list tasks of an environment (resolve env then list)
ENV_ID=$(curl -sS "$API/orchestration/environments" -H "$H" | jq -r '.[] | select(.name=="Production") | .id')
curl -sS "$API/orchestration/executables/tasks?environmentId=$ENV_ID&limit=100&offset=0" -H "$H" \
  | jq '.items[] | {id, name, workspace: .workspace.name, artifact: .artifact.name, version: .artifact.version}'

# 2. run a task with parameters, 3. poll until terminal
EXEC=$(curl -sS -X POST "$API/processing/executions" -H "$H" -H "$J" \
  -d "{\"executable\":\"$TASK_ID\",\"parameters\":{\"load_date\":\"2024-05-01\"}}" | jq -r .executionId)
while :; do S=$(curl -sS "$API/processing/executions/$EXEC" -H "$H" | jq -r .executionStatus | tr a-z A-Z)
  echo "$S"; case "$S" in EXECUTION_SUCCESS|EXECUTION_SUCCESSFUL) exit 0;; EXECUTION_FAILED|DEPLOY_FAILED|EXECUTION_REJECTED|*TERMINATED) exit 1;; esac; sleep 15; done

# 4. point a task at a newly published artifact version (full PUT; GET first, patch, PUT back)
curl -sS "$API/orchestration/executables/tasks/$TASK_ID" -H "$H" > task.json
NEW_VER=$(curl -sS "$API/orchestration/artifacts/$(jq -r .artifact.id task.json)" -H "$H" | jq -r '.versions[-1]')
jq --arg v "$NEW_VER" '{name, description, workspaceId: .workspace.id, artifact: {id: .artifact.id, version: $v},
    parameters, connections, resources, autoUpgradeInfo, tags}' task.json > task.put.json
curl -sS -X PUT "$API/orchestration/executables/tasks/$TASK_ID" -H "$H" -H "$J" -d @task.put.json
#    (or set autoUpgradeInfo.autoUpgradable=true and let publishing a new version upgrade the task)

# 5. schedule with cron (run-config) on a remote engine
curl -sS -X PUT "$API/orchestration/executables/tasks/$TASK_ID/run-config" -H "$H" -H "$J" -d '{
  "trigger":{"type":"CRON","startDate":"2024-05-01","timeZone":"Europe/Paris","cronExpression":"0 0 2 * * ?"},
  "runtime":{"type":"REMOTE_ENGINE","id":"'"$ENGINE_ID"'"},"parallelExecutionAllowed":false,"logLevel":"INFO"}'
curl -sS "$API/orchestration/executables/tasks/$TASK_ID/run-config/events?limit=5" -H "$H"   # next fire times
```

### 1.8 Webhooks, API Tester CLI

- Webhook trigger ("run a Job as a service"): set run-config `trigger.type=WEBHOOK`, then
  `POST /orchestration/executables/tasks/{taskId}/webhooks {"name":"..."}` -> response holds the callable `url`
  (shape `https://api.<region>.cloud.talend.com/orchestration/executables/tasks/{taskId}/webhooks/{webhookId}`, unverified)
  and a secret. External systems `POST` that URL (no bearer token; the secret in the URL/path is the credential) and
  may send a JSON body which the Job can read via a `resource`/context (unverified). Rotate by deleting and
  re-creating the webhook; the old URL dies immediately.
- Talend Cloud API Tester CLI = Maven plugin: run a saved API Tester project (exported `.json`) in CI.
  Coordinates `com.talend.cloud:api-tester-maven-plugin` (groupId unverified); invocation documented as
  `mvn api-tester:test -Dfile=<project.json> -DselectedEnvironment=<env> -DaccountId=<id> -DinstanceId=<id>`
  with `-DinstanceToken=` / `-DauthToken=` for the Cloud account (parameter names (unverified)). JUnit XML reports land in
  `target/`. See esb-routes-services.md for API Designer/Tester usage.

---

## 2. TAC MetaServlet API

| Item | Value |
|---|---|
| Endpoint | `http(s)://<tac-host>:8080/org.talend.administrator/metaServlet?<base64(JSON)>` (GET) or POST with the same single unnamed base64 value as body |
| Encoding | JSON -> Base64 (standard alphabet, single line, NO line wrapping: `base64 -w0`), then URL-encode `+`,`/`,`=` if your client does not. Base64 wrapped at 76 chars (GNU default) breaks the request. |
| Auth | `authUser` / `authPass` fields inside the JSON (TAC user with Operation Manager / Administrator role). Plaintext unless TAC is on HTTPS; put TAC behind TLS. TAC 8 personal tokens for MetaServlet: not documented (unverified); `forceRedeploy`-style flags exist per command. |
| Response | JSON: always `returnCode` (0 = success) and `executionTime:{millis, seconds}`; on error `error` message. |
| Helper CLI | `<TAC webapp>/WEB-INF/classes/MetaServletCaller.sh` (`.bat`) : `./MetaServletCaller.sh --tac-url=http://tac:8080/org.talend.administrator --json-params='{"actionName":"help"}'`; `--json-file=<file>` (`--file`) to read JSON from a file; `--help`; `-v` verbose (unverified). Encodes and calls for you. |
| Timeouts | `runTask` in `synchronous` mode blocks until the job ends -> client/proxy timeouts kill long jobs; use `asynchronous` + `getTaskExecutionStatus`. Servlet-side no timeout. |
| Version note | Commands differ by TAC version; `help` lists what your TAC supports. TAC 8.0 keeps MetaServlet (TAC itself is being superseded by TMC). |

```bash
JSON='{"actionName":"runTask","authUser":"admin@company.com","authPass":"admin","taskId":12,"mode":"asynchronous",
       "context":{"load_date":"2024-05-01"}}'
curl -sS "http://tac:8080/org.talend.administrator/metaServlet?$(printf '%s' "$JSON" | base64 -w0)"
# -> {"execRequestId":"1714560000000_abcDEF","returnCode":0,"executionTime":{"millis":120,"seconds":0}}
JSON2='{"actionName":"getTaskExecutionStatus","authUser":"admin@company.com","authPass":"admin","execRequestId":"1714560000000_abcDEF"}'
curl -sS "http://tac:8080/org.talend.administrator/metaServlet?$(printf '%s' "$JSON2" | base64 -w0)"
# -> {"execDetailedStatus":"ENDED","jobExitCode":0,"returnCode":0, ...}   (RUNNING / JOB_ERROR while running / failed)
```

### Command catalog

Names in bold confirmed by help.qlik.com snippets; others are from memory of the 6.x-8.0 `help` output and marked
(unverified) where doubtful. Every command takes `authUser`/`authPass` except `help`.

| Command (`actionName`) | Parameters | Result / notes |
|---|---|---|
| **`help`** | optional `commandName` | Lists all commands with parameters: the authoritative catalog for your version. |
| **`listTasks`** | none | Array of tasks `{id, label, projectName, jobName, jobVersion, context, status, ...}`. |
| **`getTaskIdByName`** | `taskName` | `{taskId}`. Task labels are not unique across projects in theory; ids are. |
| **`runTask`** | `taskId`, `mode` (`synchronous`|`asynchronous`), `context:{k:v}` (context overrides, strings), `jvmParams`? (unverified) | async -> `execRequestId`; sync -> `jobExitCode`, `execDetailedStatus`. |
| **`getTaskExecutionStatus`** | `execRequestId` | `execDetailedStatus` in `RUNNING`, `ENDED`, `JOB_ERROR`, `DEPLOYING`?, `WAITING`?; `jobExitCode`. |
| `getTaskStatus` | `taskId` | Task-level `status`: `READY_TO_RUN`, `RUNNING`, `NOT_GENERATED`, `GENERATING`, `GENERATION_FAILED`?, `DEPLOYING`, `PAUSED`? (values unverified). |
| `stopTask` / `killTask` | `taskId` | Graceful stop vs process kill (killTask unverified name). |
| `pauseTask` / `resumeTask` | `taskId` | Pause/resume triggers of a task (pausing in Job Conductor). |
| `requestPauseTriggers` / `requestResumeTriggers` | `taskId` | Older names for the same (unverified). |
| **`createTask`** | `taskName`, `projectName`, `jobName`, `jobVersion` (`"Latest"` allowed), `contextName`, `executionServerName`, `description`, `active` (bool), `onUnknownStateJob` (`WAIT`|`KILL_TASK`|`RESTART_TASK`), `branch`? , `addStatisticsCodeEnabled`, `applyContextToChildren`, `regenerateJobOnChange`, `timeout`?, `pauseOnError` | Creates a Job Conductor task from a repository (SVN/Git) job. |
| `updateTask` | `taskId` + same fields as createTask | |
| `deleteTask` | `taskId` | |
| `createArtifactTask` / `updateArtifactTask` (unverified exact) | `taskName`, `artifactRepository`?, `artifactUrl`/`artifactGroupId`/`artifactId`/`artifactVersion`, `executionServerName`, `contextName` | Nexus/Artifactory-based ("Artifact task") tasks in 6.x+. |
| `associatePreGeneratedJob` | `taskId`, `importType` (`Nexus`), `artifactUrl`? , `filePath`? | Attach a pre-built job zip to a task (skips Generate). |
| **`requestGenerate`** | `taskId` | Trigger Generate (CommandLine) for a task; async; poll `getTaskStatus`. |
| **`requestDeploy`** | `taskId` | Deploy to execution server. |
| `requestUndeploy` | `taskId` | |
| `runExecPlan` / `requestRunExecPlan` | `execPlanId` or `execPlanName`? | Run an Execution Plan; returns `execRequestId`? (unverified) |
| `listExecutionPlans`, `getExecutionPlanStatus` | `execPlanId`? | |
| `addCronTrigger` / `addSimpleTrigger` / `addFileTrigger`, `deleteTrigger`, `listTriggers`, `pauseTrigger`, `resumeTrigger` (names unverified) | `taskId`, trigger fields (`cronExpression`, `startDate`, `timeZone`, `interval`, `path`...) | Quartz cron (6-7 fields). |
| `createServer` / `updateServer` / `deleteServer` / `listServers` | `label`, `host`, `commandPort` (8000), `filePort` (8001), `monitoringPort` (8888), `timeoutUnknownState`, `useSSL`, `username`/`password` (JobServer auth), `active` | Execution servers (JobServer). |
| `createProject` / `updateProject` / `deleteProject` / `listProjects` (`listProject`) | `projectName`, `projectType` (`DI`|`DQ`|`MDM`|`ESB`...), `storage` (`GIT`|`SVN`|`None`), `url`, `username`, `password`, `description`, `author`, `technicalLabel`, `language` (`java`) | Git fields on 7.x+: `gitUrl`? verify with `help`. |
| `createUser` / `updateUser` / `deleteUser` / `listUsers` | `userLogin`, `userPassword`, `userFirstName`, `userLastName`, `userRole` (comma list: `Administrator`, `Operation manager`, `Designer`, `Viewer`), `userType` (`DI`|`DQ`|`MDM`|`ESB`), `active` | |
| `createAuthorization` / `deleteAuthorization` / `listAuthorizations` (unverified) | `userLogin`, `projectName`, `authorizationType` (`ReadOnly`|`ReadWrite`) | Equivalent of "project authorizations" UI; there is no `addUserToProject` command by that name (unverified). |
| `createUserGroup`? , `listGroups`? | | (unverified) |
| `getLicense` / `setLicense` / `updateLicense` / `getLicenseInfo` | `license` (string) | Upload/inspect licence. |
| `listConnection` / `createConnection` (unverified) | | Database/JNDI connections for DQ. |
| `getArchivaUrl` | none | Legacy (TAC 5.x Archiva); 6.x+ use Nexus settings (`getNexusUrl`? unverified). |
| `createESBTask` / `updateESBTask` / `requestStartESBTask` / `requestStopESBTask` / `getESBTaskStatus` | ESB Conductor equivalents | Talend Runtime feature deploys. |
| `setLogLevel`, `getTaskLogs`, `backupDB`, `listNexusArtifacts`, `associateProjectToTask` | | Not confirmed to exist; treat as absent unless `help` lists them. |

| `returnCode` | Meaning (0 and 30 confirmed; rest from memory, (unverified)) |
|---|---|
| 0 | OK |
| 1 | Generic error (exception in command) |
| 2 | Unknown command / not implemented in this version |
| 3 | Authentication failed (bad `authUser`/`authPass`) or missing authentication |
| 4 | Missing or invalid parameter |
| 5 | JSON parse / base64 decode error |
| 10 | Object (task/project/user) not found |
| 30 | Error while launching the task (engine down, task not generated, task already running) |
| 32 | Task already running / cannot run in current state |

Ids vs labels: `runTask` needs numeric `taskId` (`id` in `listTasks`), not the label; `getTaskIdByName` bridges.
`execRequestId` (string from `runTask`) is not the same as `taskId` or the Job Conductor "execution id"; store both.
Passwords with `"`, `\` or non-ASCII need JSON escaping before base64; `+`/`/` in the base64 need URL-encoding when
passed in a query string (MetaServletCaller does this). From a Job: tREST GET to `.../metaServlet?` + routine that
Base64-encodes (`help.qlik.com` job example "Calling MetaServlet REST web service to execute task").

---

## 3. Studio CommandLine

The CommandLine is Studio headless (`org.talend.commandline.CommandLine` application). Uses: TAC's "Generate" step
(Job Conductor -> CommandLine server on the TAC or a dedicated host), scripted exports, bulk project operations.
Since 8.0 the recommended CI build path is `talend-ci-builder` (Maven, see deployment-runtime.md); the CommandLine
remains shipped for TAC generation and scripting.

| Item | Value |
|---|---|
| Launchers | `commandline-linux.sh`, `commandline-mac.sh`, `commandline.bat` in the Studio directory (subscription Studio only). Contents: `./Talend-Studio-linux-gtk-x86_64 -nosplash -application org.talend.commandline.CommandLine -consoleLog -data commandline-workspace startServer -p 8002` |
| Modes | `startServer -p <port>` (TCP server; TAC uses it), `shell` (interactive), `scriptFile <path>` (batch; one command per line, ends with `quit`), `startServer_sh`? (unverified) |
| Ports | 8002 command port, 8003 file transfer port (TAC > Servers > CommandLine "Command line port"/"File transfer port"). TAC configuration: Configuration > CommandLine/primary: host, port, path, file transfer port. |
| Workspace | `-data <dir>`; one CommandLine per workspace (`.metadata/.lock`). Default `commandline-workspace`. |
| JVM | `commandline-linux.sh` may need `-vmargs -Xmx2048m`; same `TALEND_HOME/configuration/config.ini` as Studio. Proxy/offline: `-Dtalend.disable.internet=true`? (unverified; Studio honors `talend.studio.disable.updatesite`?) |
| Help | `help` lists commands; `<command> -help` lists options (docs point to this). |

```text
# scriptFile example (Git project on TAC)
initRemote http://tac:8080/org.talend.administrator -ul admin@company.com -up admin
logonProject -pn MYPROJ -ul admin@company.com -up admin -br master
listJob
exportJob LoadCustomers -dd /opt/builds -af LoadCustomers_0.2 -jv 0.2 -jc Default
logoffProject
quit
```

| Command | Key options | Notes |
|---|---|---|
| `initRemote <tacUrl> -ul <user> -up <pass>` | TAC URL ends with `/org.talend.administrator` | Reads project/SCM config from TAC. |
| `initLocal` | | Work with local (non-TAC) projects in the workspace. |
| `logonProject -pn <project> -ul <user> -up <pass> [-br <branch>] [-ro]` | `-br` Git branch/tag, `-gt`? (not confirmed; `-ro` read-only (unverified)) | Checks out/imports the project into the CommandLine workspace. Always `logoffProject` after. |
| `logoffProject` | | Required before switching projects; a scriptFile ending without it can leave no export (community). |
| `listProject` / `listJob` / `listItem`? / `listRoute`? | `listJob -pn`? | |
| `exportJob <job> -dd <destDir> -af <archiveName> -jv <version> -jc <context> [-ab] [-cv]...` | Confirmed: `-dd`, `-af`, `-jv`, `-jc`. Memory: `-ab` apply to all builds? , `-cv` include context values?, `-ltm` log4j level? , `-sl` sources? (unverified; run `exportJob -help`) | Produces the same zip as Studio "Build Job". |
| `buildJob <job> -dd <dir> -af <name> -jc <ctx> -jv <ver>` | Same options as exportJob (TAC 7.x docs example `buildJob MyJob -dd C:/tac/builds -af MyJob_0.1 -jc Default -jv 0.1`) | TAC "Build Job" page removed in 8.0; command still in CommandLine (unverified for 8.0). |
| `exportAllJob -dd <dir>` | | Bulk export. |
| `generateJob <job> [-jv]` / `generateAllJob` (unverified) | | What TAC calls for "Generate". |
| `executeJob <job> -jc <context> -jv <version> [-ctp key=value;key2=value2]` | `-ctp` context params (separator unverified) | Runs in the CommandLine JVM; use for smoke tests only. |
| `publishJob <job> -pv <version> -g <groupId> -a <artifactId> -r <repoUrl> -u <user> -p <pass> [-s] [-t <type>]` | `-s` snapshot, `-t` job type/packaging (unverified) | Publishes to Nexus/Artifactory (6.x/7.x "Publish" equivalent). |
| `importItems <zip|dir> [-im] [-if]` / `exportItems -dd <dir> -af <name> [-ib items...]` (options unverified) | | Repository item import/export (same as Studio Import Items). |
| `createProject -pn <name> -pd <desc> -pl java -pa <author>` ; `deleteProject -pn <name>` | | Local/TAC project creation; on TAC-connected mode also `createProject` writes TAC project (unverified). |
| `checkoutProject`? , `syncLibraries`, `changeContext`? , `setJobDependency`? | | Unverified; check `help`. |
| `quit` / `stopServer` | | `stopServer` for server mode. |

Troubleshooting: TAC Generate stuck "GENERATING" -> look in CommandLine workspace `.metadata/.log`, confirm port 8002
reachable from TAC, delete stale `.metadata/.lock`, make sure Studio and CommandLine versions match TAC patch level
(R20xx-yy), and that the CommandLine licence file (`license` in Studio dir) is valid.

---

## 4. Talend Component Kit (TCK) SDK

Framework for custom connectors usable in Studio 7.x/8.x (Standard jobs), Pipeline Designer / Remote Engine Gen2
(Beam) and Talend Cloud. Replaces javajet: components are annotated Java classes, metadata (datastore/dataset) is
reusable, forms are generated from `@Option` models, no code templates. Versions on Maven Central: `1.1.x` (2018),
`1.38.x` (Studio 7.3), `1.50`-`1.56` (8.0 R2022-R2023), `1.80`-`1.95.x` (8.0 R2024-R2025), `1.2610.0` (released
2026-09, new date-style scheme). Match the TCK version to your Studio patch (Studio ships a given runtime).

### Maven coordinates (groupId `org.talend.sdk.component`)

| Artifact | Use |
|---|---|
| `component-api` | Annotations + `Record`/`Schema` API (compile scope, `provided` in Studio). |
| `component-runtime-manager` | Runtime: `ComponentManager`, `Job` DSL (chain). |
| `component-runtime-junit` (+ `component-runtime-junit-base`) | JUnit 4/5 test harness (`SimpleComponentRule`, `@WithComponents`, `ComponentExtension`). |
| `component-runtime-testing-spark`, `component-runtime-beam` | Beam/Spark environments for tests and Pipeline Designer runtime. |
| `component-runtime-di` | Studio DI bridge (versions `1.x` and `10.x`). |
| `component-tools` | Validators, `CarBundler`, `CarMain` (the `.car` executable). |
| `component-server` | Component server used by Cloud/Pipeline Designer and `talend-component:web`. |
| `talend-component-maven-plugin` | Build goals (below). Gradle: plugin id `org.talend.sdk.component` (`talend-component-gradle-plugin`). |
| `component-starter-server` | Backend of Component Starter `https://starter-toolkit.talend.io` (generates a Maven/Gradle skeleton with chosen input/processor/output and dataset/datastore). |

### Maven plugin goals (from plugin.xml 1.95.3, prefix `talend-component`)

| Goal | Phase | Key properties | Purpose |
|---|---|---|---|
| `validate` | process-classes | `talend.validation.*` flags: `options`, `internationalization` (+`.autofix`), `layout`, `dataset`, `datastore`, `family`, `metadata`, `svg`, `record`, `schema`, `serializable`, `documentation`, `exceptions`, `httpclient`, `localConfiguration`, `placeholder`, `wording`, `noFinalOption`, `fixedschema`, `checkpoint`, `validateOutputConnection`; `talend.validation.failOnValidateExceptions` | Static checks (option names vs Messages.properties, layouts, icons, serializable configs). Runs on every build. |
| `dependencies` | process-classes | `talend.dependency.output` -> `TALEND-INF/dependencies.txt` | Runtime dependency list packed into the jar (used by Studio/engines to resolve libs). |
| `metadata` | process-classes | `talend.metadata.location` -> `TALEND-INF/components.json` | Component list/metadata. |
| `scan-descriptor` | process-classes | -> `TALEND-INF/scanning.properties` | Pre-scan speeds up runtime load. |
| `asciidoc` | process-classes | `talend.documentation.output` -> `TALEND-INF/documentation.adoc`, `talend.documentation.locales` | Generates docs from `@Documentation`. `dita` for DITA zip. |
| `svg2png` | process-classes | `talend.icons.source` (`target/classes/icons`) | Studio needs PNG 32x32 (`_icon32.png`) alongside SVG. |
| `car` | (bind manually, e.g. package) | `talend.car.output` (`target/<finalName>.car`), `talend.car.classifier=component`, `talend.car.attach`, `talend.bundle.include/exclude.artifacts` | Component ARchive: jar + dependencies + manifest. |
| `deploy-in-studio` | manual | `talend.component.studioHome` (required), `talend.component.studioM2`, `talend.component.enforceDeployment` | Copies jars into Studio's m2 and registers the component in `configuration/config.ini`. Studio must have been started once (needs `configuration/config.ini`) and must be CLOSED during deploy. |
| `web` | manual | `talend.web.port` (8080) | Starts component-server + UI to preview forms: `http://localhost:8080`. |
| `prepare-repository`, `repository-report`, `uispec`, `icon-report`, `singer`, `website`, `help` | package/manual | | Multi-module m2 staging, dependency-conflict report, UiSpec export, Singer tap packaging. |

```bash
mvn clean package                                    # validate + dependencies + metadata + asciidoc + jar
mvn talend-component:car                             # target/my-connector-1.0.0.car
mvn talend-component:deploy-in-studio -Dtalend.component.studioHome="/opt/Talend-Studio"   # quote paths with spaces
java -jar target/my-connector-1.0.0.car studio-deploy --location /opt/Talend-Studio         # same via the .car
java -jar target/my-connector-1.0.0.car maven-deploy --location ~/.m2/repository
java -jar target/my-connector-1.0.0.car deploy-to-nexus --url http://nexus:8081 --repo talend-components --user u --pass p [--threads 4] [--dir /tmp]
# CarMain commands/flags above are the literal strings in component-tools 1.95.3
```

### Project layout and metadata

```text
src/main/java/com/acme/mycomp/
  package-info.java            @Components(family = "MyFamily", categories = "Misc")  @Icon(value = Icon.IconType.CUSTOM, custom = "myfamily")
  datastore/MyDatastore.java   @DataStore("MyDatastore") @Checkable("healthcheck") @GridLayout(...)
  dataset/MyDataset.java       @DataSet("MyDataset") { @Option MyDatastore datastore; @Option String table; }
  source/MyMapper.java         @PartitionMapper(name="Input")  or  @Emitter(name="Input")
  source/MySource.java         @Producer Record next()
  output/MyOutput.java         @Processor(name="Output") @ElementListener void onNext(@Input Record r)
  service/MyService.java       @Service  (+ @HealthCheck, @Suggestions, @DiscoverSchema, @Update actions)
src/main/resources/com/acme/mycomp/Messages.properties        MyFamily._displayName=My Family
                                                            MyFamily.Input._displayName=My Input
                                                            MyFamily.datastore.MyDatastore.url._displayName=URL
src/main/resources/icons/myfamily.svg  (+ myfamily_icon32.png for Studio, generated by svg2png)
src/main/resources/TALEND-INF/local-configuration.properties  (defaults read via @Configuration/LocalConfiguration)
target/classes/TALEND-INF/{dependencies.txt, components.json, documentation.adoc, scanning.properties} (generated)
```

Messages key patterns: `<Family>._displayName`, `<Family>.<Component>._displayName`, `<Family>.<configType>.<Name>.<option>._displayName`
/ `._placeholder` / `._documentation`, enum values `<Class>.<CONSTANT>._displayName`, actions `<Family>.actions.<type>.<name>._displayName`.
`validate` fails when an `@Option` has no display name key (`talend.validation.internationalization`); `.autofix=true`
writes the missing keys.

### Annotation reference (all present in component-api 1.95.3)

| Area | Annotation / type | Notes |
|---|---|---|
| Family | `@Components(family, categories[])` on `package-info.java`; `@Icon(value, custom)`; `@Version(value, migrationHandler)` on component class; `MigrationHandler.migrate(int incomingVersion, Map<String,String> config) -> Map` | Bump `@Version` when option names change; handler receives flattened config (`configuration.dataset.table`). Also `@Metadatas`, `@ReturnVariables`/`@AfterVariables` (after-variables like legacy `NB_LINE`), `@DatabaseMapping`. |
| Input | `@Emitter(family?, name)` simple non-splittable input with `@Producer Object next()` (return `null` to end); `@PartitionMapper(family?, name, infinite=false, stoppable=false, optionalRow=false)` with `@Assessor long estimateSize()`, `@Split List<Mapper> split(@PartitionSize long bundle)`, `@Emitter Source createSource()`; source class has `@Producer`. `infinite=true` = streaming (Pipeline Designer, never ends; `stoppable` lets runtime stop via `Option.MAX_DURATION_PARAMETER`/`MAX_RECORDS_PARAMETER` constants). | `@PostConstruct` init, `@PreDestroy` release (javax/jakarta annotations). Checkpointing: `@Checkpoint`, `@CheckpointAvailable`, `@CheckpointData` (`input.checkpoint`). `BufferizedProducerSupport` helper for paged APIs. |
| Processor / output | `@Processor(family?, name)`; `@ElementListener void onNext(@Input Record in, @Input("lookup") Record other, @Output OutputEmitter<Record> main, @Output("reject") OutputEmitter<Record> reject)`; `@BeforeGroup`/`@AfterGroup` (bundle hooks; `@AfterGroup` may take `@Output` for batched emission), `@LastGroup`; `@MultiOutputIterator`, `@TaggedOutput`, `@ConditionalOutput`/`AvailableOutputFlows` (dynamic output flows) | A processor with no `@Output` is an output component (sink). Studio only shows connectors whose `@ElementListener` returns void or has outputs. |
| Standalone | `@DriverRunner` + `@RunAtDriver` (`api.standalone`) | Components with no data flow (run once on driver). |
| Configuration | `@Option(value="")` on fields of a serializable POJO; `@DataStore(name)`, `@DataSet(name)` (`configuration.type`), `@DatasetDiscovery`, `@DynamicDependenciesConfiguration`; constraints `@Required`, `@Min`, `@Max`, `@Pattern` (JS regex), `@Uniques`; conditions `@ActiveIf(target, value, negate, evaluationStrategy)`, `@ActiveIfs(operator)`, `@UIScope`; actions `@Checkable` (healthcheck), `@Proposable`, `@Suggestable`, `@BuiltInSuggestable`, `@Updatable`, `@Validable`; dependency `@ConnectorReference`/`@ConnectorRef` | Option names = field names (must match Messages keys and must not be `final`); nested POJOs produce dotted paths. A `@DataSet` must reference exactly one `@DataStore`. |
| UI | `@GridLayout(names={...}, value=...)`, `@GridLayouts`, `@GridLayout.FormType.ADVANCED` for advanced tab; `@OptionsOrder`, `@AutoLayout`, `@HorizontalLayout`, `@VerticalLayout`; widgets `@Credential` (password), `@TextArea`, `@Code("sql")`, `@Structure(type=IN|OUT, discoverSchema="...")` (schema editor), `@Path`, `@DateTime`, `@ModuleList`, `@BasedOnSchema`, `@ReadOnly`, `@Hidden`, `@DefaultValue` | `@Structure` on `List<String>` gives column list in Studio. |
| Services | `@Service` class injected into components via constructor; actions: `@HealthCheck` returns `HealthCheckStatus(Status.OK|KO, comment)`, `@Suggestions` -> `SuggestionValues`, `@DynamicValues` -> `Values`, `@DiscoverSchema`/`@DiscoverSchemaExtended` -> `Schema`, `@FixedSchema`, `@Update` (updatable form), `@AsyncValidation` -> `ValidationResult`, `@DiscoverDataset`, `@CreateConnection`/`@CloseConnection` (shared connection), `@DatabaseSchemaMapping`, `@Cached`/`LocalCache`, `@Configuration("prefix")` / `LocalConfiguration`, `Resolver`, `ObjectFactory`, `Injector`, `ProducerFinder`, `RecordService`, `RecordPointerFactory`, HTTP client: `interface Client extends HttpClient { @Request(method="GET", path="/x/{id}") Response<JsonObject> get(@Path("id") String id, @Header("Authorization") String auth, @Query("q") String q); }` with `@Base`, `@Url`, `@Codec`, `@UseConfigurer`, `@ConfigurerOption`, `oauth1.OAuth1` | Services are singletons per plugin; keep them stateless/thread-safe. `@Internationalized` interfaces give typed message bundles. |
| Record API | `Record` (`getSchema()`, typed `getString/getInt/getLong/getDouble/getFloat/getBoolean/getBytes/getRecord/getArray/getDateTime/getInstant/getDecimal`, `getOptional*` variants, `get(Class,name)`, `withNewSchema(Schema)`, `isValid()`); `RecordBuilderFactory` (`newRecordBuilder()`, `newRecordBuilder(Schema)`, `newSchemaBuilder(Schema.Type)`, `newEntryBuilder()`); `Schema.Type` = `RECORD, ARRAY, STRING, BYTES, INT, LONG, FLOAT, DOUBLE, BOOLEAN, DATETIME, DECIMAL`; `Schema.Entry` (`withName`, `withType`, `withNullable`, `withDefaultValue`, `withComment`, `withProp`), `SchemaProperty` constants (studio type/length/precision/pattern props), `OrderedMap`, `RecordPointer` (JSON-pointer access) | Nullable: entries default `nullable=false`; setting a null value into a non-nullable entry throws at build time (`RECORD_NULLABLE_CHECK` toggle). Legacy `JsonObject` records (JSON-P) still accepted by runtime but Studio/Cloud expect `Record`. |
| Context / errors | `RuntimeContext`/`RuntimeContextHolder` (`api.context`), `ComponentException(ErrorOrigin, message)`, `DiscoverSchemaException` | Throw `ComponentException` with origin `USER`/`BACKEND`/`UNKNOWN` for proper reporting. |
| Meta | `@Documentation("...")` (feeds `documentation.adoc` and tooltips), `@Internal`, `@Partial` | `validateDocumentation` requires `@Documentation` on components and options. |

### Testing

```java
// JUnit 5
@WithComponents("com.acme.mycomp")              // package to scan (+ isolatedPackages)
class MyInputTest {
  @Injected private BaseComponentsHandler handler;   // or ComponentsHandler
  @Test void readsRows() {
    final MyDataset ds = ...;
    final String cfg = configurationByExample().forInstance(ds).configured().toQueryString(); // SimpleFactory
    Job.components()
       .component("in", "MyFamily://Input?" + cfg)
       .component("out", "test://collector")
       .connections().from("in").to("out")
       .build().run();
    final List<Record> rows = handler.getCollectedData(Record.class);
    assertEquals(3, rows.size());
  }
}
// JUnit 4: @ClassRule public static final SimpleComponentRule COMPONENTS = new SimpleComponentRule("com.acme.mycomp");
// Test components: "test://emitter" (feed with handler.setInputData(list)), "test://collector".
// Job DSL signatures (component-runtime-manager 1.95.3): Job.components().component(id, uri)...connections().from(id[,branch]).to(id[,branch]).build().property(k,v).run()
// Handler helpers: createMapper(Class, config), createProcessor(Class, config), collectAsList(Class, mapper[, max]),
//   collect(Class, mapper, maxRecords[, concurrency]), findService(Class), injectServices(obj), resetState().
// Environments: @Environment(DirectRunnerEnvironment.class) / SparkRunnerEnvironment / FlinkRunnerEnvironment (+ @EnvironmentConfiguration) run the same test on Beam.
// Secrets in tests: @WithMavenServers + @DecryptedServer("server-id") reads ~/.m2/settings.xml.
```

### Studio / Cloud integration

| Topic | Detail |
|---|---|
| Install in Studio | (a) `deploy-in-studio` / `.car studio-deploy`: copies to `<studio>/configuration/.m2` (or `talend.studio.m2.repo` / `TALEND_STUDIO_MAVEN_HOME`), appends `component.java.coordinates=<groupId>:<artifactId>:<version>` (comma list) in `configuration/config.ini`; (b) Studio Preferences > Talend > Component Kit? / "Talend Component Kit" page: set a "Components registry"/server; (c) 8.0 Feature Manager / "Install from Component ARchive" via `talend.component.server.component.registry`-style settings (names (unverified)). Restart Studio; component appears under its `@Components` family in the Palette. |
| Registry file keys | `config.ini`: `component.java.coordinates` (installed TCK components), `component.java.registry` (path to a properties registry) (unverified exact), `talend.component.server.*` for a remote component server. |
| Re-deploy | A different version of the same artifact: Studio refuses (`A different version ... is already installed`); remove the old coordinate from `config.ini` and the m2 copy, or use `-Dtalend.component.enforceDeployment=true` (reported unreliable). |
| Cloud / Pipeline Designer | Components run in `component-server` on Remote Engine Gen2; upload the `.car` via TMC > Processing/Engines > "Connectors"/Custom components (name varies) or `deploy-to-nexus` + engine `component.server.extensions`/`COMPONENT_SERVER_EXTENSIONS` (literal env in CarMain) pointing to the Nexus repo. Beam-based: inputs must implement `@PartitionMapper` (not just `@Emitter`) for parallel reads. |
| Migration | `@Version(n, migrationHandler=MyMigration.class)` on the component; also on `@DataSet`/`@DataStore` classes. Old jobs store the version; on open the handler maps old keys. Never rename `@Option` fields without a handler. |
| Legacy difference | javajet: template-generated Java, XML descriptor, per-component code; TCK: compiled Java, generated UI, shared datastore/dataset metadata (Studio Metadata > "Talend Component Kit" entries when `@DataStore`/`@DataSet` exist), same jar runs in Studio, Cloud and Beam. TCK components cannot use Studio-specific features like dynamic schema columns (`Dynamic` type) or `tMap`-style lookups. |

---

## 5. Legacy javajet components

Still supported for Standard (DI) Jobs in Studio 7.x and 8.0 (Studio 8 ships them as the bulk of the palette). Install
custom ones via Preferences > Talend > Components > "User component folder" (Studio copies them into the Palette on
restart; in 8.0 also "Install external components" from Feature Manager). Talend Exchange (community sharing) is sunset.

```text
tMyComp/
  tMyComp_java.xml            descriptor
  tMyComp_begin.javajet       generated before the row loop (open connections, headers)
  tMyComp_main.javajet        generated per row (inside the input's loop)
  tMyComp_end.javajet         after the loop (close, NB_LINE)
  tMyComp_messages.properties  LONG_NAME, HELP, PARAMETER labels (`PARAM.NAME=Label`, `HELP=org.talend.help.tMyComp`)
  tMyComp_icon32.png          32x32 (also _icon16.png optional)
  lib/*.jar                   optional embedded jars (prefer MODULE in <IMPORTS>)
```

```xml
<COMPONENT>
  <HEADER PLATEFORM="ALL" SERIAL="" VERSION="0.102" STATUS="ALPHA"
          COMPATIBILITY="ALL" AUTHOR="acme" RELEASE_DATE="20240101A"
          STARTABLE="true" DATA_AUTO_PROPAGATE="false" HAS_CONDITIONAL_OUTPUTS="false"
          PARTITIONING="AUTO" LOG4J_ENABLED="true" SCHEMA_AUTO_PROPAGATE="true">
    <SIGNATURE/>
  </HEADER>
  <FAMILIES><FAMILY>Acme/Files</FAMILY></FAMILIES>
  <DOCUMENTATION><URL/></DOCUMENTATION>
  <CONNECTORS>
    <CONNECTOR CTYPE="FLOW" MAX_INPUT="1" MAX_OUTPUT="1"/>      <!-- MIN_INPUT, MAX_INPUT, MIN_OUTPUT, MAX_OUTPUT -->
    <CONNECTOR CTYPE="REJECT" MAX_OUTPUT="1"/>                   <!-- CTYPE: FLOW, REJECT, ITERATE, SUBJOB_OK, SUBJOB_ERROR, COMPONENT_OK, COMPONENT_ERROR, RUN_IF, LOOKUP, MERGE, TABLE -->
    <CONNECTOR CTYPE="ITERATE" MAX_OUTPUT="1" MAX_INPUT="1"/>
    <CONNECTOR CTYPE="SUBJOB_OK" MAX_INPUT="1"/>
    <CONNECTOR CTYPE="SUBJOB_ERROR" MAX_INPUT="1"/>
    <CONNECTOR CTYPE="COMPONENT_OK"/>
    <CONNECTOR CTYPE="COMPONENT_ERROR"/>
    <CONNECTOR CTYPE="RUN_IF"/>
  </CONNECTORS>
  <PARAMETERS>
    <PARAMETER NAME="PROPERTY" FIELD="PROPERTY_TYPE" SHOW="true" NUM_ROW="10" REPOSITORY_VALUE="DATABASE:MYSQL"/>
    <PARAMETER NAME="SCHEMA" FIELD="SCHEMA_TYPE" REQUIRED="true" NUM_ROW="20"/>
    <PARAMETER NAME="FILENAME" FIELD="FILE" REQUIRED="true" NUM_ROW="30" REPOSITORY_VALUE="FILEPATH">
      <DEFAULT>"/tmp/in.csv"</DEFAULT>
    </PARAMETER>
    <PARAMETER NAME="MODE" FIELD="CLOSED_LIST" NUM_ROW="40">
      <ITEMS DEFAULT="FAST"><ITEM NAME="FAST" VALUE="FAST"/><ITEM NAME="SAFE" VALUE="SAFE"/></ITEMS>
    </PARAMETER>
    <PARAMETER NAME="USE_AUTH" FIELD="CHECK" NUM_ROW="50"><DEFAULT>false</DEFAULT></PARAMETER>
    <PARAMETER NAME="PASS" FIELD="PASSWORD" NUM_ROW="50" SHOW_IF="(USE_AUTH == 'true')"><DEFAULT>""</DEFAULT></PARAMETER>
    <PARAMETER NAME="MAPPING" FIELD="TABLE" NUM_ROW="60" NB_LINES="5">
      <ITEMS><ITEM NAME="SCHEMA_COLUMN" FIELD="COLUMN_LIST"/><ITEM NAME="EXPR" FIELD="TEXT"/><ITEM NAME="ON" FIELD="CHECK"/></ITEMS>
    </PARAMETER>
    <PARAMETER NAME="CODE" FIELD="MEMO_JAVA" NUM_ROW="70" NB_LINES="10"/>
    <PARAMETER NAME="DIE_ON_ERROR" FIELD="CHECK" NUM_ROW="80"><DEFAULT>true</DEFAULT></PARAMETER>
  </PARAMETERS>
  <ADVANCED_PARAMETERS>
    <PARAMETER NAME="TSTATCATCHER_STATS" FIELD="CHECK" NUM_ROW="100"><DEFAULT>false</DEFAULT></PARAMETER>
  </ADVANCED_PARAMETERS>
  <CODEGENERATION>
    <IMPORTS>
      <IMPORT NAME="commons-csv" MODULE="commons-csv-1.10.0.jar" MVN="mvn:org.apache.commons/commons-csv/1.10.0" REQUIRED="true"/>
    </IMPORTS>
  </CODEGENERATION>
  <RETURNS>
    <RETURN NAME="NB_LINE" TYPE="id_Integer" AVAILABILITY="AFTER"/>     <!-- AVAILABILITY: AFTER | FLOW -->
    <RETURN NAME="ERROR_MESSAGE" TYPE="id_String" AVAILABILITY="AFTER"/>
  </RETURNS>
</COMPONENT>
```

| FIELD value | Widget | Value in template |
|---|---|---|
| `TEXT` | string expression (quoted Java) | `"abc"` or `context.x` (code, not literal) |
| `CHECK` | checkbox | `"true"`/`"false"` strings |
| `CLOSED_LIST` | combo from `<ITEMS>` | `VALUE` of chosen item |
| `OPENED_LIST` | editable combo | |
| `TABLE` | grid; columns from nested `<ITEMS>` | `ElementParameterParser.getTableValues(node, "__MAPPING__")` -> `List<Map<String,String>>` |
| `SCHEMA_TYPE` / `SCHEMA_REFERENCE` | schema editor | via `node.getMetadataList()` |
| `MEMO` / `MEMO_JAVA` / `MEMO_SQL` / `MEMO_PERL` | multi-line | raw text |
| `PASSWORD` | masked; encrypted in .item | `ElementParameterParser.getPasswordValue(node, "__PASS__")` |
| `FILE` / `DIRECTORY` | browse | quoted path expression |
| `PROPERTY_TYPE` | Built-in/Repository selector | `REPOSITORY_VALUE` filters metadata type |
| `COMPONENT_LIST` | combo of other components (`FILTER="tMysqlConnection"`) | `__CONNECTION__` unique name |
| `CONNECTION_LIST`, `COLUMN_LIST`, `PREV_COLUMN_LIST`, `LOOKUP_COLUMN_LIST`, `CONTEXT_PARAM_NAME_LIST`, `ENCODING_TYPE`, `DBTYPE_LIST`, `TECHNICAL`, `LABEL`, `IMAGE`, `COLOR`, `VERSION`, `PROCESS_TYPE` (tRunJob job picker), `JAVA_COMMAND`, `MODULE_LIST`, `RADIO`, `AS400_CHECK`, `TNS_EDITOR`, `DBTABLE` | misc | `TECHNICAL` = hidden stored value |

Conditions: `SHOW_IF`, `HIDE_IF`, `REQUIRED_IF`, `READONLY_IF`, `NOT_SHOW_IF`, `NOT_READONLY_IF` with expressions like
`(USE_AUTH == 'true') and (MODE == 'SAFE')`, `(SCHEMA.TYPE == 'id_String')`, `#LINK@NODE.CONNECTOR.PARAM == 'x'`.
Attributes: `NUM_ROW` (vertical position), `SHOW`, `REQUIRED`, `READONLY`, `REPOSITORY_VALUE`, `NB_LINES`,
`CONTEXT="..."`, `GROUP` (collapsible group), `DYNAMIC_SETTINGS`.

```java
<%@ jet
imports="
  org.talend.core.model.process.INode
  org.talend.core.model.process.ElementParameterParser
  org.talend.core.model.metadata.IMetadataTable
  org.talend.core.model.metadata.IMetadataColumn
  org.talend.core.model.process.IConnection
  org.talend.core.model.process.IConnectionCategory
  org.talend.designer.codegen.config.CodeGeneratorArgument
  java.util.List
  java.util.Map
"
%>
<%
  CodeGeneratorArgument codeGenArgument = (CodeGeneratorArgument) argument;
  INode node = (INode) codeGenArgument.getArgument();
  String cid = node.getUniqueName();                                  // e.g. tMyComp_1
  String filename = ElementParameterParser.getValue(node, "__FILENAME__");   // quoted expression as typed
  boolean dieOnError = "true".equals(ElementParameterParser.getValue(node, "__DIE_ON_ERROR__"));
  List<Map<String,String>> mapping = (List<Map<String,String>>) ElementParameterParser.getObjectValue(node, "__MAPPING__");
  List<IMetadataTable> metadatas = node.getMetadataList();
  List<? extends IConnection> outs = node.getOutgoingSortedConnections();
  List<? extends IConnection> ins = node.getIncomingConnections();
  if (metadatas != null && metadatas.size() > 0) {
    IMetadataTable metadata = metadatas.get(0);
    List<IMetadataColumn> columns = metadata.getListColumns();
%>
  int nb_line_<%=cid%> = 0;
  java.io.BufferedReader reader_<%=cid%> = new java.io.BufferedReader(new java.io.FileReader(<%=filename%>));
  globalMap.put("<%=cid%>_READER", reader_<%=cid%>);
<%   for (IConnection conn : outs) { if (conn.getLineStyle().hasConnectionCategory(IConnectionCategory.DATA)) { %>
       // in _main: <%=conn.getName()%>.<%=columns.get(0).getLabel()%> = value;
<%   } }
  }
%>
```

Rules: `__NAME__` placeholders are resolved only for parameters declared in the XML (undeclared -> literal string);
`cid` suffixes every generated variable to keep uniqueness; store cross-template objects in `globalMap`
(`globalMap.get("cid_READER")` in `_end`); `end` must set returns: `globalMap.put("<%=cid%>_NB_LINE", nb_line_<%=cid%>);`.
Wrong `imports` or compile errors appear in Studio as "Error in component template" / the Palette push fails for
invalid XML (`Right-click XML > Validate Component XML` in the component project). Jars listed in `<IMPORT>` must be
installed (Modules view) or the job shows "Module not installed" and will not compile.

---

## 6. Running exported Jobs from Java

Build Job (Studio) or `talend-ci-builder` produce `<Job>_<ver>.zip` containing `<Job>/<Job>_run.sh|.bat`,
`<Job>/lib/*.jar` (dependencies + child job jars), `<Job>/<job>_<ver>.jar` (the job jar; name lower-cased in some
versions), `<Job>/<project>/<job>_<ver>/contexts/*.properties`, `jobInfo.properties` (see artifact-formats.md). The
job class is in the job jar.

| Element | Value |
|---|---|
| Class name | `<projectname_lowercase>.<jobname_lowercase>_<major>_<minor>.<JobName>` e.g. `myproj.loadcustomers_0_1.LoadCustomers` |
| Interface | `routines.system.api.TalendJob` (in `routines` jar on the classpath; also `TalendMRJob`/`TalendESBJob` variants) |
| Entry points | `public static void main(String[] args)` (calls `runJobInTOS`, then `System.exit(exitCode)`); `public int runJobInTOS(String[] args)` returns exit code (0 ok, 1 generic error, 4 Java exception default `tDie` code 4, custom `tDie` code); `public String[][] runJob(String[] args)` runs the job and returns the content of the `tBufferOutput` buffer (`String[][]`), or an empty/null array when the job has no tBufferOutput (community: null-check it); `public boolean hastBufferOutputComponent()` |
| Other methods | `public String getStatus()` (`""` while/after normal end, `"end"` / `"failure"` set by error handling, unverified exact), `public Integer errorCode` field (unverified getter), `public void setDataSources(java.util.Map<String, javax.sql.DataSource> dataSources)` (JNDI/container datasources for `tXxxConnection` "Specify a data source alias"), `public void setDataSourceReferences(java.util.List serviceReferences)` (ESB/OSGi), `public ContextProperties getContext()`? (unverified), `public java.util.Map<String,Object> globalMap` field, `public String jobName`, `public String projectName`, `public String jobVersion`, `public String contextStr` |
| Args | `--context=<name>`, `--context_param <key>=<value>` (repeat; also `--context_param key=value` single token form), `--father_pid=`, `--root_pid=`, `--pid=`, `--stat_port=`, `--log4jLevel=INFO`, `--context_type`? ; parsing is in `runJobInTOS` via `readParams`/`parseCommandLine` (unverified names). Values with spaces must be one arg (no shell splitting). |
| Classpath | all `lib/*.jar` + the job jar(s) + child job jars (tRunJob children are separate jars in `lib/`). Java version must match the Studio build target (8.0 default Java 11, optional 17; 7.3 Java 8/11); otherwise `UnsupportedClassVersionError`. |

```java
import myproj.loadcustomers_0_1.LoadCustomers;
LoadCustomers job = new LoadCustomers();                 // NEW instance per run: globalMap is an instance field, not reset otherwise
job.setDataSources(Map.of("DWH", dataSource));           // if the job uses data source aliases
int rc = job.runJobInTOS(new String[]{"--context=PROD", "--context_param", "load_date=2024-05-01"});
String[][] rows = job.runJob(new String[]{"--context=PROD"});  // rows[i][j] = tBufferOutput column j as String; may be null/empty
System.out.println(job.getStatus() + " rc=" + rc);
```

Caveats: the generated class keeps static state in routines (`Numeric.sequence("s1", 1, 1)` counters are static maps,
`TalendDate` formats cache) -> sequences continue across runs in one JVM unless `Numeric.resetSequence`/`removeSequence`;
`System.exit` is only in `main`, so use `runJobInTOS`; log4j2 config comes from `log4j2.xml` inside the job jar (override
with `-Dlog4j2.configurationFile`); contexts are loaded from `contexts/<ctx>.properties` on the classpath (`ContextProperties`);
`tRunJob` children started "as independent process" spawn a JVM via the `java` on PATH; `tBufferOutput` only works in-JVM.

Other embedding routes: Spring/Camel route `cTalendJob` (Mediation, runs the job class in-route, see esb-routes-services.md);
Job as REST/SOAP service (`tRESTRequest`/`tESBProviderRequest`, deployed to Talend Runtime); legacy TOS 4.x/5.x "Export as
Webservice" produced an Axis WAR exposing `http://host/<Job>/services/<Job>?method=runJob&args=--context_param%20x=1`
(dead since 6.x). JobServer (port 8000/8001) has a private protocol used by TAC only (no public API); automate via TAC
MetaServlet or run the launcher.

---

## 7. Other product APIs

| Product | Base / key endpoints | Auth | Notes |
|---|---|---|---|
| Talend MDM Server (7.x/8.0, Tomcat 8180) | `http://<mdm>:8180/talendmdm/services/rest/` : data: `POST /data/{container}` (create record, XML or JSON body; existing id -> update; `Location` header = id; 8.0 marks deprecated), `PUT /data/{container}/query?container=MASTER|STAGING` (body = MDM JSON query language; `ignoreCase` param), `GET /data/{container}/{type}/{id}`, `DELETE /data/{container}/{type}/{id}`, `POST /data/{container}/batch` (batch create/update), `PATCH`/`PUT .../bulk`? (bulk partial update, 7.2+), `DELETE .../query` (delete by query); system: `/system/models`, `/system/containers`, `/system/roles`, `/system/users`? , `/system/views`; tasks/workflow: `/tasks`? (paths other than data CRUD (unverified)) | HTTP Basic (MDM user) | WADL at `.../services/rest?_wadl` (CXF). Data REST APIs are subscription-only (community). Studio components `tMDMRestInput` paginate by batch size. Legacy SOAP `/talendmdm/services/soap?wsdl`. UI: `/talendmdm/ui`. See data-quality-governance.md. |
| Talend Data Stewardship (on-prem 7.x/8.0) | `https://<tds>/data-stewardship/api/v1/campaigns`, `/campaigns/{id}`, `/tasks`, `/tasks/search` (POST, query DSL), `/tasks/{id}` (PATCH state/assign), `/campaigns/{id}/tasks`, `/users` (paths (unverified)); Swagger UI `/data-stewardship/swagger-ui.html` | Basic or IAM OIDC bearer; cloud: TMC PAT via `api.<region>.cloud.talend.com/data-stewardship/...`? (unverified) | Studio components `tDataStewardshipTaskInput/Output/Delete` wrap this API. |
| Talend Data Preparation (on-prem) | `http://<dataprep>:9999/api/preparations` (list/create), `/api/preparations/{id}/actions` (add step), `/api/datasets` (POST multipart or `?name=`), `/api/datasets/{id}` , `/api/export?preparationId=&exportType=CSV`, `/api/transform/...`, `/api/version`, `/api/types` (semantic types) (unverified exact) | Basic / IAM; cloud: TMC token | Components `tDataprepRun` run a preparation on a flow. Semantic types = Talend Dictionary Service (TDS/`dictionary-service`), API `.../api/v1/categories`? (unverified). |
| Talend Data Catalog (TDC, ex-MetaIntegration MM) | `http://<tdc>:11480/MM/REST/...` ; REST API docs `http://<tdc>:11480/MM/REST-API.html` (unverified); import bridges via `MIMB` (Meta Integration Model Bridge) CLI `MimbClient`/`mimb.sh -import ...`; Talend Studio metadata harvested by the "Talend Data Integration" bridge | Basic / token (`/MM/REST/v1/users/login`?) | Default ports 11480 HTTP, 11443 HTTPS. See data-quality-governance.md. |
| Talend Dictionary Service | `http://<tds>:8187/api/...`? (unverified) | | Semantic categories shared by Data Prep/Data Stewardship/Data Quality (`tDataStewardship...`, `Semantic Discovery`). |
| Talend Cloud Data Inventory / Trust Score | public API presence (unverified); UI only for most operations | TMC token | Trust Score = validity + completeness + popularity + usage; see data-quality-governance.md. |
| API Designer | Export OAS 2/3 JSON/YAML, RAML (UI); `GET /apis/designer/...`? (unverified) | TMC token | Imports to Studio `tRESTRequest` via "Import API definition". See esb-routes-services.md. |
| API Tester (Cloud) | Maven plugin (section 1.8); Chrome extension project `.json` export | account/instance ids | |
| Pipeline Designer | tasks/executions via TMC API (artifact type pipeline); design API (unverified) | TMC token | Remote Engine Gen2 exposes no public REST. |
| Stitch (Talend acquisition) | `https://api.stitchdata.com/v4/sources`, `/v4/sources/{id}/streams`, `/v4/destinations`, `/v4/sources/{id}/sync` (start replication), Connect API `/v3/clients` for partner-created accounts (partial, unverified) | `Authorization: Bearer <stitch api token>` | Separate product; not reachable through TMC tokens. |
| Talend Open Studio Exchange | `exchange.talend.com` API | | Dead (service shut down); Studio "Exchange" view removed in 7.x/8.0. |
| Talend Runtime (Karaf) JMX | `service:jmx:rmi:///jndi/rmi://<host>:1099/karaf-trun` (`org.apache.karaf:type=bundle,...`), Talend ESB `org.talend.esb:...` MBeans; Job statistics via `--stat_port` to tStatCatcher/AMC | JMX creds `karaf/karaf` default | See esb-routes-services.md. |
| Remote Engine (Gen1) | No public REST; local `jolokia` optional; pairing by pre-authorized key; `remote-engine.sh` CLI | | deployment-runtime.md. |
| LogServer (6.x/7.x) | Elasticsearch 5.x on `:9200`; indices `talendlogs-*`? ; Kibana `:5601` | | 8.0 TAC drops LogServer bundling. |
| Activity Monitoring Console (AMC) | DB tables `tlogcatcher`, `tstatcatcher`, `tflowmetercatcher` (names configurable) | | orchestration-logging.md owns details. |

---

## 8. Routines, beans and generated-code API

| Surface | Detail |
|---|---|
| System routines (`routines` jar, package `routines`) | `TalendDate` (`getCurrentDate()`, `parseDate(pattern, s)`, `formatDate(pattern, d)`, `addDate`, `diffDate`, `compareDate`, `TO_DATE`...), `TalendString` (`replaceSpecialCharForXML`, `talendTrim`, `getAsciiRandomString`, `removeAccents`), `StringHandling` (`UPCASE`, `DOWNCASE`, `LEN`, `INDEX`, `LEFT`, `RIGHT`, `CHANGE`, `EREPLACE`, `IS_ALPHA`, `TRIM`...), `Numeric` (`sequence(name, start, step)`, `random(min,max)`, `convertImpliedDecimalFormat`, `resetSequence`, `removeSequence`), `Mathematical`, `Relational` (`ISNULL`, `NOT`, `AND`...), `DataOperation`, `TalendDataGenerator` (`getFirstName()`, `getUsCity()`...), `TalendStringUtil`, `SQLike`, `DQTechnical`, `Defaults`. Callable from tMap/tJava as `routines.TalendDate.getDate("CCYY-MM-DD")` or just `TalendDate.getDate(...)` (imported). Details: tmap-expressions.md. |
| User routines | Repository > Code > Routines: `public class MyRoutine { public static String f(String s) {...} }` under `routines` package; add jars via "Edit Routine Libraries". Available in every job of the project (Studio 8: "Global routines" vs "Inner routines" per job). |
| `routines.system.*` | `ContextProperties extends java.util.Properties` (`context`): typed fields `context.load_date` generated per variable plus `context.getProperty("load_date")`, `context.setContextType(...)`, `context.synchronizeContext()` (copy Properties -> typed fields after `context.put`); `ResumeUtil resumeUtil` (checkpoint/recovery logging: `resumeUtil.addLog("CHECKPOINT", ...)`, `initCommonInfo`), `RunStat runStat` (`runStat.updateStatOnConnection("row1", 0|1|2, nbRows)` feeds Traces/statistics via `--stat_port`), `TalendJob` interface, `TalendException`/`TDieException`/`ControlException`, `ParserUtils` (`parseTo_Integer`, `parseTo_Date(s, pattern)`, `parseTo_BigDecimal`), `FormatterUtils` (`format_Date(d, pattern)`, `format_Number`), `RoutinesUtils`? , `JobStructureCatcherUtils` (tStatCatcher/tFlowMeterCatcher plumbing), `LogCatcherUtils`, `TalendJobLog`? (unverified exact), `GlobalResource`, `Dynamic`/`DynamicMetadata` (dynamic schema columns), `api.TalendJob`, `api.TalendMRJob`, `api.TalendESBJob`, `api.TalendESBRoute`. |
| `globalMap` | `java.util.Map<String,Object>` instance field on the job; component results `((Integer) globalMap.get("tFileInputDelimited_1_NB_LINE"))`, connection objects `globalMap.get("conn_tMysqlConnection_1")`, user values `globalMap.put("k", v)` via tSetGlobalVar; child jobs have their own unless tRunJob "Transmit whole context". Shared static map via routine when needed. |
| tJava / tJavaRow / tJavaFlex | Direct access to `context`, `globalMap`, `row1.col`, `output_row.col`, `routines.*`, the component's `cid` vars (`nb_line_tJavaRow_1`), `runStat`, `resumeUtil`, `log` (log4j2 `Logger log`), `jobName`, `jobVersion`, `projectName`, `pid`, `rootPid`, `fatherPid`, `errorCode`, `status`. `tJava` basic settings "Import" field for imports. |
| Beans (Mediation/Routes) | Repository > Code > Beans: `public class MyBean { @Handler public String process(String body, Exchange ex) {...} }` (Camel `org.apache.camel.Handler`), used by `cBean`/`cBeanRegister`/`cProcessor` (`exchange.getIn().getBody(String.class)`); routes generated as `RouteBuilder`. Details esb-routes-services.md. |
| Job script (Jobscript API) | Text DSL (`addComponent {...}`, `addConnection {...}`) imported by Studio or TAC "Job Creation API" + CommandLine `generateJob`; artifact-formats.md. |
| Metadata Bridge / Repository Manager | Repository Manager tool (7.x) migrates items between SVN/Git projects; no public API. |

---

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` on every TMC call although the PAT is fresh | Wrong regional host (token minted on `eu`, calls to `api.us.cloud.talend.com`) or missing `Bearer ` prefix | Use the host matching the account's region; header `Authorization: Bearer <token>`; test with `GET /orchestration/environments`. |
| `403 Forbidden` on `POST /processing/executions` but `GET` works | Token owner / service account lacks `Engines - Use` (`TMC_ENGINE_USE`) or workspace `Execute` right; environment not shared | Grant role with TMC_ENGINE_USE + workspace Execute; for service accounts also `Operations` permissions. 403 is a permission problem, never a token problem. |
| Service-account calls start failing after ~30 min | Token lifetime 30 min | Re-run `POST /security/oauth/token` on 401, cache until `expires_in - 60s`. |
| Script written for `/tmc/v2.0/tasks` returns 404/410 | Public API v1.x/v2.0/v2.1 removed; tasks live under `/executables/tasks` (v2.0+) and `/orchestration/executables/tasks` | Migrate to family paths; check `swagger-ui.html` for the current version. |
| Poller never exits | Task executions return `EXECUTION_SUCCESS` (failures `EXECUTION_FAILED`, `DEPLOY_FAILED`, `EXECUTION_REJECTED`, `EXECUTION_TERMINATED`, `EXECUTION_TERMINATED_TIMEOUT`) while plan executions return lower-case `execution_successful` / `execution_failed`; a poller matching only one spelling or one case never exits | Upper-case the value and accept both `EXECUTION_SUCCESS` and `EXECUTION_SUCCESSFUL`; treat anything outside `DISPATCHING/DEPLOYING/EXECUTING/TERMINATING` as terminal. |
| `EXECUTION_REJECTED` right after `POST /executions` | Previous run still active and `parallelExecutionAllowed=false`, engine paused/unpaired, or licence token limit | Wait for the previous execution, enable parallel in run-config, check engine status. |
| `PUT /executables/tasks/{id}` drops parameters/connections | PUT is a full replace; partial body resets omitted fields | GET, modify, PUT the entire object (name, workspaceId, artifact, parameters, connections, resources, autoUpgradeInfo). |
| `PUT run-config` 400 on `cronExpression` | TMC cron minimum granularity 5 min (`*/5`), timezone must be IANA; Quartz vs 5-field format mismatch | Use a 5-minute-or-coarser expression; copy the format from an existing run-config GET. |
| Webhook URL stops working | Webhook deleted/re-created (new id + secret), or trigger type changed from WEBHOOK | Re-fetch via `GET .../webhooks`; keep the secret out of logs. |
| MetaServlet returns HTML login page or `returnCode` 5 / "JSON parse" | Base64 wrapped at 76 chars (`base64` default) or `+`/`/`/`=` not URL-encoded in the GET URL | `base64 -w0`, URL-encode, or use `MetaServletCaller.sh --json-params`. |
| MetaServlet `returnCode` 3 with correct password | `authPass` contains `"`/`\`/`&` not JSON-escaped, or user lacks Operation Manager role | Escape JSON, use `--json-file`, check role; prefer HTTPS so the password is not in clear in proxy logs. |
| `getTaskExecutionStatus` returns nothing useful / unknown id | Passed `taskId` or Job Conductor execution id instead of `execRequestId` from `runTask` | Keep `execRequestId` string from the async `runTask` answer. |
| `runTask` `returnCode` 30 | Task not generated/deployed, server down, task already running | `requestGenerate` + `requestDeploy`, then `runTask`; or check `getTaskStatus`. |
| CommandLine `startServer` fails: "workspace is in use" / `.metadata/.lock` | Another CommandLine/Studio on the same `-data`, or crashed process left the lock | One workspace per instance; delete `commandline-workspace/.metadata/.lock` after confirming no process. |
| `scriptFile` exportJob produces no archive, window closes | Missing `logoffProject`/`quit`, wrong `-jv` (version must exist), or branch not given for Git project | Add `-br <branch>`, exact `-jv`, end with `logoffProject` + `quit`; run in `shell` mode first to see errors. |
| TAC Generate stays `GENERATING` | CommandLine not reachable (port 8002), version mismatch TAC/CommandLine, licence missing | Check TAC > Servers CommandLine config; align patch levels; read CommandLine workspace `.metadata/.log`. |
| TCK `mvn package` fails `validate`: "No display name for option ..." | `@Option` field without `<Family>.<cfgType>.<Name>.<field>._displayName` in `Messages.properties` | Add keys or `-Dtalend.validation.internationalization.autofix=true` once; keep option names stable. |
| `deploy-in-studio` `NoSuchFileException configuration/config.ini` | Studio never started (no config.ini) or wrong `studioHome` | Start Studio once, close it, pass `-Dtalend.component.studioHome` quoted. |
| Component not in Palette after `.car studio-deploy` | Studio was running during deploy, or an older version of the coordinate already in `config.ini` ("different version already installed") | Close Studio, remove old `component.java.coordinates` entry and `configuration/.m2` copy, redeploy, restart; check `workspace/.metadata/.log`. |
| TCK record build throws on `withString("col", null)` | Entry not `nullable` (default false) | `newEntryBuilder().withName("col").withType(STRING).withNullable(true)` or use `getOptional*` readers downstream. |
| Streaming input never ends in Studio / pipeline never finishes | `@PartitionMapper(infinite=true)` is for Pipeline Designer streaming; Studio DI runs batch | Use `infinite=false` for Studio, or set `stoppable=true` + max records/duration options. |
| javajet component shows literal `__PARAM__` in generated code | Placeholder not declared as `<PARAMETER NAME="PARAM">` in `_java.xml` (also for ADVANCED) | Declare it; names are matched exactly (upper case convention). |
| Job with custom component: "Module not installed" / compile error | Jar in `<IMPORT MODULE=...>` not resolvable (not in Studio m2, no `MVN` coordinate) | Install via Modules view or drop jar under component folder / set `MVN` + `UrlPath`; Studio 8 needs the jar in `configuration/.m2`. |
| `runJob()` returns null / `ArrayIndexOutOfBounds` reading results | Job has no `tBufferOutput` or it was in a child job running as separate process | Check `hastBufferOutputComponent()`; put tBufferOutput in the same JVM job; null-check. |
| `UnsupportedClassVersionError` when embedding the job jar | Job built with Studio target Java 11/17, host JVM older | Run on the Studio's target JDK (8.0: 11 default, 17 optional) or rebuild with matching "Java version" in project settings. |
| Second run of the same job object returns stale `globalMap` values / sequences continue | `globalMap` is an instance field never cleared; `Numeric.sequence` uses static maps per JVM | `new JobClass()` per run; call `Numeric.removeSequence(name)` or restart JVM; never share one instance across threads. |
| `--context_param x=some value` ignored | Shell split the value; parser takes `key=value` as one argument | Quote: `"--context_param" "x=some value"`; in Java pass as one array element. |
| MDM REST `404` on `/talendmdm/services/rest/data/...` | Wrong port (8180 not 8080), container/type name casing, or Open Source edition (data REST subscription-only) | Use `http://host:8180/talendmdm/services/rest/...`; check `?_wadl`; confirm edition. |

## Sources

https://help.qlik.com/talend/en-US/api-user-guide/Cloud/using-service-accounts-api
https://help.qlik.com/talend/en-US/api-user-guide/Cloud/generate-service-account-token
https://help.qlik.com/talend/en-US/api-user-guide/Cloud/create-schedule
https://help.qlik.com/talend/en-US/api-user-guide/Cloud/error-handling
https://help.qlik.com/talend/en-US/release-notes/8.0/r2022-05-service-account
https://help.qlik.com/talend/en-US/archive-release-notes/8.0/r2022-02-api-orchestration
https://help.qlik.com/talend/en-US/release-notes/8.0/r2022-05-api-event-search
https://help.qlik.com/talend/en-US/release-notes/7.3/r2020-02-talend-cloud-management-console
https://help.qlik.com/talend/en-US/release-notes/7.3/r2020-06-talend-cloud-management-console
https://help.qlik.com/talend/en-US/release-notes/7.3/r2021-03-talend-cloud-management-console
https://help.qlik.com/talend/en-US/release-notes/7.3/r2021-08-talend-cloud-management-console
https://help.qlik.com/talend/en-US/management-console-user-guide/Cloud/cloud-access-token
https://help.qlik.com/talend/en-US/management-console-user-guide/Cloud/configuring-cron-trigger-for-pipeline-tasks
https://help.qlik.com/talend/en-US/components/8.0/mediation-apache-cxf/obtaining-a-jwt-from-talend-cloud-iam
https://talend.qlik.dev/apis/oauth/2021-03/
https://talend.qlik.dev/apis/service-accounts/2021-03/
https://talend.qlik.dev/apis/processing/2021-03/
https://talend.qlik.dev/apis/orchestration/2021-03/
https://talend.qlik.dev/apis/execution-history-search/2021-03/
https://talend.qlik.dev/use-cases/service-accounts/generating-service-account-token/
https://talend.qlik.dev/use-cases/service-accounts/using-service-account-to-run-tasks/
https://talend.qlik.dev/use-cases/creating-tasks/create-task-with-connections/
https://talend.qlik.dev/use-cases/multiple-triggers/use-schedule-to-organize-task-runs/create-schedule/
https://community.qlik.com/t5/Administering-and-Monitoring/Retrieve-the-status-execution-for-a-Task-via-Tmc-Public-Api/m-p/2354329/highlight/true
https://community.qlik.com/t5/Deployment/TMC-Public-API-Status-Explanation-Meaning/m-p/2317036
https://community.qlik.com/t5/Deployment/Cloud-Task-pointing-to-previous-version-of-Artifact/m-p/2321661
https://community.qlik.com/t5/Design-and-Development/How-to-kill-Talend-job-by-Using-the-Talend-Cloud-Management/m-p/2352048
https://community.qlik.com/t5/Design-and-Development/Getting-quot-executable-quot-value-for-a-flow-running-in-Talend/td-p/2283559
https://docs.stonebranch.com/integrations/talend-cloud
https://help.qlik.com/talend/en-US/administration-center-api/8.0/metaservlet-api
https://help.qlik.com/talend/en-US/administration-center-api/8.0/metaservlet-commands
https://help.qlik.com/talend/r/en-US/8.0/administration-center-metaservlet-api
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/executing-a-task-and-returning-its-status-using-metaservlet
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/returning-status-of-task-executed-in-asynchronous-mode
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/returning-status-of-task-executed-in-synchronous-mode
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/how-to-add-cron-based-trigger
https://help.qlik.com/talend/en-US/data-integration-job-examples/8.0/calling-metaservlet-rest-web-service-to-execute-task
https://help.qlik.com/talend/en-US/data-integration-job-examples/7.3/configuring-components-for-calling-metaservlet-rest-web-service-to-execute-task
https://help.qlik.com/talend/en-US/data-integration-job-examples/7.3/configuring-routine
https://community.qlik.com/t5/Talend-Studio/Calling-a-Talend-Job-from-Web-browser-with-the-context-variables/m-p/2315055
https://community.qlik.com/t5/Talend-Studio/MetaServlet-runTask-mode-synchronous-failing/m-p/2317373/highlight/true
https://help.qlik.com/talend/fr-FR/commandline-api/7.3
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/building-job-using-commandline
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/generating-job-created-with-job-creation-api-using-commandline
https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/generating-job-using-talend-commandline
https://help.qlik.com/talend/fr-FR/administration-center-user-guide/7.3/executing-job-on-server-with-ssl-enabled-using-commandline
https://community.qlik.com/t5/Talend-Studio/Problem-with-running-commandline-in-script-mode/m-p/2371695/highlight/true
https://community.qlik.com/t5/Talend-Studio/Running-the-build-step-from-outside-of-the-Talend-ide/td-p/2371257
https://repo1.maven.org/maven2/org/talend/sdk/component/component-api/
https://repo1.maven.org/maven2/org/talend/sdk/component/talend-component-maven-plugin/
https://repo1.maven.org/maven2/org/talend/sdk/component/component-runtime-junit/
https://repo1.maven.org/maven2/org/talend/sdk/component/component-runtime-manager/
https://repo1.maven.org/maven2/org/talend/sdk/component/component-tools/
https://community.qlik.com/t5/Component-Development/Unable-to-deploy-Custom-Talend-Component-from-Intellij-to-Talend/td-p/2248004
https://community.qlik.com/t5/Component-Development/Talend-Component-Kit-Error-deploying-to-Studio/m-p/2248611/highlight/true
https://community.qlik.com/t5/Component-Development/Error-when-I-tried-to-deploy-component-with-Maven/m-p/2253441/highlight/true
https://community.qlik.com/t5/Component-Development/Tutorial-Talend-Component-Kit-5-Implementation-of-the-Partition/td-p/2249005
https://community.qlik.com/t5/Component-Development/How-to-get-parameter-values-from-talend-UI-to-service-java/td-p/2247364
https://community.qlik.com/t5/Talend-Studio/Questions-comparing-JET-with-Talend-Development-Kit/m-p/2248288
https://help.qlik.com/talend/en-US/remote-engine-gen2-quick-start-guide/Cloud/developing-your-connectors-or-processors
https://help.qlik.com/talend/r/ja-JP/8.0/develop-component-using-kit
https://jira.talendforge.org/browse/TCOMP-719
https://help.qlik.com/talend/en-US/what-is-a-component/8.0/xml-descriptor-file
https://help.qlik.com/talend/en-US/what-is-a-component/8.0/java-template-file
https://community.qlik.com/t5/Talend-Studio/Push-components-to-palette-failed-for-these-invalid-XML-files/td-p/2269298
https://community.qlik.com/t5/Design-and-Development/run-Talend-ETL-jobs-from-java-application/td-p/2296074
https://community.qlik.com/t5/Talend-Studio/Pass-values-from-parent-Job-to-child-using-tBufferOutput/m-p/2347069/highlight/true
https://community.qlik.com/t5/Talend-Studio/resolved-Passing-custom-object-through-parent-and-children-jobs/m-p/2349622/highlight/true
https://community.qlik.com/t5/Talend-Studio/Calling-job-from-an-external-Java-application-return-code/td-p/2217256
https://help.qlik.com/talend/en-US/components/7.3/buffer/tbufferoutput-standard-properties
https://help.qlik.com/talend/en-US/mdm-query-language/8.0/create-record
https://help.qlik.com/talend/en-US/mdm-query-language/7.3/get-records-by-query
https://help.qlik.com/talend/en-US/release-notes/7.2/mdm--new-features
https://community.qlik.com/t5/Talend-Studio/Working-with-data-container-using-REST-API/td-p/2375418
https://help.qlik.com/talend/en-US/components/7.3/mdm-data-processing/tmdmrestinput-standard-properties
