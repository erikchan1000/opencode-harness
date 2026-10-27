import { describe, expect, test } from "bun:test";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import realPolicy from "./policy.json" with { type: "json" };
import { allowedServers, deniedReason, registerMcpScope, sanitizeServer, serverOfTool } from "./mcp-scope";
import { type HarnessPolicy, parsePolicy } from "./policy";

const policy: HarnessPolicy = {
	mcp: {
		servers: ["google", "google-sheets", "stripe", "paper"],
		agents: { worker: ["paper"], sheets: ["google-sheets"], none: [] },
	},
	spawn: {},
};

type Handler = (event: any, ctx: any) => any;

function fakePi(active: string[]) {
	const handlers = new Map<string, Handler>();
	const calls: string[][] = [];
	const pi = {
		on: (name: string, handler: Handler) => handlers.set(name, handler),
		getActiveTools: () => active,
		setActiveTools: async (names: string[]) => {
			calls.push(names);
		},
	};
	return { pi: pi as any, handlers, calls };
}

const sub = (name: string) => ({ agent: { kind: "sub", name } });
const main = { agent: { kind: "main", name: "main" } };

describe("sanitizeServer", () => {
	test("matches omp's sanitizer", () => {
		expect(sanitizeServer("google-sheets")).toBe("google_sheets");
		expect(sanitizeServer("brave-search")).toBe("brave_search");
		expect(sanitizeServer("comfy-cloud")).toBe("comfy_cloud");
		expect(sanitizeServer("Server 2.0")).toBe("server_2_0");
		expect(sanitizeServer("--a__b--")).toBe("a_b");
	});
});

describe("serverOfTool", () => {
	test("longest prefix wins", () => {
		expect(serverOfTool("mcp__google_sheets_read", policy.mcp.servers)).toBe("google-sheets");
		expect(serverOfTool("mcp__google_search", policy.mcp.servers)).toBe("google");
	});
	test("non-MCP and unlisted servers resolve to undefined", () => {
		expect(serverOfTool("read", policy.mcp.servers)).toBeUndefined();
		expect(serverOfTool("mcp__unlisted_tool", policy.mcp.servers)).toBeUndefined();
	});
	test("a server prefix only matches up to the separator", () => {
		// "mcp__googler_x" must not be attributed to "google" (prefix is "google_").
		expect(serverOfTool("mcp__googler_x", policy.mcp.servers)).toBeUndefined();
		// Without the "mcp__" marker even a server-shaped name is not MCP.
		expect(serverOfTool("google_sheets_read", policy.mcp.servers)).toBeUndefined();
	});
	test("empty server list never resolves", () => {
		expect(serverOfTool("mcp__stripe_charge", [])).toBeUndefined();
	});
});

describe("policy decisions", () => {
	test("sub agent allowed / denied per policy", () => {
		expect(deniedReason("mcp__paper_get", "worker", policy)).toBeUndefined();
		const reason = deniedReason("mcp__stripe_charge", "worker", policy);
		expect(reason).toContain("'stripe'");
		expect(reason).toContain("'worker'");
	});
	test("unlisted server is allowed for everyone", () => {
		expect(deniedReason("mcp__unlisted_tool", "none", policy)).toBeUndefined();
	});
	test("unknown sub agent gets no scoped servers", () => {
		expect(allowedServers("mystery", policy)).toEqual([]);
		expect(deniedReason("mcp__paper_get", "mystery", policy)).toBeDefined();
	});
	test("inherited Object properties are not policy entries", () => {
		// An `in`/index lookup would hand "constructor"/"toString" a non-array; must fail closed.
		expect(allowedServers("constructor", policy)).toEqual([]);
		expect(allowedServers("toString", policy)).toEqual([]);
		expect(deniedReason("mcp__paper_get", "constructor", policy)).toBeDefined();
	});
	test("agent with an empty allow list is denied every scoped server", () => {
		for (const tool of ["mcp__google_x", "mcp__google_sheets_read", "mcp__stripe_charge", "mcp__paper_get"]) {
			expect(deniedReason(tool, "none", policy)).toBeDefined();
		}
	});
	test("longest-prefix attribution decides the allow check", () => {
		// "sheets" may use google-sheets but not google; a short-prefix match would flip both.
		expect(deniedReason("mcp__google_sheets_read", "sheets", policy)).toBeUndefined();
		expect(deniedReason("mcp__google_search", "sheets", policy)).toContain("'google'");
	});
});

