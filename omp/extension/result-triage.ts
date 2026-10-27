// Result triage: condenses large settled subagent results before they reach the
// orchestrator's context (a 60-child fan-out otherwise injects ~150k tokens).
//
// Design (fixed): a DIRECT call to the cheap `@smol` model, not
// `ctx.runEphemeralTurn`.
//  - cost: the digest needs only the job's own text (~3k tokens in, ~300 out) on
//    the cheapest model; an ephemeral turn re-sends the parent's whole context
//    (100k+ tokens) on the parent's model, once per child.
//  - cache: a separate request never touches the parent's prompt-cache prefix.
//  - latency/concurrency: a ~2-5 s small-model call is independent of whether
//    the parent is streaming; a side turn contends with the live turn and cannot
//    nest.
//  - failure: every failure is local and degrades to "deliver the original".
// Trade-off: the digester sees only the child's report, not the parent's task,
// so the prompt asks for faithful condensation, not interpretation.
//
// Opt-in via <agentDir>/harness-policy.json (user-owned, never written by the
// installer). Value imports of omp packages live in result-triage-wiring.ts so
// this file and its tests never need the fork.
import type { Api, Model } from "@oh-my-pi/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";
import systemPrompt from "./result-triage.prompt.md" with { type: "text" };

export type TriageJobType = "task" | "bash" | "eval";
export type TriageStatus = "completed" | "failed" | "cancelled";

export interface TriageConfig {
	enabled: boolean;
	thresholdChars: number;
	model: string;
	maxDigestChars: number;
	timeoutMs: number;
	statuses: TriageStatus[];
	jobTypes: TriageJobType[];
}

/** Defaults for a present `resultTriage` object. An absent file/key means OFF. */
export const DEFAULT_TRIAGE_CONFIG: TriageConfig = {
	enabled: false,
	thresholdChars: 6000,
	model: "@smol",
	maxDigestChars: 2500,
	timeoutMs: 20000,
	statuses: ["completed"],
	jobTypes: ["task"],
};

/** The extension runner aborts handlers at 30 s; the digest budget must stay below. */
export const RUNNER_HANDLER_TIMEOUT_MS = 30000;
/** Max concurrent digest calls across all jobs. */
export const MAX_CONCURRENT_DIGESTS = 4;

const JOB_TYPES: readonly string[] = ["task", "bash", "eval"];
const STATUSES: readonly string[] = ["completed", "failed", "cancelled"];
const KEYS = Object.keys(DEFAULT_TRIAGE_CONFIG);

function fail(message: string): never {
	throw new Error(`harness-policy.json resultTriage: ${message}`);
}

function positiveInt(obj: Record<string, unknown>, key: string, dflt: number): number {
	if (!(key in obj)) return dflt;
	const v = obj[key];
	if (typeof v !== "number" || !Number.isInteger(v) || v <= 0) fail(`'${key}' must be a positive integer`);
	return v;
}

function enumList<T extends string>(obj: Record<string, unknown>, key: string, allowed: readonly string[], dflt: T[]): T[] {
	if (!(key in obj)) return dflt;
	const v = obj[key];
	if (!Array.isArray(v) || v.length === 0) fail(`'${key}' must be a non-empty array`);
	for (const item of v) {
		if (typeof item !== "string" || !allowed.includes(item)) {
			fail(`'${key}' entries must be one of ${allowed.join("|")}, got ${JSON.stringify(item)}`);
		}
	}
	return v as T[];
}

/**
 * Parses the file contents (already JSON-decoded). Returns `undefined` when the
 * feature is not configured (the documented off state). Throws a precise error
 * for a present-but-invalid file.
 */
