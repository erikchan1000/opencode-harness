// Shape of the generated policy.json (written by omp/build.py via omp/policy.py).
export interface HarnessPolicy {
	mcp: { servers: string[]; agents: Record<string, string[]> };
	spawn: Record<string, string[]>;
}

function isStringArray(value: unknown): value is string[] {
	return Array.isArray(value) && value.every(item => typeof item === "string");
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Validate the generated policy; throws on any malformed shape (no fallback). */
export function parsePolicy(raw: unknown): HarnessPolicy {
	if (!isRecord(raw)) throw new Error("harness policy: expected an object");
	const { mcp, spawn } = raw;
	if (!isRecord(mcp)) throw new Error("harness policy: 'mcp' must be an object");
	if (!isStringArray(mcp.servers)) throw new Error("harness policy: 'mcp.servers' must be a string array");
	if (!isRecord(mcp.agents)) throw new Error("harness policy: 'mcp.agents' must be an object");
	for (const [agent, allowed] of Object.entries(mcp.agents)) {
		if (!isStringArray(allowed)) throw new Error(`harness policy: 'mcp.agents.${agent}' must be a string array`);
		for (const server of allowed) {
			if (!mcp.servers.includes(server)) {
				throw new Error(`harness policy: agent '${agent}' allows unscoped server '${server}'`);
			}
		}
	}
	if (!isRecord(spawn)) throw new Error("harness policy: 'spawn' must be an object");
	for (const [agent, parents] of Object.entries(spawn)) {
		if (!isStringArray(parents) || parents.length === 0) {
			throw new Error(`harness policy: 'spawn.${agent}' must be a non-empty string array`);
		}
	}
	return {
		mcp: { servers: mcp.servers, agents: mcp.agents as Record<string, string[]> },
		spawn: spawn as Record<string, string[]>,
	};
}