describe("registerMcpScope", () => {
	test("tool_call blocks subs, never main", () => {
		const { pi, handlers } = fakePi([]);
		registerMcpScope(pi, policy);
		const toolCall = handlers.get("tool_call")!;
		const event = { toolName: "mcp__stripe_charge" };
		expect(toolCall(event, sub("worker"))).toMatchObject({ block: true });
		expect(toolCall(event, main)).toBeUndefined();
		expect(toolCall({ toolName: "mcp__paper_get" }, sub("worker"))).toBeUndefined();
		expect(toolCall({ toolName: "bash" }, sub("worker"))).toBeUndefined();
	});
	test("tool_call reason names the server and the calling agent", () => {
		const { pi, handlers } = fakePi([]);
		registerMcpScope(pi, policy);
		expect(handlers.get("tool_call")!({ toolName: "mcp__stripe_charge" }, sub("worker"))).toEqual({
			block: true,
			reason: "MCP server 'stripe' is not available to the 'worker' agent (harness policy: write-capable MCP work stays in the main session). Do it in the orchestrator or use an allowed tool.",
		});
	});
	test("main session keeps denied MCP tools active", async () => {
		const { pi, handlers, calls } = fakePi(["mcp__stripe_charge"]);
		registerMcpScope(pi, policy);
		await handlers.get("session_start")!({}, main);
		await handlers.get("before_agent_start")!({ reason: "prompt" }, main);
		expect(calls).toEqual([]);
	});
	test("session_start removes only denied MCP tools", async () => {
		const { pi, handlers, calls } = fakePi(["read", "mcp__paper_get", "mcp__stripe_charge", "mcp__unlisted_x"]);
		registerMcpScope(pi, policy);
		await handlers.get("session_start")!({}, sub("worker"));
		expect(calls).toEqual([["read", "mcp__paper_get", "mcp__unlisted_x"]]);
	});
	test("setActiveTools is skipped when nothing is denied, and for main", async () => {
		const { pi, handlers, calls } = fakePi(["read", "mcp__paper_get"]);
		registerMcpScope(pi, policy);
		await handlers.get("session_start")!({}, sub("worker"));
		await handlers.get("session_start")!({}, main);
		expect(calls).toEqual([]);
	});
	test("before_agent_start re-filters but skips revive", async () => {
		const { pi, handlers, calls } = fakePi(["mcp__stripe_charge"]);
		registerMcpScope(pi, policy);
		const handler = handlers.get("before_agent_start")!;
		await handler({ reason: "revive" }, sub("worker"));
		expect(calls).toEqual([]);
		await handler({ reason: "prompt" }, sub("worker"));
		expect(calls).toEqual([[]]);
	});
});

describe("generated policy.json", () => {
	const parsed = parsePolicy(realPolicy);
	test("real allow sets", () => {
		expect(new Set(parsed.mcp.agents["harness-impl"])).toEqual(
			new Set(["codegraph", "context7", "dart", "paper", "playwright"]),
		);
		expect(parsed.mcp.agents["harness-recovery"]).toEqual([]);
		expect(new Set(parsed.mcp.agents["harness-pipeline"])).toEqual(new Set(["paper"]));
	});

	const forkDir = process.env.OMP_FORK_DIR ?? path.join(homedir(), "Documents/code/oh-my-pi");
	const bridge = path.join(forkDir, "packages/coding-agent/src/mcp/tool-bridge.ts");
	test("serverOfTool agrees with the fork's createMCPToolName", async () => {
		if (!existsSync(bridge)) throw new Error(`omp fork checkout required: set OMP_FORK_DIR (missing ${bridge})`);
		const { createMCPToolName } = await import(bridge);
		for (const server of parsed.mcp.servers) {
			expect(serverOfTool(createMCPToolName(server, "some_tool"), parsed.mcp.servers)).toBe(server);
		}
	});
});
