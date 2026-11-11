# Google ADK Agent Implementation Guide

This guide explains how to add a Google Agent Development Kit (ADK) agent to another Python project. It uses this repository's task assistant as a practical reference and is intended to be adapted to a different application's domain.

## Important: what this project currently uses

The current TaskFlow assistant is **not implemented with Google ADK**. It uses the `google-genai` SDK directly:

- `src/agent/task_agent.py` calls `client.models.generate_content(...)`.
- The model is asked to return JSON for application actions.
- `extract_json()` parses that JSON, and `_dispatch_action()` manually calls Python functions.
- `src/frontend/router.py` provides the authenticated HTTP endpoints and stores prompt/response pairs in the database.

ADK is a higher-level agent framework. When porting this pattern, replace the direct model call and custom JSON/action dispatcher with an ADK `Agent`, tools, a `Runner`, and a session service. Keep the existing application's business logic, authorization, and persistence in its own layers.

## Recommended architecture

Keep the agent as one application component, not as a replacement for the web application:

```text
Web UI / API
    |
    +-- Authentication and request validation
    |
    +-- Agent integration (Runner + ADK session service)
    |       |
    |       +-- ADK Agent (instructions + registered tools)
    |               |
    |               +-- Application service functions
    |                       |
    |                       +-- Database / external APIs
    |
    +-- Application-owned chat history / audit records (if needed)
```

The agent should decide **which approved tool to call**. The tool and application service should enforce **what the authenticated user is allowed to do**. Never rely on the model's instructions as an authorization check.

## How a chatbot request reaches an application service

The chatbot does not normally call a database service directly. The browser sends a request to the web application's API; the API authenticates the user and invokes the agent; the agent selects a tool; and that tool calls the application's service/controller. The service performs the validated, user-scoped operation and accesses the database.

### Current TaskFlow request flow

For a text message, the flow in this repository is:

```text
User types a message in templates/base.html
  -> browser POSTs prompt (+ optional session_id) to /agent
  -> src/frontend/router.py: agent_action()
       -> FastAPI dependencies provide authenticated user and database session
       -> calls run_agent(prompt, db, user)
  -> src/agent/task_agent.py: run_agent()
       -> sends prompt and instructions to Gemini using google-genai
       -> model returns either ordinary text or JSON describing an action
       -> extract_json() parses action JSON
       -> _dispatch_action() maps the action to a Python tool function
       -> tool function calls src/tasks/controller.py or another controller
       -> controller checks business rules/ownership and reads or writes via SQLAlchemy
  -> endpoint saves prompt/response in ChatHistoryModel
  -> endpoint returns {response, session_id} to browser
  -> browser displays the response
```

So in the current code, `/agent` is a **FastAPI endpoint in the same application**, not an ADK endpoint. The model does not call `src/tasks/controller.py` itself: the Python `_dispatch_action()` function does that after parsing the model's JSON. The controller/service is also not another HTTP endpoint; it is application code called inside the server process.

The file upload path is separate: the browser POSTs the file to `/agent/upload`; the route calls the file parser/extractor and task controller directly. It does not go through `run_agent()` for ordinary Excel rows or Word tables.

### Request flow after an ADK migration

The outer browser/API/authentication/database flow can remain the same. The middle changes from hand-written JSON parsing and action dispatch to ADK's `Runner` and tool-calling loop:

```text
Browser
  -> POST /agent with prompt and conversation/session identifier
  -> FastAPI authenticates request; provides trusted user and DB context
  -> route creates/reuses the ADK session and calls Runner
  -> Runner runs the ADK Agent with the user's message
  -> Agent decides whether a tool is needed
       -> if needed, Runner invokes a registered Python tool with validated arguments
       -> tool calls the application service/controller
       -> service enforces ownership/business rules and accesses the database
       -> tool result returns to Runner/Agent
       -> Agent may produce the final user-facing response
  -> route saves any app-owned chat/audit record and returns response
  -> Browser displays it
```

In this ADK flow, do not keep the old model-produced JSON format plus `_dispatch_action()` for the same operations: ADK's registered tools provide that selection/invocation mechanism. The trusted authenticated user must still come from the server, not from prompt text or model-supplied arguments. Keep `src/tasks/controller.py` (or the equivalent service layer) as the authority for database operations and authorization.

## Step-by-step implementation

### 1. Define the agent's scope before coding

Write down:

- The concrete user problem and supported requests.
- The data sources and external services the agent needs.
- The operations it may perform, including operations that require confirmation.
- What it must not do and how failures should be reported.
- Whether conversations must persist across requests, restarts, or deployments.
- Where it will run: local prototype, existing application server, or a deployed agent service.

