/**
 * Cloudflare Worker for LeetCode Cloud Sync Event-Driven MVP
 *
 * 1. Cron Trigger (every 2 minutes): Polls LeetCode GraphQL API for recent submission stubs.
 * 2. Deduplication: Compares submission IDs against Cloudflare KV durable state.
 * 3. Queue Producer: Pushes new unseen submission events to Cloudflare Queue (with safe post-send KV marking).
 * 4. Queue Consumer: Triggers GitHub Actions workflow_dispatch via GitHub REST API for each event.
 */

interface Env {
  LEETCODE_USERNAME: string;
  LEETCODE_SESSION: string;
  LEETCODE_CSRF_TOKEN?: string;
  GITHUB_TOKEN: string; // Personal Access Token with repo / workflow permissions
  GITHUB_REPO: string;  // e.g. "kaviyack/leetcode-cloud-sync"
  SYNC_WORKFLOW_FILE?: string; // default: "leetcode-sync.yml"
  SYNC_STATE: KVNamespace;
  SUBMISSION_QUEUE: Queue<SubmissionEvent>;
}

interface SubmissionEvent {
  userId: string;
  submissionId: string;
  detectedAt: number;
  status: string;
  retryCount: number;
  idempotencyKey: string;
}

const GRAPHQL_URL = "https://leetcode.com/graphql";
const SUBMISSION_LIST_QUERY = `
query submissionList($offset: Int!, $limit: Int!, $lastKey: String) {
  submissionList(offset: $offset, limit: $limit, lastKey: $lastKey) {
    submissions {
      id
      title
      statusDisplay
      status
      timestamp
    }
  }
}
`;

export default {
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(handlePoll(env));
  },

  async queue(batch: MessageBatch<SubmissionEvent>, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(handleQueueBatch(batch, env));
  },

  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response(JSON.stringify({ error: "Method Not Allowed" }), {
        status: 405,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (path === "/health" || path === "/healthz") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "leetcode-cloud-sync-worker",
          timestamp: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (path === "/") {
      return new Response(
        JSON.stringify({
          name: "leetcode-cloud-sync-worker",
          description: "Event-driven submission detector and queue consumer for LeetCode Cloud Sync",
          status: "active",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    return new Response(JSON.stringify({ error: "Not Found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  },
};

async function handlePoll(env: Env): Promise<void> {
  const username = env.LEETCODE_USERNAME;
  const session = env.LEETCODE_SESSION;
  const csrf = env.LEETCODE_CSRF_TOKEN || "";

  if (!username || !session) {
    console.error("Missing LEETCODE_USERNAME or LEETCODE_SESSION in worker environment.");
    return;
  }

  console.log(`Polling LeetCode submissions for user: ${username}`);

  try {
    const response = await fetch(GRAPHQL_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 LeetCodeCloudSyncWorker/1.0",
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
        "Cookie": `LEETCODE_SESSION=${session}; csrftoken=${csrf}`,
        ...(csrf ? { "x-csrftoken": csrf } : {}),
      },
      body: JSON.stringify({
        query: SUBMISSION_LIST_QUERY,
        variables: { offset: 0, limit: 10, lastKey: null },
      }),
    });

    if (!response.ok) {
      console.error(`LeetCode API error during poll: HTTP ${response.status}`);
      return;
    }

    const data: any = await response.json();
    const subs = data?.data?.submissionList?.submissions;
    if (!subs || !Array.isArray(subs)) {
      console.warn("Invalid submission list response structure.");
      return;
    }

    for (const sub of subs) {
      const subId = String(sub.id);
      const statusDisplay = sub.statusDisplay || sub.status || "";

      // Only care about accepted submissions by default
      if (statusDisplay !== "Accepted" && sub.status !== "AC") {
        continue;
      }

      const seenKey = `seen:${subId}`;
      const alreadySeen = await env.SYNC_STATE.get(seenKey);

      if (!alreadySeen) {
        console.log(`New accepted submission detected: ${subId} (${sub.title})`);

        const submissionEvent: SubmissionEvent = {
          userId: username,
          submissionId: subId,
          detectedAt: Date.now(),
          status: statusDisplay,
          retryCount: 0,
          idempotencyKey: `${username}-${subId}-${Date.now()}`,
        };

        try {
          // Send to queue first; mark seen in KV only after successful queue publication
          // to prevent permanent loss if queue send fails.
          await env.SUBMISSION_QUEUE.send(submissionEvent);
          await env.SYNC_STATE.put(seenKey, String(Date.now()));
          console.log(`Successfully queued and marked submission event for ${subId}`);
        } catch (sendErr) {
          console.error(`Failed to queue submission ${subId}, will retry on next poll:`, sendErr);
        }
      }
    }
  } catch (err) {
    console.error("Exception during LeetCode polling:", err);
  }
}

async function handleQueueBatch(batch: MessageBatch<SubmissionEvent>, env: Env): Promise<void> {
  const repo = env.GITHUB_REPO || "kaviyack/leetcode-cloud-sync";
  const workflowFile = env.SYNC_WORKFLOW_FILE || "leetcode-sync.yml";
  const githubToken = env.GITHUB_TOKEN;

  if (!githubToken) {
    console.error("Missing GITHUB_TOKEN in worker environment for queue dispatch.");
    return;
  }

  for (const message of batch.messages) {
    const event = message.body;
    console.log(`Processing queue event for submission ID: ${event.submissionId}`);

    try {
      const dispatchUrl = `https://api.github.com/repos/${repo}/actions/workflows/${workflowFile}/dispatches`;
      const resp = await fetch(dispatchUrl, {
        method: "POST",
        headers: {
          "Authorization": `token ${githubToken}`,
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "LeetCodeCloudSyncWorker/1.0",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ref: "main",
          inputs: {
            submission_id: event.submissionId,
          },
        }),
      });

      if (resp.status === 204 || resp.status === 201) {
        console.log(`Successfully dispatched workflow for submission ${event.submissionId}`);
        message.ack();
      } else {
        const errorText = await resp.text();
        console.error(`Failed to dispatch GitHub workflow: HTTP ${resp.status} — ${errorText}`);

        if (event.retryCount >= 3) {
          console.error(`Max retries reached for submission ${event.submissionId}. Routing message to dead-letter queue.`);
          // Not calling message.ack() allows Cloudflare Queues to route the message to dead_letter_queue
        } else {
          event.retryCount++;
          message.retry({ delaySeconds: Math.pow(2, event.retryCount) * 10 });
        }
      }
    } catch (err) {
      console.error(`Exception dispatching GitHub workflow for ${event.submissionId}:`, err);
      message.retry({ delaySeconds: 30 });
    }
  }
}
