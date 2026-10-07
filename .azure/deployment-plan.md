# Azure deployment plan

Status: Deployed

## Target

- Subscription: ME-DIAx08652819-chiencchen-1 (`512e9bf5-6902-4817-b782-514dbd8cb5bd`)
- Tenant: `d6ccf307-5f7b-42fb-84c1-0cf3e2009159`
- Resource group: `rg-ipm-workshop-20261007` (new for this deployment).
- Region: `southeastasia` (user selected).
- Deployment: Reuse `deploy/azure.yaml` and its Bicep; provision missing Foundry prerequisites in the new resource group.

## Requirements and scope

- Mode: MODIFY; reuse existing deployment assets without rewriting application logic.
- User selected individual/workshop usage, low concurrency, and cost optimization.
- Deploy the main four-agent workflow as `qvn-ipm-review`.
- Create a new Foundry account, project, model deployment, and monitoring resources.
- Exclude Lab 5, AWS, GCP, AI Search, Teams publication, and Bot Service.
- Use Entra authentication and managed identities; disable account API-key authentication.
- Public service endpoints require authentication. No private endpoints are included.
- Global Standard model inference can be processed outside Singapore.

## Components and recipe

| Component | Technology | Path |
| --- | --- | --- |
| Four-agent workflow | Python 3.13, pinned Microsoft Agent Framework | `src/` |
| Hosted API | Responses protocol 2.0.0 | `deploy/agent.yaml` |
| Container | Python 3.13, uv, remote ACR build | `deploy/Dockerfile` |
| Existing infrastructure | Resource-group-scoped Bicep, ACR Basic and permissions | `deploy/infra/main.bicep` |

Recipe: AZD (Bicep) for existing container deployment, plus a separate prerequisite Bicep template.
Keep the existing infrastructure's "existing Foundry account/project" contract intact.

## Architecture

| Resource | Planned configuration |
| --- | --- |
| Foundry account | AIServices S0, system-assigned identity, project management enabled |
| Foundry project | `ipm-workshop`, system-assigned identity |
| Model | `gpt-4.1-mini`, version `2025-04-14`, GlobalStandard, 50 capacity units (50K TPM) |
| Hosted agent | `qvn-ipm-review`, 0.5 vCPU and 1 GiB per active session |
| Container Registry | Basic; existing template generates a unique name |
| Log Analytics | Pay-as-you-go, 30-day retention, low daily ingestion cap |
| Application Insights | Connected to the project; message-content capture remains disabled |
| Identity/RBAC | Required project/model access, deployment permissions, and ACR pull/build roles scoped to the new resources |

No Key Vault is needed for this keyless path because no application secrets are introduced.
The model is marked Legacy by the catalog but remains deployable; the catalog reports inference retirement on 2027-04-14.
Do not automatically upgrade pinned runtime packages or the model.

## Policy constraints

Subscription-level assignments returned three Microsoft Defender initiatives:
OpenSourceRelationalDatabasesProtectionSecurityCenter, SqlVmAndArcSqlServersProtection,
and DataProtectionSecurityCenter. No location restriction was present in the returned assignments.
Inherited policies are not yet fully evaluated; ARM validation/what-if must verify the proposed deployment.
The authenticated principal has Owner, User Access Administrator, and Foundry User access.
Do not change or reuse existing resources outside the new resource group.

## Provisioning limit checklist

Quota API probes for CognitiveServices, ContainerRegistry, OperationalInsights, and Insights returned BadRequest.
Use CognitiveServices regional usages and resource inventory as fallback, not an assumption of unlimited capacity.

| Resource | Add | Current -> planned total | Limit / capacity evidence |
| --- | --- | --- | --- |
| Resource groups | 1 | 14 -> 15 in subscription | 980 documented limit |
| AIServices S0 accounts | 1 | 1 -> 2 in Singapore | 100 from regional usages API |
| CognitiveServices accounts overall | 1 | 1 -> 2 in Singapore | 200 from regional usages API |
| GPT-4.1-mini GlobalStandard | 50K TPM | 0 -> 50K TPM | 5,000K TPM from regional usages API |
| Foundry projects | 1 | 0 -> 1 in the new account | No project-specific quota exposed by the queried API; require ARM validation |
| Container Registry | 1 | 0 -> 1 in Singapore | Quota API unsupported; 10 GiB included Basic storage; require ARM validation |
| Log Analytics | 1 | 1 -> 2 in Singapore | Quota API unsupported; require ARM validation |
| Application Insights | 1 | 1 -> 2 in Singapore | Quota API unsupported; require ARM validation |
| Hosted agent | 1 | 0 -> 1 in the new project | Singapore is officially supported; dynamic session capacity is not guaranteed by model quota |

