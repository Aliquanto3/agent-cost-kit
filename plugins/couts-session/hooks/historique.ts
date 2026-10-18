import type { Compteurs, Cumul } from '../types'
import { additionner, VIDE } from './calcul'

/** Fenêtre de temps (ms depuis l'époque) des réponses à compter, bornes comprises. */
export type Fenetre = { debut: number; fin: number }

/** Tokens par modèle, dans l'ordre où les modèles apparaissent. */
export type ParModele = Record<string, Compteurs>

/** Un sous-agent relu : sa fiche et ses tokens. */
export type AgentRepris = { type: string; description: string; modeles: ParModele }

/** Ce que les transcriptions donnent avant la fusion dans le cumul. */
export type Historique = {
  tours: number
  modeles: ParModele
  agents: Record<string, AgentRepris>
  partielle: boolean
  jusqua: number
}

type Usage = Record<string, unknown>
const nombre = (x: unknown) => (typeof x === 'number' && Number.isFinite(x) ? x : 0)

/**
 * Un appel par `message.id` : une même réponse occupe plusieurs lignes (un bloc par ligne), on garde
 * l'usage dont `output_tokens` est le plus grand, comme `appels()` de mesurer_couts.py. `vus` reçoit
 * les ids comptés et écarte ceux déjà comptés ailleurs (autres fichiers, session reprise qui recopie
 * l'ancienne). Ignorés : lignes non JSON, sans id, hors assistant, modèle `<synthetic>`, hors
 * fenêtre, et `isSidechain: true` si `sansSidechain` (fichier de la session principale).
 */
export function analyser(texte: string, fenetre: Fenetre, vus: Set<string>, sansSidechain = false): ParModele {
  const appels = new Map<string, { modele: string; usage: Usage }>()
  for (const ligne of texte.split('\n')) {
    if (!ligne.trim()) continue
    let entree: any
    try {
      entree = JSON.parse(ligne)
    } catch {
      continue
    }
    const message = entree?.message
    if (!message || message.role !== 'assistant' || typeof message.id !== 'string' || !message.id) continue
    if (sansSidechain && entree.isSidechain === true) continue
    const modele = String(message.model ?? '')
    if (!modele || modele === '<synthetic>') continue
    const instant = Date.parse(String(entree.timestamp ?? ''))
    if (!(instant >= fenetre.debut && instant <= fenetre.fin)) continue
    if (vus.has(message.id)) continue
    const usage: Usage = message.usage ?? {}
    const avant = appels.get(message.id)
    if (!avant || nombre(usage.output_tokens) >= nombre(avant.usage.output_tokens)) appels.set(message.id, { modele, usage })
  }
  const modeles: ParModele = {}
  for (const [id, { modele, usage }] of appels) {
    vus.add(id)
    const tour: Compteurs = {
      input: nombre(usage.input_tokens),
      output: nombre(usage.output_tokens),
      cacheRead: nombre(usage.cache_read_input_tokens),
      cacheWrite: nombre(usage.cache_creation_input_tokens),
    }
    modeles[modele] = additionner(modeles[modele] ?? VIDE, tour)
  }
  return modeles
}

/** Dossier de projet de Claude Code : tout caractère hors [A-Za-z0-9] devient « - ». */
export function nomDossierProjet(cwd: string): string {
  return cwd.replace(/[^A-Za-z0-9]/g, '-')
}

/** `agent-<id>.jsonl` -> id, sinon undefined. */
export function idSousAgent(nomFichier: string): string | undefined {
  return /^agent-(.+)\.jsonl$/.exec(nomFichier)?.[1]
}

function sommer(a: ParModele, b: ParModele): ParModele {
  const somme = { ...a }
  for (const [m, c] of Object.entries(b)) somme[m] = additionner(somme[m] ?? VIDE, c)
  return somme
}

/**
 * Ajoute l'historique au cumul (qui a pu recevoir des `turn.complete` pendant la lecture) et pose la
 * marque `reprise`. Un sous-agent déjà connu du cumul voit ses tokens additionnés, pas écrasés.
 */
export function fusionner(c: Cumul, h: Historique): Cumul {
  const agents = { ...c.agents }
  for (const [id, a] of Object.entries(h.agents)) {
    const connu = agents[id]
    agents[id] = connu ? { ...connu, modeles: sommer(connu.modeles, a.modeles) } : a
  }
  return {
    ...c,
    tours: c.tours + h.tours,
    modeles: sommer(c.modeles, h.modeles),
    agents,
    reprise: { jusqua: h.jusqua, ...(h.partielle ? { partielle: true } : {}) },
  }
}
