import { describe, expect, test } from "bun:test";
import systemPrompt from "./result-triage.prompt.md" with { type: "text" };
import {
	createSemaphore,
	DEFAULT_TRIAGE_CONFIG,
	MAX_CONCURRENT_DIGESTS,
	digestResult,
	parseTriageConfig,
	registerResultTriage,
	shouldTriage,
	type TriageCompletion,
	type TriageConfig,
	type TriageEvent,
} from "./result-triage";

const big = "x".repeat(8000);
const ev = (o: Partial<TriageEvent> = {}): TriageEvent => ({
	jobId: "j1", jobType: "task", agentId: "a1", status: "completed", text: big, ...o,
});
const ok = (text = "short digest"): TriageCompletion => ({ content: [{ type: "text", text }], stopReason: "stop" });

function setup(opts: { raw?: unknown; complete?: (...a: any[]) => Promise<TriageCompletion>; model?: unknown; key?: string | undefined; hasUI?: boolean } = {}) {
	const logs = { error: [] as string[], warn: [] as string[] };
	const notes: string[] = [];
	let handler: any;
	const pi: any = {
		on: (_n: string, h: any) => (handler = h),
		logger: { error: (m: string) => logs.error.push(m), warn: (m: string) => logs.warn.push(m) },
	};
	const calls: any[] = [];
	registerResultTriage(pi, {
		loadRawConfig: async () => opts.raw,
		digestDeps: () => ({
			resolveModel: () => ("model" in opts ? opts.model : { id: "m" }),
			getApiKey: async () => ("key" in opts ? opts.key : "k"),
			complete: opts.complete ?? (async (...a: any[]) => (calls.push(a), ok())),
		}),
	});
	const ctx = { hasUI: opts.hasUI ?? true, ui: { notify: (m: string) => notes.push(m) } };
	return { run: (e: TriageEvent) => handler(e, ctx), logs, notes, calls };
}
const on = { resultTriage: { enabled: true } };

describe("shouldTriage", () => {
	const cfg: TriageConfig = { ...DEFAULT_TRIAGE_CONFIG, enabled: true };
	test("gates", () => {
		expect(shouldTriage(ev(), cfg)).toBe(true);
		expect(shouldTriage(ev({ text: "x".repeat(6000) }), cfg)).toBe(false);
		expect(shouldTriage(ev(), { ...cfg, enabled: false })).toBe(false);
		expect(shouldTriage(ev({ jobType: "bash" }), cfg)).toBe(false);
		expect(shouldTriage(ev({ jobType: "eval" }), cfg)).toBe(false);
		expect(shouldTriage(ev({ jobType: "bash" }), { ...cfg, jobTypes: ["task", "bash"] })).toBe(true);
		expect(shouldTriage(ev({ status: "failed" }), cfg)).toBe(false);
		expect(shouldTriage(ev({ status: "cancelled" }), cfg)).toBe(false);
	});
});

describe("parseTriageConfig", () => {
	test("absent is off", () => expect(parseTriageConfig({})).toBeUndefined());
	test("defaults fill in", () => expect(parseTriageConfig(on)).toEqual({ ...DEFAULT_TRIAGE_CONFIG, enabled: true }));
	test("unknown key", () => expect(() => parseTriageConfig({ resultTriage: { bogus: 1 } })).toThrow("unknown key 'bogus'"));
	test("timeout >= 30000", () => expect(() => parseTriageConfig({ resultTriage: { timeoutMs: 30000 } })).toThrow("'timeoutMs' must be below 30000"));
	test("bad jobTypes", () => expect(() => parseTriageConfig({ resultTriage: { jobTypes: ["task", "x"] } })).toThrow("'jobTypes' entries must be one of task|bash|eval"));
	test("bad enabled type", () => expect(() => parseTriageConfig({ resultTriage: { enabled: "yes" } })).toThrow("'enabled' must be a boolean"));
	test("non-object file", () => expect(() => parseTriageConfig([])).toThrow("JSON object"));
});