Start with one agent and only the tools required for the first use case. Add sub-agents or workflow orchestration only when there is a clear need.

### 2. Prepare the target project

For a new agent project, use the agents-cli scaffold workflow to establish the ADK project layout and development conventions before writing agent code. For an existing Python application, enhance or integrate the existing project rather than replacing its web server, database, or authentication.

For a plain Python setup, install ADK using the project's chosen dependency manager and lock the dependency:

```powershell
uv add google-adk
```

If the target already uses `requirements.txt`, add and pin a tested `google-adk` version there instead. Do not add a second environment or dependency file unless the project needs one.

Choose one Google model access mode:

- **Google AI API key:** configure `GOOGLE_API_KEY` as a local environment variable or in an ignored `.env` file.
- **Vertex AI:** configure the project, location, and Google Cloud credentials according to the deployment environment.

Do not hardcode credentials, commit `.env`, or print secrets in logs. Keep model and access configuration in the target project's settings.

### 3. Separate tools from agent configuration

Create small, typed Python functions for capabilities the agent can use. For a TaskFlow-like agent, these could be:

- `list_my_tasks`
- `create_task`
- `update_task`
- `delete_task`

Each tool should have a clear name, type annotations, and a useful docstring because ADK uses tool metadata to inform the model. A tool should call the application's existing service/controller layer instead of duplicating SQL or business rules.

Example shape:

```python
def list_my_tasks(status: str | None = None) -> dict:
    """List tasks belonging to the authenticated user, optionally filtered by status."""
    # Resolve trusted request/user context, call the application service,
    # and return a small JSON-serializable result.
    ...
```

Treat the example as a design sketch: adapt context handling, return types, and error conventions to the selected ADK version and the host application's architecture.

### 4. Define the ADK agent

Put the ADK agent definition in a dedicated module, separate from FastAPI routes and database models. A minimal definition has this shape:

```python
from google.adk.agents import Agent

from .tools import list_my_tasks

root_agent = Agent(
    name="task_assistant",
    model="<model-supported-by-your-Google-AI-or-Vertex-AI-setup>",
    instruction=(
        "Help the signed-in user manage their tasks. "
        "Use available tools for task data and actions. "
        "Do not claim an action succeeded unless its tool succeeded."
    ),
    tools=[list_my_tasks],
)
```

Replace the model placeholder with one supported in the chosen location and configured for the environment. Keep instructions focused on behavior; put validation and access control in code.

Suggested layout:

```text
project/
├── app/
│   ├── agent/
│   │   ├── agent.py       # ADK Agent definition
│   │   ├── tools.py       # ADK-callable tool functions
│   │   └── service.py     # Optional application-service adapter
│   ├── api/               # FastAPI routes
│   ├── models/            # Database models
│   └── ...
├── tests/
├── .env                   # Local only; ignored by git
└── pyproject.toml
```

Use the host repository's existing conventions if it already has an established layout.

### 5. Integrate ADK with the web application

In a FastAPI application, the route should:

1. Authenticate the request using the existing authentication system.
2. Validate the prompt, uploaded content, and any submitted conversation identifier.
3. Resolve the authenticated user and create/reuse the correct ADK session.
4. Run the agent through an ADK `Runner` and collect the final response.
5. Return the response using the application's existing API contract.
6. Persist application chat/audit records if the product needs them.

Use ADK's `Runner` and a session service appropriate to the environment. An in-memory session service is useful for a local prototype but loses sessions when the process restarts and is not shared between workers. For a deployed application, choose a supported persistent session service or another explicitly designed persistence strategy.

The ADK conversation session and an application's chat-history table are not automatically the same thing. TaskFlow currently records user/assistant prompt-response pairs in `ChatHistoryModel`; if that remains useful for the UI or audit trail, keep it separate from ADK's session state and define how the two stay associated.

### 6. Pass trusted user and database context safely

TaskFlow tools currently receive a SQLAlchemy `Session` and authenticated user directly. In an ADK integration, do not let the model provide or select a user ID, database session, role, or authorization scope.

Instead:

- Derive the user identity from the authenticated request.
- Make that trusted identity available to the tool through the host application's request-scoped adapter or ADK's supported tool/session context mechanism.
- Open and close database sessions using the application's existing dependency/lifecycle pattern.
- Apply user-scoped filters in every service operation, including reads, updates, and deletes.
- Avoid storing live database connections, ORM objects, credentials, or other non-serializable secrets in ADK session state.

Before shipping, verify that a user cannot read, edit, or delete another user's records by asking the agent to do so.

### 7. Add validation and safeguards to tools

