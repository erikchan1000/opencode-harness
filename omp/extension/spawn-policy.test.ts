import { describe, expect, test } from "bun:test";
import realPolicy from "./policy.json" with { type: "json" };
import { registerHarnessPolicy } from "./register";
import { type HarnessPolicy, parsePolicy } from "./policy";
import { checkSpawn, registerSpawnPolicy } from "./spawn-policy";

const policy = parsePolicy(realPolicy);

describe("checkSpawn", () => {
	for (const agent of ["harness-impl", "harness-test", "harness-debug"]) {
		test(`main is blocked from ${agent}`, () => {
			const result = checkSpawn(agent, { kind: "main", name: "main" }, policy);
			expect(result?.block).toBe(true);
			expect(result?.reason).toBe(
				`'${agent}' must run under harness-pipeline, not 'main' directly. Spawn harness-pipeline with the work item instead.`,
			);
		});
		test(`harness-pipeline may spawn ${agent}`, () => {
			expect(checkSpawn(agent, { kind: "sub", name: "harness-pipeline" }, policy)).toBeUndefined();
		});
	}
	test("another sub agent is blocked", () => {
		expect(checkSpawn("harness-impl", { kind: "sub", name: "harness-research" }, policy)?.block).toBe(true);
	});
	test("unrelated spawns are untouched", () => {
		expect(checkSpawn("harness-pipeline", { kind: "main", name: "main" }, policy)).toBeUndefined();
		expect(checkSpawn("coder", { kind: "main", name: "main" }, policy)).toBeUndefined();
	});
	test("inherited Object property names are not restricted agents", () => {
		expect(checkSpawn("constructor", { kind: "main", name: "main" }, policy)).toBeUndefined();
	});
	test("reason lists every allowed parent from the data", () => {
		const multi: HarnessPolicy = { mcp: { servers: [], agents: {} }, spawn: { leaf: ["p1", "p2"] } };
		expect(checkSpawn("leaf", { kind: "sub", name: "p2" }, multi)).toBeUndefined();
		expect(checkSpawn("leaf", { kind: "main", name: "main" }, multi)).toEqual({
			block: true,
			reason: "'leaf' must run under p1, p2, not 'main' directly. Spawn p1 or p2 with the work item instead.",
		});
	});
});

describe("registerHarnessPolicy", () => {
	test("registers both policies against the real generated policy", async () => {
		const handlers = new Map<string, (event: any, ctx: any) => any>();
		const set: string[][] = [];
		registerHarnessPolicy({
			on: (name: string, h: any) => handlers.set(name, h),
			getActiveTools: () => ["read", "mcp__stripe_x", "mcp__paper_get"],
			setActiveTools: async (names: string[]) => {
				set.push(names);
			},
		} as any, {
			// Triage stays off: no harness-policy.json.
			loadRawConfig: async () => undefined,
			digestDeps: () => {
				throw new Error("digestDeps must not be called while triage is off");
			},
		});
		const main = { agent: { kind: "main", name: "main" } };
		const impl = { agent: { kind: "sub", name: "harness-impl" } };
		expect(handlers.get("before_subagent_spawn")!({ agent: "harness-test", invocationKind: "task" }, main)?.block).toBe(true);
		expect(handlers.get("tool_call")!({ toolName: "mcp__stripe_x" }, impl)?.block).toBe(true);
		expect(handlers.get("tool_call")!({ toolName: "mcp__stripe_x" }, main)).toBeUndefined();
		await handlers.get("session_start")!({}, impl);
		expect(set).toEqual([["read", "mcp__paper_get"]]);
	});
});

describe("registerSpawnPolicy", () => {
	test("applies to task and eval invocations, using the spawner's agent", () => {
		let handler: ((event: any, ctx: any) => any) | undefined;
		registerSpawnPolicy({ on: (_name: string, h: any) => (handler = h) } as any, policy);
		const main = { agent: { kind: "main", name: "main" } };
		for (const invocationKind of ["task", "eval"]) {
			expect(handler!({ agent: "harness-impl", invocationKind }, main)?.block).toBe(true);
			expect(handler!({ agent: "harness-impl", invocationKind }, { agent: { kind: "sub", name: "harness-pipeline" } })).toBeUndefined();
		}
	});
});

describe("parsePolicy", () => {
	const good: HarnessPolicy = { mcp: { servers: ["a"], agents: { x: ["a"] } }, spawn: { y: ["x"] } };
	test("accepts a well-formed policy", () => {
		expect(parsePolicy(good)).toEqual(good);
	});
	test.each([
		["non-object", 3],
		["missing mcp", { spawn: {} }],
		["servers not array", { mcp: { servers: "a", agents: {} }, spawn: {} }],
		["agent allows unscoped server", { mcp: { servers: ["a"], agents: { x: ["b"] } }, spawn: {} }],
		["missing spawn", { mcp: { servers: [], agents: {} } }],
		["empty parents", { mcp: { servers: [], agents: {} }, spawn: { y: [] } }],
		["null", null],
		["array root", []],
		["agents not object", { mcp: { servers: [], agents: [] }, spawn: {} }],
		["agent allow list not array", { mcp: { servers: ["a"], agents: { x: "a" } }, spawn: {} }],
		["non-string server", { mcp: { servers: [1], agents: {} }, spawn: {} }],
		["non-string parent", { mcp: { servers: [], agents: {} }, spawn: { y: [1] } }],
	])("rejects %s", (_label, raw) => {
		expect(() => parsePolicy(raw)).toThrow();
	});
});