describe("handler", () => {
	test("replaces large completed task result with shorter digest", async () => {
		const t = setup({ raw: on });
		const r = await t.run(ev());
		expect(r.text).toBe("short digest\n[digest of 12 chars by @smol]");
		expect(r.text.length).toBeLessThan(big.length);
		expect(r.suppress).toBeUndefined();
		expect(t.calls[0][2]).toMatchObject({ apiKey: "k", maxTokens: 834, disableReasoning: true });
	});
	test("below threshold untouched", async () => {
		const t = setup({ raw: on });
		expect(await t.run(ev({ text: "small" }))).toBeUndefined();
		expect(t.calls.length).toBe(0);
	});
	test("bash/eval/failed/cancelled untouched by default", async () => {
		const t = setup({ raw: on });
		for (const o of [{ jobType: "bash" }, { jobType: "eval" }, { status: "failed" }, { status: "cancelled" }] as Partial<TriageEvent>[]) {
			expect(await t.run(ev(o))).toBeUndefined();
		}
	});
	test("bash triaged when listed, footer carries no pointer (core adds it)", async () => {
		const t = setup({ raw: { resultTriage: { enabled: true, jobTypes: ["bash"] } } });
		const r = await t.run(ev({ jobType: "bash", agentId: undefined }));
		expect(r.text).toBe("short digest\n[digest of 12 chars by @smol]");
		expect(r.text).not.toContain("://");
	});
	test("config absent or disabled is off", async () => {
		expect(await setup({ raw: undefined }).run(ev())).toBeUndefined();
		expect(await setup({ raw: { resultTriage: { enabled: false } } }).run(ev())).toBeUndefined();
	});
	test("invalid config delivers original, logs one error", async () => {
		const t = setup({ raw: { resultTriage: { nope: 1 } } });
		expect(await t.run(ev())).toBeUndefined();
		expect(await t.run(ev())).toBeUndefined();
		expect(t.logs.error.length).toBe(1);
		expect(t.notes.length).toBe(1);
	});

	const failures: Array<[string, Parameters<typeof setup>[0]]> = [
		["complete rejects", { complete: async () => { throw new Error("boom"); } }],
		["stopReason error", { complete: async () => ({ content: [], stopReason: "error", errorMessage: "bad" }) }],
		["stopReason length", { complete: async () => ({ ...ok(), stopReason: "length" }) }],
		["empty text", { complete: async () => ok("   ") }],
		["digest longer than input", { complete: async () => ok("y".repeat(9000)) }],
		["unresolved model", { model: undefined }],
		["no api key", { key: undefined }],
	];
	for (const [name, o] of failures) {
		test(`${name} delivers original and logs`, async () => {
			const t = setup({ raw: on, ...o });
			expect(await t.run(ev())).toBeUndefined();
			expect(t.logs.warn.length).toBe(1);
			expect(t.logs.warn[0]).toContain("j1");
		});
	}
	test("timeout delivers original and logs", async () => {
		const t = setup({
			raw: { resultTriage: { enabled: true, timeoutMs: 20 } },
			complete: (_m, _c, o) => new Promise((_, rej) => o.signal.addEventListener("abort", () => rej(o.signal.reason))),
		});
		expect(await t.run(ev())).toBeUndefined();
		expect(t.logs.warn.length).toBe(1);
	});
});

describe("semaphore", () => {
	test("never exceeds cap", async () => {
		const sem = createSemaphore(2);
		let active = 0, max = 0;
		const cfg: TriageConfig = { ...DEFAULT_TRIAGE_CONFIG, enabled: true };
		const deps = {
			resolveModel: () => ({}),
			getApiKey: async () => "k",
			semaphore: sem,
			systemPrompt: "p",
			complete: async () => {
				active++; max = Math.max(max, active);
				await Bun.sleep(5);
				active--;
				return ok();
			},
		};
		const results = await Promise.all(Array.from({ length: 10 }, () => digestResult(ev(), cfg, deps)));
		expect(results.every(r => r.ok)).toBe(true);
		expect(max).toBe(2);
	});
	test("waiting job gives up when its budget expires", async () => {
		const sem = createSemaphore(1);
		const hold = await sem.acquire(new AbortController().signal);
		await expect(sem.acquire(AbortSignal.timeout(10))).rejects.toBeDefined();
		hold();
		await sem.acquire(new AbortController().signal);
	});
});

test("system prompt file is loaded and non-empty", () => {
	expect(systemPrompt.trim().length).toBeGreaterThan(100);
});

