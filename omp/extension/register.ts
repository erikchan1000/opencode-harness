// Registers every harness policy. Takes the triage deps as a parameter so this module has no value
// imports from omp and can be loaded by tests outside the omp host.
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import rawPolicy from "./policy.json" with { type: "json" };
import { registerMcpScope } from "./mcp-scope";
import { parsePolicy } from "./policy";
import { registerResultTriage, type TriageDeps } from "./result-triage";
import { registerSpawnPolicy } from "./spawn-policy";

// Fails extension load loudly when the generated file is missing or malformed.
const policy = parsePolicy(rawPolicy);

export function registerHarnessPolicy(pi: ExtensionAPI, triageDeps: TriageDeps): void {
	registerMcpScope(pi, policy);
	registerSpawnPolicy(pi, policy);
	registerResultTriage(pi, triageDeps);
}