Capacity status: model and account quotas pass; ARM validation and hosted-agent provisioning remain required.

## Cost estimate

Retail prices queried on 2026-10-07, USD, before tax and subscription discounts:

- ACR Basic: $0.1666/day, approximately $5.00 per 30-day month.
- GPT-4.1-mini GlobalStandard: $0.40 per million input tokens and $1.60 per million output tokens.
- Example model usage: 1M input + 0.25M output tokens = $0.80.
- ACR Tasks: published paid tier $0.0001 per vCPU-second, with a separate zero-price tier.
- Hosted-agent runtime: usage-based CPU and memory during active sessions, including idle timeout.
  The retail API did not return Singapore Hosted meters. Do not substitute zero or quote another region as Singapore.
  East US reference only: $0.0994/vCPU-hour and $0.0118/GiB-hour, or $0.0615 per hour for the configured session.
  Twenty aggregate session-hours at those reference rates would cost $1.23; Singapore's actual rate is unverified.
- Monitoring, build, storage overage, and network charges are additional consumption items.

Planning allowance for light workshop use: $10-20/month, not a verified quote or spending cap.
Continuous usage and multiple active sessions can exceed this substantially.
User must approve the pricing uncertainty before provisioning.

## Files and tooling

- Add `deploy/prerequisites.bicep` rather than changing the existing resource-group deployment contract.
- Add a short new-project bootstrap section to `docs/03-lab3-deploy.md`.
- Update `.dockerignore` and `.gitignore` to exclude new local deployment/auth artifacts.
- Write endpoint/model settings to ignored `src/.env` and an isolated `deploy/.azure/` environment.
- Current azd 1.34.1 reports installed agent/project extensions as incompatible.
  Resolve with a compatible session-local azd version; do not upgrade global tooling without permission.
- Use the existing Dockerfile and manifest unless validation reveals a required compatibility correction.

## Execution checklist

- [x] Verify the requested Azure account and subscription using isolated CLI authentication.
- [x] Inspect the existing deployment configuration.
- [x] Confirm main-system scope, workshop sizing, and Singapore region.
- [x] Inspect model availability, account/model quotas, policies, and retail prices.
- [x] Obtain approval for preparation and validation (not provisioning).
- [x] Prepare configuration and prerequisites.
- [x] Update status to Ready for Validation.
- [x] Invoke azure-validate and complete predeployment validation.
- [x] Record validation proof and obtain deployment approval.
- [x] Invoke azure-deploy.
- [x] Deploy and verify an actual agent response.

## Validation proof

Validation checks (azure-validate):

- [x] AZD installation: signature-verified 1.35.0; isolated agent extension.
- [x] Schema validation: official azure.yaml JSON schema via jsonschema.
- [x] Environment setup: local-disk staging avoids unsupported UNC file locking.
- [x] Authentication: isolated azd uses the requested Azure CLI account.
- [x] Subscription/location: explicitly configured and echoed by provision preview.
- [x] Aspire checks: not applicable (Python).
- [x] Provision preview: bootstrap ARM what-if and existing azd provision preview succeeded.
- [x] Build verification: both Bicep templates compile; pinned Python imports and workflow/server construction pass.
- [x] Docker context: src/pyproject.toml, src/uv.lock, src/, and deploy/Dockerfile exist; local auth excluded.
- [x] Package validation: azd package succeeds (remote build intentionally deferred to deployment).
- [x] Azure Policy validation: ARM validate succeeds; what-if contains only creates in the new RG.
- [x] Static roles: user Project Manager on project; existing ACR module gives project MI AcrPull and deployer Tasks Contributor.

