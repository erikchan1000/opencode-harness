// Production wiring for result-triage: the only file with value imports from omp.
import * as path from "node:path";
import { completeSimple } from "@oh-my-pi/pi-ai";
import { getAgentDir } from "@oh-my-pi/pi-utils";
import type { TriageDeps } from "./result-triage";

export const productionTriageDeps: TriageDeps = {
	async loadRawConfig() {
		const file = Bun.file(path.join(getAgentDir(), "harness-policy.json"));
		// Absent file is the documented off state; read/parse errors propagate to the handler's config catch.
		if (!(await file.exists())) return undefined;
		return await file.json();
	},
	digestDeps: ctx => ({
		resolveModel: spec => ctx.models.resolve(spec),
		getApiKey: model => ctx.modelRegistry.getApiKey(model),
		complete: (model, context, options) => completeSimple(model, context, options),
	}),
};