describe("gap coverage (test agent)", () => {
	const flush = async () => {
		for (let i = 0; i < 20; i++) await Promise.resolve();
	};

	test("statuses opt-in: failed/cancelled triaged only when listed", async () => {
		const t = setup({ raw: { resultTriage: { enabled: true, statuses: ["failed"] } } });
		expect((await t.run(ev({ status: "failed" }))).text).toContain("short digest");
		expect(await t.run(ev({ status: "completed" }))).toBeUndefined();
		expect(await t.run(ev({ status: "cancelled" }))).toBeUndefined();
		expect(t.calls.length).toBe(1);
	});

	test("eval triaged when listed, task then untouched", async () => {
		const t = setup({ raw: { resultTriage: { enabled: true, jobTypes: ["eval"] } } });
		expect((await t.run(ev({ jobType: "eval" }))).text).toContain("short digest");
		expect(await t.run(ev({ jobType: "task" }))).toBeUndefined();
	});

	test("configured thresholdChars is honoured and the boundary is exclusive", async () => {
		const t = setup({ raw: { resultTriage: { enabled: true, thresholdChars: 100 } } });
		expect(await t.run(ev({ text: "z".repeat(100) }))).toBeUndefined();
		expect((await t.run(ev({ text: "z".repeat(101) }))).text).toContain("short digest");
		expect(t.calls.length).toBe(1);
	});

	test("digest exactly as long as the original is rejected (strictly shorter)", async () => {
		const footer = "\n[digest of 10 chars by @smol]";
		const original = "q".repeat(10 + footer.length);
		const t = setup({ raw: { resultTriage: { enabled: true, thresholdChars: 1 } }, complete: async () => ok("d".repeat(10)) });
		expect(await t.run(ev({ text: original }))).toBeUndefined();
		expect(t.logs.warn[0]).toContain("not shorter");
		const t2 = setup({ raw: { resultTriage: { enabled: true, thresholdChars: 1 } }, complete: async () => ok("d".repeat(10)) });
		expect((await t2.run(ev({ text: original + "q" }))).text).toBe(`${"d".repeat(10)}${footer}`);
	});

	for (const stopReason of ["toolUse", "aborted"] as const) {
		test(`stopReason ${stopReason} delivers original and logs the reason`, async () => {
			const t = setup({ raw: on, complete: async () => ({ ...ok(), stopReason }) });
			expect(await t.run(ev())).toBeUndefined();
			expect(t.logs.warn[0]).toContain(stopReason);
		});
	}

	test("only text blocks form the digest", async () => {
		const t = setup({
			raw: on,
			complete: async () => ({ content: [{ type: "thinking", text: "SECRET" }, { type: "text", text: "a" }, { type: "text", text: "b" }], stopReason: "stop" }),
		});
		const r = await t.run(ev());
		expect(r.text.startsWith("ab\n[digest of 2 chars")).toBe(true);
		expect(r.text).not.toContain("SECRET");
	});

	test("request: configured model spec, preface with jobType+label, system prompt, signal", async () => {
		const specs: string[] = [];
		let seen: any[] = [];
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error() {}, warn() {} } };
		registerResultTriage(pi, {
			loadRawConfig: async () => ({ resultTriage: { enabled: true, model: "@custom", maxDigestChars: 300 } }),
			systemPrompt: "SYS",
			digestDeps: () => ({
				resolveModel: (s: string) => (specs.push(s), { id: "m" }),
				getApiKey: async () => "k",
				complete: async (...a: any[]) => ((seen = a), ok()),
			}),
		});
		const r = await handler(ev({ label: "fix-bug" }), { hasUI: false });
		expect(specs).toEqual(["@custom"]);
		const [, context, options] = seen;
		expect(context.systemPrompt).toEqual(["SYS"]);
		expect(context.messages).toHaveLength(1);
		expect(context.messages[0].role).toBe("user");
		expect(context.messages[0].content).toContain("task");
		expect(context.messages[0].content).toContain("fix-bug");
		expect(context.messages[0].content.endsWith(big)).toBe(true);
		expect(options.maxTokens).toBe(100);
		expect(options.signal).toBeInstanceOf(AbortSignal);
		expect(r.text).toContain("by @custom]");
	});

	test("unresolved model never falls back to another model", async () => {
		const specs: string[] = [];
		let completed = false;
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error() {}, warn() {} } };
		registerResultTriage(pi, {
			loadRawConfig: async () => on,
			digestDeps: () => ({
				resolveModel: (s: string) => (specs.push(s), undefined),
				getApiKey: async () => "k",
				complete: async () => ((completed = true), ok()),
			}),
		});
		expect(await handler(ev(), { hasUI: false })).toBeUndefined();
		expect(specs).toEqual(["@smol"]);
		expect(completed).toBe(false);
	});

	test("config load error (bad JSON) delivers original, logs error, notifies", async () => {
		const logs: string[] = [];
		const notes: Array<[string, string]> = [];
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error: (m: string) => logs.push(m), warn() {} } };
		registerResultTriage(pi, {
			loadRawConfig: async () => {
				throw new SyntaxError("JSON Parse error: Unexpected EOF");
			},
			digestDeps: () => {
				throw new Error("must not be reached");
			},
		});
		expect(await handler(ev(), { hasUI: true, ui: { notify: (m: string, l: string) => notes.push([m, l]) } })).toBeUndefined();
		expect(logs).toHaveLength(1);
		expect(logs[0]).toContain("Unexpected EOF");
		expect(notes).toHaveLength(1);
		expect(notes[0][1]).toBe("error");
	});

	test("invalid config without UI logs but does not notify", async () => {
		const t = setup({ raw: { resultTriage: { timeoutMs: 30000 } }, hasUI: false });
		expect(await t.run(ev())).toBeUndefined();
		expect(t.logs.error).toHaveLength(1);
		expect(t.notes).toHaveLength(0);
	});

	test("each distinct config error is logged; a fixed config resumes triage", async () => {
		let raw: unknown = { resultTriage: { bogus: 1 } };
		const logs: string[] = [];
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error: (m: string) => logs.push(m), warn() {} } };
		registerResultTriage(pi, {
			loadRawConfig: async () => raw,
			digestDeps: () => ({ resolveModel: () => ({}), getApiKey: async () => "k", complete: async () => ok() }),
		});
		const ctx = { hasUI: false };
		expect(await handler(ev(), ctx)).toBeUndefined();
		raw = { resultTriage: { timeoutMs: 99999 } };
		expect(await handler(ev(), ctx)).toBeUndefined();
		expect(logs).toHaveLength(2);
		raw = on;
		expect((await handler(ev(), ctx)).text).toContain("short digest");
	});

	test("digestDeps throwing delivers original and warns", async () => {
		const warns: string[] = [];
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error() {}, warn: (m: string) => warns.push(m) } };
		registerResultTriage(pi, {
			loadRawConfig: async () => on,
			digestDeps: () => {
				throw new Error("no registry");
			},
		});
		expect(await handler(ev(), { hasUI: false })).toBeUndefined();
		expect(warns).toHaveLength(1);
		expect(warns[0]).toContain("no registry");
	});

	test("no failure path ever returns suppress", async () => {
		const modes: Array<Parameters<typeof setup>[0]> = [
			{ raw: on },
			{ raw: on, complete: async () => { throw new Error("x"); } },
			{ raw: on, complete: async () => ({ content: [], stopReason: "error" }) },
			{ raw: { resultTriage: { bad: true } } },
			{ raw: on, model: undefined },
		];
		for (const m of modes) {
			const r = await setup(m).run(ev());
			if (r !== undefined) {
				expect(Object.keys(r)).toEqual(["text"]);
			}
		}
	});

	test("semaphore slot is released when complete throws", async () => {
		const sem = createSemaphore(1);
		const cfg: TriageConfig = { ...DEFAULT_TRIAGE_CONFIG, enabled: true };
		const base = { resolveModel: () => ({}), getApiKey: async () => "k", semaphore: sem, systemPrompt: "p" };
		await expect(digestResult(ev(), cfg, { ...base, complete: async () => { throw new Error("boom"); } })).rejects.toThrow("boom");
		const r = await digestResult(ev(), { ...cfg, timeoutMs: 50 }, { ...base, complete: async () => ok() });
		expect(r.ok).toBe(true);
	});

	test("job queued behind a full semaphore delivers original once its budget expires", async () => {
		const sem = createSemaphore(1);
		const hold = await sem.acquire(new AbortController().signal);
		const warns: string[] = [];
		let completed = false;
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error() {}, warn: (m: string) => warns.push(m) } };
		registerResultTriage(pi, {
			loadRawConfig: async () => ({ resultTriage: { enabled: true, timeoutMs: 20 } }),
			digestDeps: () => ({
				resolveModel: () => ({}),
				getApiKey: async () => "k",
				complete: async () => ((completed = true), ok()),
				semaphore: sem,
			}),
		});
		expect(await handler(ev(), { hasUI: false })).toBeUndefined();
		expect(completed).toBe(false);
		expect(warns).toHaveLength(1);
		expect(warns[0]).toContain("j1");
		hold();
	});

	test("default module semaphore caps concurrent handler digests at MAX_CONCURRENT_DIGESTS", async () => {
		expect(MAX_CONCURRENT_DIGESTS).toBe(4);
		let active = 0;
		let max = 0;
		const gates: Array<() => void> = [];
		let handler: any;
		const pi: any = { on: (_n: string, h: any) => (handler = h), logger: { error() {}, warn() {} } };
		registerResultTriage(pi, {
			loadRawConfig: async () => on,
			digestDeps: () => ({
				resolveModel: () => ({}),
				getApiKey: async () => "k",
				complete: async () => {
					active++;
					max = Math.max(max, active);
					const { promise, resolve } = Promise.withResolvers<void>();
					gates.push(resolve);
					await promise;
					active--;
					return ok();
				},
			}),
		});
		const runs = Array.from({ length: 10 }, (_, i) => handler(ev({ jobId: `j${i}` }), { hasUI: false }));
		await flush();
		expect(active).toBe(MAX_CONCURRENT_DIGESTS);
		while (gates.length > 0 || active > 0) {
			gates.shift()?.();
			await flush();
		}
		const results = await Promise.all(runs);
		expect(results.every(r => r?.text?.includes("short digest"))).toBe(true);
		expect(max).toBe(MAX_CONCURRENT_DIGESTS);
	});
});

