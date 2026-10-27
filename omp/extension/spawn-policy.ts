// Restricts who may spawn the leaf harness agents. omp's `spawns:` list only
// constrains subagents; this also covers the main session.
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import type { HarnessPolicy } from "./policy";

export function checkSpawn(
	agentToSpawn: string,
	spawner: { kind: "main" | "sub"; name: string },
	policy: HarnessPolicy,
): { block: true; reason: string } | undefined {
	if (!Object.hasOwn(policy.spawn, agentToSpawn)) return undefined;
	const parents = policy.spawn[agentToSpawn];
	if (parents.includes(spawner.name)) return undefined;
	return {
		block: true,
		reason: `'${agentToSpawn}' must run under ${parents.join(", ")}, not '${spawner.name}' directly. Spawn ${parents.join(" or ")} with the work item instead.`,
	};
}

export function registerSpawnPolicy(pi: ExtensionAPI, policy: HarnessPolicy): void {
	// Fires in the spawning (parent) session for both "task" and "eval" invocations.
	pi.on("before_subagent_spawn", (event, ctx) => checkSpawn(event.agent, ctx.agent, policy));
}
