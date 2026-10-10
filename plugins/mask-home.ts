/**
 * mask-home — keep the home directory path (/Users/<name>) out of chat history.
 *
 * Everything the model sees shows `~` in place of the home directory:
 * the system prompt (env block, instruction headers, skill locations), tool
 * descriptions, tool output/titles/metadata, user text, and replayed history.
 * `~` paths the model writes into tool path args are expanded to absolute
 * paths just before the tool runs (opencode's built-in file tools do not
 * expand `~`).
 *
 * Tool output arrives in two shapes (built-in vs MCP) — see the
 * `tool.execute.after` hook below.
 *
 * The model never sees the absolute path, but the DB still stores it in places
 * plugin hooks cannot reach (verified against opencode 1.18.32):
 *   - tool-call input: opencode persists the args object after
 *     `tool.execute.before` has expanded it, as a copy, so the stored input
 *     holds the absolute path the tool actually ran with
 *   - tool errors: a thrown tool never reaches `tool.execute.after`
 *   - `patch` parts (snapshot file lists), session.directory,
 *     project.worktree, message `path.cwd`/`path.root`
 *   - the workspace-sync `event` table (~/clear-opencode-events.sh wipes it)
 * Replays of all of these to the model are masked by the messages transform.
 */
import type { Plugin } from "@opencode-ai/plugin"
import os from "node:os"
import path from "node:path"

const HOME = os.homedir()
if (!path.isAbsolute(HOME) || HOME === "/") {
  throw new Error(`mask-home: refusing to run with home directory ${JSON.stringify(HOME)}`)
}

// Whole-segment match only: masks /Users/erikchan and /Users/erikchan/x, never
// /Users/erikchan1000 or github.com/erikchan1000.
const HOME_RE = new RegExp(`${HOME.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![A-Za-z0-9._-])`, "g")

const mask = (text: string): string => text.replace(HOME_RE, "~")

// Tool args, metadata and tool state are JSON-serializable (opencode persists
// them as JSON), and the home path contains no JSON-escaped characters, so a
// masked round-trip covers nested values and object keys alike.
const maskJson = <T>(value: T): T => JSON.parse(mask(JSON.stringify(value)))

// Masks an MCP `CallToolResult.content` array in place — exactly the fields
// opencode renders for the model: a `text` item's `text`, and a `resource`
// item's `text` and `uri` (the uri appears in opencode's omitted-binary
// notice and as the attachment filename). `image`, `audio` and
// `resource_link` items put no text in front of the model. MCP requires the
// fields read here, so a missing one is a broken result: throw, naming it.
const maskMcpContent = (tool: string, content: unknown[]): void => {
  const requireString = (value: unknown, field: string): string => {
    if (typeof value !== "string") {
      throw new Error(`mask-home: ${tool} returned MCP content whose ${field} is ${typeof value}, not a string`)
    }
    return value
  }
  for (const item of content as Array<Record<string, unknown>>) {
    if (item.type === "text") {
      item.text = mask(requireString(item.text, "text"))
    } else if (item.type === "resource") {
      const resource = item.resource as Record<string, unknown>
      resource.uri = mask(requireString(resource.uri, "resource.uri"))
      if (resource.text !== undefined) resource.text = mask(requireString(resource.text, "resource.text"))
    }
  }
}

const expand = (value: string): string => {
  if (value === "~") return HOME
  if (value.startsWith("~/")) return path.join(HOME, value.slice(2))
  return value
}

// Built-in tools: read/write/edit `filePath`, glob/grep/list `path`, bash
// `workdir`. The rest cover path-shaped args of MCP tools. `projectPath` is
// codegraph's: without it the model, which never sees the real home path,
// guessed an absolute one (a made-up /Users/<name>) and every query missed
// the index (2026-10-05).
const PATH_KEYS = new Set([
  "filePath", "path", "paths", "workdir", "cwd", "directory", "dir", "root", "localPath", "projectPath",
])

const PATH_NOTE = [
  "",
  "Paths: `~` is the user's home directory and is shown in place of its absolute path.",
  "Tool path arguments (filePath, path, workdir, ...) may start with `~/`; they are expanded automatically.",
  'In bash commands leave `~/` unquoted or write "$HOME/..." — a quoted "~/..." is not expanded by the shell.',
].join("\n")

export const MaskHome: Plugin = async () => {
  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (output.system.length === 0) throw new Error("mask-home: empty system prompt")
      for (let i = 0; i < output.system.length; i++) output.system[i] = mask(output.system[i])
      output.system[output.system.length - 1] += PATH_NOTE
    },

    "tool.definition": async (_input, output) => {
      output.description = mask(output.description)
    },

    "chat.message": async (_input, output) => {
      for (const part of output.parts) {
        if (part.type === "text") part.text = mask(part.text)
      }
    },

    // `output.args` is the very object the tool executes with, so expansion
    // mutates it in place. Only path-named keys are expanded: content args
    // (edit oldString/newString, write content, bash command) must pass through
    // verbatim — a leading "~/" there is text, not a path.
    "tool.execute.before": async (_input, output) => {
      const args = output.args as Record<string, unknown>
      for (const [key, value] of Object.entries(args)) {
        if (!PATH_KEYS.has(key)) continue
        if (typeof value === "string") args[key] = expand(value)
        else if (Array.isArray(value)) args[key] = value.map((v) => (typeof v === "string" ? expand(v) : v))
      }
    },

    // Two result shapes reach this hook (verified against opencode 1.18.33):
    //   - built-in tools and the MCP resource tools pass the declared
    //     `{ title, output, metadata }`;
    //   - an MCP server's tools pass the raw MCP `CallToolResult`
    //     (`{ content: [...] }`, no title/output/metadata) — the plugin SDK
    //     types do not say so — and opencode builds the model's text from
    //     `content` AFTER this hook, so masking `content` masks what the model
    //     sees. Treating that shape as the first one threw on
    //     `mask(undefined)` and made every MCP call report failure after the
    //     server had already run it.
    "tool.execute.after": async (input, output) => {
      const result = output as unknown as Record<string, unknown>
      if (Array.isArray(result.content)) {
        maskMcpContent(input.tool, result.content)
        return
      }
      if (typeof output.title !== "string" || typeof output.output !== "string") {
        throw new Error(
          `mask-home: unrecognised tool.execute.after result shape from ${input.tool} ` +
            `(keys: ${Object.keys(result).join(", ")})`,
        )
      }
      output.title = mask(output.title)
      output.output = mask(output.output)
      if (output.metadata !== undefined) output.metadata = maskJson(output.metadata)
    },

    "experimental.text.complete": async (_input, output) => {
      output.text = mask(output.text)
    },

    // Replayed history: covers sessions recorded before this plugin existed and
    // tool errors, which bypass tool.execute.after.
    "experimental.chat.messages.transform": async (_input, output) => {
      for (const message of output.messages) {
        for (const part of message.parts) {
          if (part.type === "text" || part.type === "reasoning") part.text = mask(part.text)
          else if (part.type === "tool") part.state = maskJson(part.state)
        }
      }
    },
  }
}