| Check | Command / evidence | Result | Date |
| --- | --- | --- | --- |
| Bootstrap compilation | `az bicep build --file deploy/prerequisites.bicep` | Pass | 2026-10-07 |
| Existing ACR compilation | `az bicep build --file deploy/infra/main.bicep` | Pass | 2026-10-07 |
| Python runtime | `uv run --project src --python 3.13 --locked --no-dev` imports | Pass in WSL | 2026-10-07 |
| Workflow | `create_workflow(...)` and `ResponsesHostServer(...)` | Correct star topology; construction passes | 2026-10-07 |
| Manifest schema | `jsonschema.validate(config, official_schema)` | Pass | 2026-10-07 |
| ARM validation | `az deployment sub validate --template-file prerequisites.bicep ...` | Succeeded, no error | 2026-10-07 |
| Bootstrap preview | `az deployment sub what-if ... --result-format ResourceIdOnly` | Eight creates, no changes/deletes | 2026-10-07 |
| ACR preview | `azd provision --preview --no-prompt` | Succeeded, new ACR and project connection | 2026-10-07 |
| Packaging | `azd package --no-prompt` | Succeeded; remote image build remains at deployment | 2026-10-07 |

Validated by: azure-validate workflow (status progression in staging `.azure/validate-status.json`).
The validation results above describe predeployment checks; actual deployment results follow below.
Correction: `azd provision --preview` created the empty resource group at
2026-10-07T05:15:53Z despite its preview label. Activity logs confirmed the caller
and no resources existed inside it before the approved provisioning continued.

## Preparation results

- Added `deploy/prerequisites.bicep` and `deploy/infra/prerequisites-resources.bicep`.
- Reused Microsoft's basic Foundry resource/connection patterns; existing ACR AVM stays unchanged.
- Added bootstrap instructions and excluded local azd/onboarding artifacts from build context.
- Downloaded signature-verified azd 1.35.0 to session storage and installed agent extension
  1.0.0-beta.15 in a separate `AZD_CONFIG_DIR`. Global tool installation is unchanged.
- Windows dependency download failed with TLS handshake errors, including with native certificate trust.
  Linux `uv run --project src --python 3.13 --locked --no-dev` succeeded and both Foundry runtime imports passed.
- Both the bootstrap template and existing ACR template compile with Bicep 0.48.1.
- Local workflow construction confirms primary-to-three-specialists topology with return-only specialist edges.
  ResponsesHostServer construction passed; telemetry's IMDS probe timed out locally as expected outside Azure.
- Windows azd cannot lock `.env` on the WSL UNC filesystem ("Incorrect function").
  Staged only tracked source/deployment files plus the new templates to the session's
  `files/deployment-workspace` on local Windows disk. No `.env` or virtual environment was copied.
  azd environment creation and explicit subscription/region/tenant settings succeeded there.
  Use this staging directory for azd and resync changed deployment files before deployment.

## Functional verification

User approved local construction plus a real cross-domain prompt after deployment.
Dependency imports, workflow topology, and Responses server construction passed.
The complete 4,011-character T11 fixture returned both coding and architecture findings
from hosted version 2 on 2026-10-07, without a degraded reply. This is a smoke test,
not the full 12-case workshop acceptance suite or a verification of every handoff event.

## Deployment results

- User approved paid resource creation, scoped role assignments, container build/upload,
  agent deployment, and the real verification prompt.
- Foundry account: `ai-ipm-w23tvxbi24buu`; project: `ipm-workshop`.
- Project endpoint: https://ai-ipm-w23tvxbi24buu.services.ai.azure.com/api/projects/ipm-workshop
- ACR: `crrtdjoctkap25g`; remote container build and upload succeeded.
- Hosted agent: `qvn-ipm-review`, version `5`, status `active` (latest repair).
- Responses endpoint: https://ai-ipm-w23tvxbi24buu.services.ai.azure.com/api/projects/ipm-workshop/agents/qvn-ipm-review/endpoint/protocols/openai/responses?api-version=v1
- Playground: https://ai.azure.com/nextgen/r/US6b9WkCSBe3glFNvYy1vQ,rg-ipm-workshop-20261007,,ai-ipm-w23tvxbi24buu,ipm-workshop/build/agents/qvn-ipm-review/build?version=5
- Model: `gpt-4.1-mini`, GlobalStandard, 50K TPM.
- Monitoring: `appi-ipm-w23tvxbi24buu` and `log-ipm-w23tvxbi24buu`.
- Live role checks confirmed project MI AcrPull on ACR, deployer Tasks Contributor
  on ACR, and deployer Foundry Project Manager on the project.