describe("parseTriageConfig precise errors (test agent)", () => {
	const cases: Array<[string, unknown, string]> = [
		["null file", null, "file must contain a JSON object"],
		["non-object resultTriage", { resultTriage: true }, "'resultTriage' must be an object"],
		["array resultTriage", { resultTriage: [] }, "'resultTriage' must be an object"],
		["bad statuses", { resultTriage: { statuses: ["done"] } }, "'statuses' entries must be one of completed|failed|cancelled"],
		["empty jobTypes", { resultTriage: { jobTypes: [] } }, "'jobTypes' must be a non-empty array"],
		["non-array statuses", { resultTriage: { statuses: "completed" } }, "'statuses' must be a non-empty array"],
		["zero threshold", { resultTriage: { thresholdChars: 0 } }, "'thresholdChars' must be a positive integer"],
		["fractional maxDigestChars", { resultTriage: { maxDigestChars: 1.5 } }, "'maxDigestChars' must be a positive integer"],
		["string timeoutMs", { resultTriage: { timeoutMs: "100" } }, "'timeoutMs' must be a positive integer"],
		["empty model", { resultTriage: { model: "" } }, "'model' must be a non-empty string"],
		["timeout above runner", { resultTriage: { timeoutMs: 45000 } }, "'timeoutMs' must be below 30000"],
	];
	for (const [name, raw, msg] of cases) {
		test(name, () => expect(() => parseTriageConfig(raw)).toThrow(msg));
	}
	test("timeoutMs just below the runner limit is accepted; full override round-trips", () => {
		const full = { enabled: true, thresholdChars: 10, model: "@x", maxDigestChars: 50, timeoutMs: 29999, statuses: ["completed", "failed"], jobTypes: ["task", "bash", "eval"] };
		expect(parseTriageConfig({ resultTriage: full })).toEqual(full as TriageConfig);
	});
	test("other top-level keys are ignored when resultTriage is absent", () => {
		expect(parseTriageConfig({ somethingElse: 1 })).toBeUndefined();
	});
});
