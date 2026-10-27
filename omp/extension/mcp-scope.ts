// Per-agent MCP scoping for omp subagents. Mirrors opencode.jsonc: every scoped
// server is denied globally and re-allowed per agent. The human-facing main
// session (ctx.agent.kind === "main") is never restricted.
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import type { HarnessPolicy } from "./policy";

const MCP_PREFIX = "mcp__";

/** Port of omp's MCP server-name sanitizer (CA/src/mcp/tool-bridge.ts). */
export function sanitizeServer(name: string): string {
	return name
		.toLowerCase()
		.replace(/[^a-z0-9_]+/g, "_")
		.replace(/__+/g, "_")
		.replace(/^_+|_+$/g, "");
}

/**
 * Raw server name (from `knownServers`) that owns an MCP tool name, picking the
 * longest sanitized-prefix match. `undefined` for non-MCP tools and for MCP
 * tools of a server not in `knownServers`: deliberate fail-open that mirrors
 * opencode, where a server with no global deny is visible to every agent.
 */
export function serverOfTool(toolName: string, knownServers: readonly string[]): string | undefined {
	if (!toolName.startsWith(MCP_PREFIX)) return undefined;
	const rest = toolName.slice(MCP_PREFIX.length);
	let best: string | undefined;
	let bestLength = -1;
	for (const server of knownServers) {
		const prefix = `${sanitizeServer(server)}_`;
		if (rest.startsWith(prefix) && prefix.length > bestLength) {
			best = server;
			bestLength = prefix.length;
		}
	}
	return best;
}

/**
 * Scoped servers a subagent may use. A subagent NOT listed in the policy gets
 * none (fail closed): the Claude/opencode builds also deny every scoped server
 * to an unlisted agent. This covers omp built-ins (`task`, `explore`), `/tan`
 * clones (`sub`) and the `advisor`.
 */
export function allowedServers(agentName: string, policy: HarnessPolicy): readonly string[] {
	return Object.hasOwn(policy.mcp.agents, agentName) ? policy.mcp.agents[agentName] : [];
}

/** Why `toolName` is denied for the subagent `agentName`, or `undefined` when allowed. */
export function deniedReason(toolName: string, agentName: string, policy: HarnessPolicy): string | undefined {
	const server = serverOfTool(toolName, policy.mcp.servers);
	if (server === undefined || allowedServers(agentName, policy).includes(server)) return undefined;
	return `MCP server '${server}' is not available to the '${agentName}' agent (harness policy: write-capable MCP work stays in the main session). Do it in the orchestrator or use an allowed tool.`;
}

export function registerMcpScope(pi: ExtensionAPI, policy: HarnessPolicy): void {
	// Best-effort: hide denied tools so the model does not try them.
	const filterActiveTools = async (agentName: string): Promise<void> => {
		const active = pi.getActiveTools();
		const kept = active.filter(tool => deniedReason(tool, agentName, policy) === undefined);
		if (kept.length !== active.length) await pi.setActiveTools(kept);
	};

	// The guarantee: hard-block the call.
	pi.on("tool_call", (event, ctx) => {
		if (ctx.agent.kind !== "sub") return undefined;
		const reason = deniedReason(event.toolName, ctx.agent.name, policy);
		return reason === undefined ? undefined : { block: true, reason };
	});

	pi.on("session_start", async (_event, ctx) => {
		if (ctx.agent.kind === "sub") await filterActiveTools(ctx.agent.name);
	});

	// MCP tools may connect after session_start; re-run the idempotent filter.
	pi.on("before_agent_start", async (event, ctx) => {
		if (ctx.agent.kind !== "sub" || event.reason === "revive") return undefined;
		await filterActiveTools(ctx.agent.name);
		return undefined;
	});
}
