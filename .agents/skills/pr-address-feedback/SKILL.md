---
name: pr-address-feedback
description: >
Guide for handling pull request reviews, including automated (Copilot) and
human reviewer feedback. Use when responding to PR comments, resolving
review threads, or updating PRs after review.
argument-hint: ""
user-invocable: true
metadata:
author: APME Team
version: 1.1.0
---

# PR Address Feedback

This skill defines how to handle PR review feedback in the APME project.

## Responding to review comments

Every review comment MUST receive a response. Resolve threads only after the
feedback has been addressed and accepted; leave threads unresolved when disputing
feedback and escalate to a human reviewer. Unanswered comments or unresolved
disputed threads block merge.

### Rules

* Address ALL review comments before requesting re-review. Do not leave
  comments unanswered.

* Every comment requires a **closing reply**. When the feedback is addressed
  or accepted, also **resolve the thread** via the GitHub API. When
  disputing or flagging a false positive, leave the thread unresolved for
  human escalation.

* Reply to each comment with a **brief explanation of how it was resolved** and
  the commit hash (e.g., "Removed the unused imports so Ruff F401 passes.
  Fixed in abc1234."). Do not reply with only the SHA; explain the fix.

* If a comment is a false positive or you disagree, reply with a clear
  technical explanation. Do not resolve the thread. This will require human
  intervention. Do not dismiss without justification.

* After pushing fixes, update the PR description to reflect the expanded scope
  (per the pr-new skill).

### Deferred work MUST be tracked

Any time a review response includes language like "follow-up PR", "subsequent
PR", "leaving as a follow-up", "future enhancement", "out of scope for this
PR", or "logging this for later" — you **MUST** create a GitHub issue
immediately using `gh issue create`. Do not reply to the comment without also
creating the issue. Include the issue URL in your reply so the reviewer can
verify tracking.

Untracked follow-ups are invisible debt. If it is worth mentioning, it is
worth an issue.

```bash
# Create a follow-up issue and capture the URL
gh issue create --repo ansible/apme \
  --title "<type>(scope): <brief description>" \
  --body "$(cat <<'EOF'
## Context

<What was the review comment and why it wasn't addressed in this PR>

Flagged in: <link to PR comment thread>

## Proposal

<What should be done>

## References

- PR #N
EOF
)"
```

## Copilot review patterns

Copilot automated reviews surface recurring categories. Address these
proactively before pushing to avoid review round-trips:

### Supply-chain security

Pin GitHub Actions to commit SHAs instead of mutable tags (`@v1`). Mutable
tags allow upstream changes to affect CI without review. Use a comment to
note the original tag:

```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4
```

### Inaccurate documentation

Documentation MUST accurately describe the actual behavior. Be specific about triggers, branches, and conditions.

### Markdown table formatting

Tables must use a single leading `|` on each line. Double leading `||` renders
as an extra empty column. Validate table rendering before committing.

### Inaccurate comments

Code comments and docstrings MUST accurately describe what the code does. If
you rename a function, change behavior, or remove functionality, update all
associated comments in the same commit.

### Secrets in documentation

Never show API keys, tokens, or credentials on command lines in docs or
examples. Demonstrate env var usage instead.

### Unused imports (Ruff F401)

Remove unused imports or use the symbol. Prefer trimming the import list over `# noqa: F401` unless the import is intentionally side-effect only.

## Workflow

1. **Sync Branch:** Ensure the PR branch is up to date with upstream main.

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Review & Plan:** Check CI status and read all review comments. **Write out a brief Action Plan** detailing which files you will edit to fix the comments.

3. **Fix & Validate Locally:** Fix all issues in minimal commits. **Crucially, run local validation before pushing** (e.g., `tox -e lint` or `tox -e unit`) to ensure your fix doesn't break something else.

4. **Push:** `git push --force-with-lease`

5. **Wait & Verify Remote CI:** Wait 2-3 minutes for remote CI pipelines to run, then check their status. Some tests only run remotely; fix any remote-only failures before proceeding.

6. **Reply & Resolve (GraphQL):** Reply to *every single comment* with how it was handled (fixed + hash, deferred + issue link, or disputed). **Only resolve the threads you actually fixed or formally deferred.** Leave disputed threads unresolved for human review.

7. **Verify Actions:** Query the threads one last time to ensure every thread has your reply, and that you didn't accidentally resolve a thread you didn't fix.

### Checking CI status

Always check CI checks as part of the review workflow.

```bash
# After pushing, wait a few minutes, then list pending or failing checks (replace N with PR number)
gh pr checks N --json name,state --jq '.[] | select(.state != "SUCCESS")'

# View failed job logs directly
gh run view RUN_ID --log-failed 2>&1 | tail -80
```

Do **not** run `ruff`, `mypy`, `pytest`, or `prek` directly — always use tox.

### Replying to and Resolving review threads (GraphQL ONLY)

**CRITICAL:** Always use GraphQL (Base64 Node IDs) for both listing, replying, and resolving. Do NOT mix REST integer IDs with GraphQL Node IDs. Do NOT use `minimizeComment`.

**Step 1: List unresolved threads to get `THREAD_ID`**
Replace `N` with the PR number. This gets the `id` for each unresolved thread.

```bash
gh api graphql -f query='{
  repository(owner: "ansible", name: "apme") {
    pullRequest(number: N) {
      reviewThreads(first: 50) {
        nodes { id isResolved comments(first:1) { nodes { body } } }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | {id, snippet: .comments.nodes[0].body[0:120]}'
```

**Step 2: Reply to the thread**
Replace `THREAD_ID` with the `id` fetched above. State how the issue was resolved and the commit hash, OR explain why it is being disputed.

```bash
gh api graphql -f query='mutation {
  addPullRequestReviewThreadReply(input: {pullRequestThreadId: "THREAD_ID", body: "Removed the unused imports so Ruff F401 passes. Fixed in abc1234."}) {
    comment { id }
  }
}'
```

**Step 3: Resolve the thread (CONDITIONAL)**
Only run this if you successfully addressed the comment or filed a follow-up issue. **Do NOT run this if you are disputing the comment.**

```bash
gh api graphql -f query='mutation {
  resolveReviewThread(input: {threadId: "THREAD_ID"}) {
    thread { isResolved }
  }
}'
```

*(You may combine Step 2 and Step 3 in a single bash script or execute them sequentially.)*

### Verification Check

After replying and selectively resolving, run the Step 1 query one final time.

* **Verify Replies:** Ensure that *every* thread (whether resolved or left unresolved) has a new reply from you explaining your action or dispute.

* **Verify Intentional State:** It is expected to see unresolved threads returned in this query *only* if they are disputed. Verify that any thread you left unresolved was left open intentionally. Do NOT blindly resolve all threads just to clear the list.

### After pushing fixes: check for a new Copilot review

Copilot may run again on new commits. Re-check whether it left a new review or
line comments so you can reply and resolve any new threads.

```bash
# New Copilot review (replace N with PR number, ISO8601 with last push time)
gh api repos/ansible/apme/pulls/N/reviews --jq '.[] | select(.user.login == "copilot-pull-request-reviewer[bot]" and .submitted_at > "ISO8601") | {submitted_at, state, body: .body[0:200]}'
```

