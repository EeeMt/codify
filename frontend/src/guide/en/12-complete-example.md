---
title: Complete example
section: User Guide
tier: core
---

## Start with the example

This fictional repository shows the full path from a new Issue to a reviewed result. The goal is to add a test for an expired token returning 401 from a login endpoint. Your project may use different files and endpoints, so replace the names with the ones in your repository.

The example keeps two layers separate: the Issue description holds context that remains true across turns, while the Task prompt describes the work for this turn.

## Create the Issue first

| Field | Example | Why |
|---|---|---|
| Title | Add an expired-token test to login | The title names the problem in a few words |
| Description | The login endpoint returns 401 for invalid credentials. Keep successful login responses and existing auth rules unchanged. | This context should still apply to a follow-up Task |
| Project | `acme/auth-service` | Choose the GitLab project that should receive the change |
| Starting Branch | `develop` | Use the current development baseline |
| Merge Target | `develop` | Send the Merge Request back to the same development branch |
| Create Merge Request | On | The team will review the code |
| Branch cleanup | Follow your team practice | Decide whether the AI branch is removed after merge |
| Worker | A verified Worker with the required Harness | The Worker is fixed after creation, so check it now |

Before submitting, confirm the project, branches, merge-request setting, Worker, and advanced settings. Those choices are frozen with the Issue; create another Issue when you need a different set.

## Write the Task prompt

On the Issue page, select **Create Task**, **Implementation**, and **Execute Now**. The Issue description is copied into the Prompt field first. You can replace it with this focused prompt:

```text
Goal: add and commit a test for an expired token on the login endpoint.

Scope: inspect the existing login endpoint, authentication middleware, and test directory first. Change only files directly related to this scenario.

Constraints: keep successful login and other existing error responses unchanged; follow the repository's current test framework and assertion style; do not change the database schema.

Acceptance criteria:
- a request with an expired token returns HTTP 401;
- the test reproduces that result reliably;
- the existing login tests still pass;
- the change has a clear commit message.

Verification: run the focused login tests, then the full test command documented by the repository. Report the commands and the important output.
```

This prompt tells the Harness what to do, where it may work, what must stay stable, and how to verify the result. Name known files and commands; when you do not know them, ask the Harness to inspect the repository instead of guessing.

## Run, review, and continue

After submitting, follow this order:

1. Read **Events** on the Task page to see the repository check, edit, and verification steps.
2. Open **Raw Logs** or download the runtime archive only when you need the complete output.
3. When the Task completes, inspect the **Commit Record** and **Delivery Result**, then review the Merge Request.
4. If one test or document is still missing, append a Task to the same Issue and name that remaining work and its verification command.
5. Create a new Issue when the project, starting branch, merge target, or Worker must change.

| Result | Next action |
|---|---|
| Tests, commit, and push all succeed | Review and merge the Merge Request |
| The code is right but one test is missing | Append a Task for that test and its verification |
| A quota, runtime, or network condition caused a transient failure | Read the failure reason, fix the condition, and retry |
| The Task prompt set the wrong scope | Append a clearer Task or correct and retry; do not treat the mistaken prompt as Issue context |

## Why this example is shaped this way

The Issue description does not contain a one-off filename or command, so a later Task can reuse its background. The Task prompt states a result that can be checked, giving the Harness a useful boundary for inspection, edits, and verification. If you use a custom Run Instruction Template, confirm that it includes `{{user_prompt}}`; otherwise this prompt will not enter the Final Run Prompt automatically. See [Creating a Task](/guide/30-create-task).
