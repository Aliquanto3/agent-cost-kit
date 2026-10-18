/** Tokens cumulés, tels que l'usage de `turn.complete` les compte. */
export type Compteurs = {
  input: number
  output: number
  cacheRead: number
  cacheWrite: number
}

/** Un sous-agent : son type, sa description courte et ses tokens par modèle. */
export type AgentCumul = {
  type: string
  description: string
  modeles: Record<string, Compteurs>
}

/** Les cumuls d'une session : tous les tours par modèle, et les sous-agents à part. */
export type Cumul = {
  sessionId: string
  startedAt: number
  tours: number
  modeles: Record<string, Compteurs>
  agents: Record<string, AgentCumul>
}

/** 0 : une ligne ; 1 : tableau par modèle et sous-agents ; 2 : plus le contexte. */
export type Niveau = 0 | 1 | 2

declare module 'claude-code' {
  interface PluginState {
    'couts-session': { cumul: Cumul | null; niveau: Niveau }
  }
}