Model-produced tool arguments are untrusted input. For every tool:

- Validate required fields, lengths, enums, dates, and identifiers in application code.
- Use the same business rules and database constraints as normal UI/API operations.
- Return concise, serializable results; do not return entire ORM models or sensitive fields.
- Report expected failures clearly instead of returning a success-shaped response.
- Require explicit user confirmation in application logic for destructive or high-impact operations, such as deleting all records.
- Add rate limits, upload size/type restrictions, and content checks where relevant.

Keep tools narrow. For example, prefer a user-scoped `delete_task(task_id)` over a generic database/query tool.

### 8. Preserve file-import and other non-chat workflows deliberately

TaskFlow has a separate file-import path: it reads `.xlsx` and `.docx` files, uses deterministic parsers where possible, and calls Gemini for unstructured Word text. Decide independently whether such workflows need an ADK agent.

If import can be handled by ordinary parsing and validation, keep it deterministic. If the model is needed for extraction, constrain its output, validate every extracted item, and keep file size/type and authorization checks in the API/application layer. Do not assume that migrating the chat endpoint requires moving every AI-related feature into ADK.

### 9. Run locally and verify behavior

Use the project's dependency manager to install/sync dependencies, then use ADK's local CLI (for example, `adk run` or `adk web`, depending on the workflow) to verify the agent before integrating it into the application server.

Verify these layers separately:

1. **Tool tests:** valid inputs, invalid inputs, ownership checks, missing records, and database failures.
2. **Agent smoke tests:** representative requests, correct tool selection, clear responses when a tool fails.
3. **API integration tests:** unauthenticated requests fail, session IDs cannot cross users, and responses match the existing UI contract.
4. **Behavioral evaluation:** use ADK/agents-cli evaluation for tool selection, task completion, and safety behavior. Do not rely only on a successful response to one prompt.
5. **Deployment checks:** persistent sessions, secret configuration, logs without sensitive content, timeouts, and concurrent workers.

When evaluating model behavior, use representative cases such as:

- List only the signed-in user's tasks.
- Create a task with a valid title and due date.
- Ask to update or delete another user's task.
- Request an unsupported or ambiguous operation.
- Cause a tool/database error and confirm the assistant does not claim success.
- Attempt a destructive operation and confirm the intended confirmation policy.

Do not write brittle unit tests that require the model to produce exact wording. Unit-test deterministic tools and use evaluations for model behavior.

### 10. Deploy only after review

Before deploying, decide where the agent and session state will live, configure least-privilege Google credentials, and verify that the deployed identity can access only required Google resources. Store production secrets in the deployment platform's secret manager, not in source control or image layers.

Review tool permissions, per-user data isolation, retention of chat/session data, and logging before enabling real users. Deploy only after the application owner has approved the target and configuration.

## TaskFlow porting checklist

When applying this guide to another project, map the TaskFlow pieces to that project's equivalents:

| TaskFlow responsibility | What to carry into the other project |
|---|---|
| `src/agent/task_agent.py` | Replace direct `generate_content`, JSON parsing, and `_dispatch_action()` with an ADK agent and registered tools. |
| `src/tasks/controller.py` | Reuse the destination project's service/business logic; keep it as the source of truth for validation and persistence. |
| `src/frontend/router.py` | Integrate the ADK runner after authentication; retain the API's response contract and request checks. |
| `src/agent/models.py` | Decide whether app-owned chat history is still needed in addition to ADK session storage. |
| `src/utils/db.py` | Reuse the application's database lifecycle; never serialize a live SQLAlchemy session into agent state. |
| `src/agent/file_import.py` | Keep deterministic parsing separate; use an agent only for the portions that genuinely need model reasoning. |
| `.env` / application settings | Configure Google credentials and model access outside source code; use deployment secrets in production. |

## Completion checklist

- [ ] The target application has a clear agent scope and tool list.
- [ ] ADK dependencies and Google model access are configured for the target environment.
- [ ] The ADK agent and tools are separated from API routes and database models.
- [ ] Tools call existing application services and enforce validation and user ownership.
- [ ] ADK sessions have an intentional persistence strategy.
- [ ] The application API, chat history, and UI behavior remain compatible.
- [ ] Tool, API, and agent behavior have been tested/evaluated, including failures and authorization boundaries.
- [ ] Production credentials, session retention, logs, and deployment settings have been reviewed.

## References

- [Google ADK documentation](https://adk.dev/)
- [ADK Python samples and recipes](https://github.com/google/adk-samples)
- [Google agents-cli](https://github.com/google/agents-cli) for scaffold, run, eval, and deployment workflows
