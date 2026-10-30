import { describe, it, expect } from "vitest";
import worker from "./index";

describe("LeetCode Cloud Sync Worker Fetch Handler", () => {
  const mockEnv = {
    LEETCODE_USERNAME: "testuser",
    LEETCODE_SESSION: "testsession",
    GITHUB_TOKEN: "testtoken",
    GITHUB_REPO: "test/repo",
    SYNC_STATE: {} as any,
    SUBMISSION_QUEUE: {} as any,
  };

  const mockCtx = {
    waitUntil: () => {},
    passThroughOnException: () => {},
  } as any;

  it("returns status ok and service name for /health", async () => {
    const req = new Request("https://worker.test/health");
    const res = await worker.fetch(req, mockEnv, mockCtx);
    expect(res.status).toBe(200);
    const data = await res.json() as any;
    expect(data.status).toBe("ok");
    expect(data.service).toBe("leetcode-cloud-sync-worker");
  });

  it("returns status ok for /healthz", async () => {
    const req = new Request("https://worker.test/healthz");
    const res = await worker.fetch(req, mockEnv, mockCtx);
    expect(res.status).toBe(200);
    const data = await res.json() as any;
    expect(data.status).toBe("ok");
  });

  it("returns service info for root /", async () => {
    const req = new Request("https://worker.test/");
    const res = await worker.fetch(req, mockEnv, mockCtx);
    expect(res.status).toBe(200);
    const data = await res.json() as any;
    expect(data.name).toBe("leetcode-cloud-sync-worker");
    expect(data.status).toBe("active");
  });

  it("returns 404 for unknown routes", async () => {
    const req = new Request("https://worker.test/unknown-route");
    const res = await worker.fetch(req, mockEnv, mockCtx);
    expect(res.status).toBe(404);
    const data = await res.json() as any;
    expect(data.error).toBe("Not Found");
  });

  it("returns 405 for non-GET/HEAD methods", async () => {
    const req = new Request("https://worker.test/health", { method: "POST" });
    const res = await worker.fetch(req, mockEnv, mockCtx);
    expect(res.status).toBe(405);
  });
});
