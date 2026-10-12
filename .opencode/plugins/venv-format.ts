import type { Plugin } from "@opencode-ai/plugin"

// OpenCode equivalent of the Claude hooks in .claude/hooks/:
// - venv.sh        -> shell.env: put venv/bin on PATH so pytest/flake8/etc. work
// - format.sh      -> tool.execute.after: isort + black edited .py files
//                     (edit/write, plus apply_patch used by GPT models)
export const venvFormatPlugin: Plugin = async ({ worktree, directory, $ }) => {
  const projectDir = worktree ?? directory

  return {
    "shell.env": async (_input, output) => {
      const venvBin = `${projectDir}/venv/bin`
      const currentPath = output.env?.PATH ?? process.env.PATH ?? ""
      if (!currentPath.split(":").includes(venvBin)) {
        output.env.PATH = `${venvBin}:${currentPath}`
      }
      output.env.CLAUDE_PROJECT_DIR = projectDir
    },

    "tool.execute.after": async (input) => {
      for (const file of editedFiles(input.tool, input.args)) {
        if (!file.endsWith(".py")) continue
        await $`${".claude/hooks/format.sh"} ${file}`.cwd(projectDir).quiet()
      }
    },
  }
}

// Paths touched by a file-editing tool call; apply_patch lists them in its
// patch text ("*** Add File: x", "*** Update File: x", "*** Move to: x").
function editedFiles(tool: string, args: any): string[] {
  if (tool === "edit" || tool === "write") {
    return typeof args?.filePath === "string" ? [args.filePath] : []
  }
  if (tool === "apply_patch" && typeof args?.patchText === "string") {
    const re = /^\*\*\* (?:Add File|Update File|Move to): (.+)$/gm
    return [...args.patchText.matchAll(re)].map((m) => m[1].trim())
  }
  return []
}