export function parseTriageConfig(raw: unknown): TriageConfig | undefined {
	if (typeof raw !== "object" || raw === null || Array.isArray(raw)) fail("file must contain a JSON object");
	const top = raw as Record<string, unknown>;
	if (!("resultTriage" in top)) return undefined;
	const obj = top.resultTriage;
	if (typeof obj !== "object" || obj === null || Array.isArray(obj)) fail("'resultTriage' must be an object");
	const cfg = obj as Record<string, unknown>;
	for (const key of Object.keys(cfg)) {
		if (!KEYS.includes(key)) fail(`unknown key '${key}' (allowed: ${KEYS.join(", ")})`);
	}
	if ("enabled" in cfg && typeof cfg.enabled !== "boolean") fail("'enabled' must be a boolean");
	if ("model" in cfg && (typeof cfg.model !== "string" || cfg.model.length === 0)) fail("'model' must be a non-empty string");
	const timeoutMs = positiveInt(cfg, "timeoutMs", DEFAULT_TRIAGE_CONFIG.timeoutMs);
	if (timeoutMs >= RUNNER_HANDLER_TIMEOUT_MS) {
		fail(`'timeoutMs' must be below ${RUNNER_HANDLER_TIMEOUT_MS} (the runner's handler timeout), got ${timeoutMs}`);
	}
	return {
		enabled: (cfg.enabled as boolean | undefined) ?? DEFAULT_TRIAGE_CONFIG.enabled,
		thresholdChars: positiveInt(cfg, "thresholdChars", DEFAULT_TRIAGE_CONFIG.thresholdChars),
		model: (cfg.model as string | undefined) ?? DEFAULT_TRIAGE_CONFIG.model,
		maxDigestChars: positiveInt(cfg, "maxDigestChars", DEFAULT_TRIAGE_CONFIG.maxDigestChars),
		timeoutMs,
		statuses: enumList<TriageStatus>(cfg, "statuses", STATUSES, DEFAULT_TRIAGE_CONFIG.statuses),
		jobTypes: enumList<TriageJobType>(cfg, "jobTypes", JOB_TYPES, DEFAULT_TRIAGE_CONFIG.jobTypes),
	};
}

export interface TriageEvent {
	jobId: string;
	jobType: TriageJobType;
	agentId?: string;
	label?: string;
	status: TriageStatus;
	text: string;
}

export function shouldTriage(event: TriageEvent, config: TriageConfig): boolean {
	return (
		config.enabled &&
		config.jobTypes.includes(event.jobType) &&
		config.statuses.includes(event.status) &&
		event.text.length > config.thresholdChars
	);
}

export interface Semaphore {
	acquire(signal: AbortSignal): Promise<() => void>;
}

export function createSemaphore(cap: number): Semaphore {
	let active = 0;
	const waiters: Array<() => void> = [];
	const release = () => {
		active--;
		waiters.shift()?.();
	};
	return {
		async acquire(signal) {
			signal.throwIfAborted();
			if (active >= cap) {
				const { promise, resolve } = Promise.withResolvers<void>();
				const wake = () => resolve();
				waiters.push(wake);
				const onAbort = () => {
					const i = waiters.indexOf(wake);
					if (i >= 0) waiters.splice(i, 1);
					resolve();
				};
				signal.addEventListener("abort", onAbort, { once: true });
				await promise;
				signal.removeEventListener("abort", onAbort);
				signal.throwIfAborted();
			}
			active++;
			return release;
		},
	};
}

export const digestSemaphore = createSemaphore(MAX_CONCURRENT_DIGESTS);

export interface TriageContext {
	systemPrompt: string[];
	messages: Array<{ role: "user"; content: string; timestamp: number }>;
}
export interface TriageCompleteOptions {
	apiKey: string;
	maxTokens: number;
	signal: AbortSignal;
	disableReasoning: true;
}
export interface TriageCompletion {
	content: Array<{ type: string; text?: string }>;
	stopReason: "stop" | "length" | "toolUse" | "error" | "aborted";
	errorMessage?: string;
}

export interface DigestDeps<M = unknown> {
	resolveModel(spec: string): M | undefined;
	getApiKey(model: M): Promise<string | undefined>;
	complete(model: M, context: TriageContext, options: TriageCompleteOptions): Promise<TriageCompletion>;
	semaphore: Semaphore;
	systemPrompt: string;
	now?: () => number;
}

