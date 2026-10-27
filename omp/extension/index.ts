// Harness policy extension entry point: wires the production triage deps (the only value imports
// from omp, resolved by the omp host's extension loader) into the registrar.
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { registerHarnessPolicy } from "./register";
import { productionTriageDeps } from "./result-triage-wiring";

export default function harnessPolicy(pi: ExtensionAPI): void {
	registerHarnessPolicy(pi, productionTriageDeps);
}