- Version 1 exposed an existing runtime defect: AzureCliCredential cannot work in
  a container without Azure CLI. Version 2 explicitly selects ManagedIdentityCredential
  when AgentConfig identifies a hosted environment; local CLI authentication is unchanged.
  Both selection paths were checked before rebuilding. Real model invocation then succeeded.
- Smoke-test trace ID: `d44033fe2ac94e1bce3aa489f10513b0`.
- Windows positional multiline input did not deliver the complete fixture.
  Sending a UTF-8 JSON body with `--input-file` and `--new-session --new-conversation`
  delivered both source materials and produced the expected two-domain answer.
- Original version 2 limitation (superseded by the repair below): resetting only the conversation in an already-used workflow session
  produced `Unexpected content type while awaiting request info responses`.
  Start a new session together with a new conversation for independent test cases.
  The existing runtime also logged checkpoint deserialization warnings; conversational
  recovery across restarts has not been established by this deployment.
- No Lab 5, cross-cloud resources, Teams, or Bot Service were deployed.
- All three verification sessions were stopped and confirmed `idle`; their state was
  preserved, and the agent deployment remains active for subsequent invocations.
- Foundry Canvas refresh returned `not_signed_in`; its deployment indicator is not
  authoritative for this isolated CLI login. Azure CLI/azd confirmed the live deployment.
- Resources remain billable. The estimate above is not a spending limit.

Deployment metadata and invocation logs are saved under this Copilot session's `files/`.
The working azd environment is in `files/deployment-workspace/deploy/.azure/`;
an ignored copy is retained in the repository's `deploy/.azure/` for recovery.
Windows azd must still run from local-disk staging because UNC file locking fails.

### Playground continuation repair (2026-10-07)

- The user's second-turn `no, go ahead` reproduced a generic WorkflowAgent mismatch:
  Playground sends text while request_info expects a function result. Handoff request
  checkpoint deserialization was also blocked.
- Added `HandoffResponsesHost` using public Responses handler and Workflow APIs.
  Each turn creates independent executors, restores the user/conversation checkpoint,
  and routes text to the single pending Handoff request.
- Provider raw SDK objects caused pickling errors during intermediate verification.
  Hosted-only middleware removes those debug payloads without dropping message/tool data.
- Container-root files disappear after session stop; final version 5 stores checkpoints
  in persistent `$HOME/.handoff-checkpoints/`. Missing/corrupt state is not silently reset.
- Ten local regression tests passed, including HTTP streaming/nonstream responses,
  multiple turns, host recreation, isolation, concurrent followups, and corrupt state.
- Version 5 was confirmed active. Multiple `no, go ahead` messages no longer crashed;
  code review and an architecture followup succeeded with the original snapshot.
  The model sometimes asks an additional confirmation or repeats the code review;
  this is distinct from the fixed protocol/checkpoint failure.
- After stopping and resuming the version 5 session, the architecture followup retained
  the snapshot; trace `68779823f654a64da86838f7c6b6808f`. Logs confirmed checkpoint
  restoration and new checkpoint writes under `/home/session/.handoff-checkpoints/`.
- Repair-created version 3/4/5 sessions were stopped; the user's Playground session
  was not changed. Select version 5 and create one new session/conversation to adopt
  the fix; old version sessions/checkpoints are not migrated.

## Authentication

Use the session-specific `AZURE_CONFIG_DIR` for every Azure command.
Do not use the machine's default Azure account or persist credentials in this repository.

## Sources

- https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
- https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits
- https://learn.microsoft.com/en-us/azure/container-registry/container-registry-skus
- https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/service-limits
- https://prices.azure.com/api/retail/prices
- https://azure.microsoft.com/en-us/pricing/details/foundry-agent-service/