export type DigestOutcome = { ok: true; text: string } | { ok: false; reason: string };

export async function digestResult<M>(event: TriageEvent, config: TriageConfig, deps: DigestDeps<M>): Promise<DigestOutcome> {
	// Budget runs from enqueue time, so time spent waiting on the semaphore counts.
	const signal = AbortSignal.timeout(config.timeoutMs);
	const model = deps.resolveModel(config.model);
	if (model === undefined) return { ok: false, reason: `model '${config.model}' did not resolve` };
	const apiKey = await deps.getApiKey(model);
	if (apiKey === undefined) return { ok: false, reason: `no API key for model '${config.model}'` };
	const release = await deps.semaphore.acquire(signal);
	let result: TriageCompletion;
	try {
		const preface = `Subagent report (job type: ${event.jobType}${event.label === undefined ? "" : `, label: ${event.label}`}). Limit: ${config.maxDigestChars} characters.`;
		result = await deps.complete(
			model,
			{
				systemPrompt: [deps.systemPrompt],
				messages: [{ role: "user", content: `${preface}\n\n${event.text}`, timestamp: (deps.now ?? Date.now)() }],
			},
			{ apiKey, maxTokens: Math.ceil(config.maxDigestChars / 3), signal, disableReasoning: true },
		);
	} finally {
		release();
	}
	if (result.stopReason !== "stop") {
		return { ok: false, reason: `stopReason ${result.stopReason}${result.errorMessage === undefined ? "" : `: ${result.errorMessage}`}` };
	}
	const digest = result.content
		.filter(b => b.type === "text")
		.map(b => b.text ?? "")
		.join("")
		.trim();
	if (digest.length === 0) return { ok: false, reason: "empty digest" };
	const text = `${digest}\n[digest of ${digest.length} chars by ${config.model}]`;
	if (text.length >= event.text.length) return { ok: false, reason: "digest not shorter than original" };
	return { ok: true, text };
}

export interface TriageDeps {
	/** Returns the JSON-decoded harness-policy.json, or undefined when the file does not exist. */
	loadRawConfig(): Promise<unknown | undefined>;
	/** Builds per-event digest deps (model resolution and API keys come from the live context). */
	digestDeps(ctx: ExtensionContext): Omit<DigestDeps<Model<Api>>, "systemPrompt" | "semaphore"> & Partial<Pick<DigestDeps<Model<Api>>, "semaphore">>;
	systemPrompt?: string;
}

export function registerResultTriage(pi: ExtensionAPI, deps: TriageDeps): void {
	let reportedConfigError: string | undefined;
	pi.on("async_result", async (event: TriageEvent, ctx: ExtensionContext) => {
		let config: TriageConfig | undefined;
		try {
			const raw = await deps.loadRawConfig();
			config = raw === undefined ? undefined : parseTriageConfig(raw);
		} catch (err) {
			// A broken config must not drop results: report once, deliver the original.
			const message = err instanceof Error ? err.message : String(err);
			if (reportedConfigError !== message) {
				reportedConfigError = message;
				pi.logger.error(`result-triage disabled: ${message}`);
				if (ctx.hasUI) ctx.ui.notify(`result-triage disabled: ${message}`, "error");
			}
			return undefined;
		}
		if (config === undefined || !shouldTriage(event, config)) return undefined;
		try {
			const digestDeps = deps.digestDeps(ctx);
			const outcome = await digestResult(event, config, {
				...digestDeps,
				semaphore: digestDeps.semaphore ?? digestSemaphore,
				systemPrompt: deps.systemPrompt ?? systemPrompt,
			});
			if (outcome.ok) return { text: outcome.text };
			pi.logger.warn(`result-triage: delivering original for job ${event.jobId}: ${outcome.reason}`);
		} catch (err) {
			// Dropping or truncating a subagent result is worse than delivering a large one.
			pi.logger.warn(`result-triage: delivering original for job ${event.jobId}: ${err instanceof Error ? err.message : String(err)}`);
		}
		return undefined;
	});
}
