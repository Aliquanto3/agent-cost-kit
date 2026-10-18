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

/** Un sous-agent qui tourne : lancé ou repris, sans `turn.complete` encore. `debut` en ms depuis l'époque. */
export type AgentEnCours = {
  type: string
  description: string
  model?: string
  debut: number
}

/** Les cumuls d'une session : tous les tours par modèle, et les sous-agents à part. */
export type Cumul = {
  sessionId: string
  startedAt: number
  tours: number
  modeles: Record<string, Compteurs>
  agents: Record<string, AgentCumul>
  /** Les sous-agents qui tournent (absent d'un cumul écrit avant 0.1.2) ; jamais repris d'une session stockée. */
  enCours?: Record<string, AgentEnCours>
}

/** 0 : une ligne ; 1 : tableau par modèle et sous-agents ; 2 : plus le contexte. */
export type Niveau = 0 | 1 | 2

declare module 'claude-code' {
  interface PluginState {
    'couts-session': { cumul: Cumul | null; niveau: Niveau; maintenant: number }
  }
}
