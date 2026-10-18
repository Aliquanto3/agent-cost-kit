import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer, TurnUsage } from 'claude-code'

import type { Cumul, Niveau } from '../types'
import { additionner, VIDE } from './calcul'
import { colonnes, corps, tete } from './rendu'
import type { Contexte } from './rendu'

const cumulRef = atom({ plugin: 'couts-session', key: 'cumul' } as const, null)
const NIVEAU = { plugin: 'couts-session', key: 'niveau' } as const
const niveauRef = atom(NIVEAU, 0)
/** Heure (ms) du dernier rafraîchissement : l'écrire redessine la bande, qui en tire les durées. */
const maintenantRef = atom({ plugin: 'couts-session', key: 'maintenant' } as const, 0)

/** Période de rafraîchissement des durées des sous-agents en cours. */
const PERIODE_MS = 30_000
/**
 * Un en-cours absent de `$.agent.list()` depuis au moins ce délai est tenu pour fini : le moteur
 * retire la tâche d'un sous-agent quelque temps après sa fin, et un tué peut n'avoir aucun `turn.complete`.
 */
const ABSENT_MS = 2 * PERIODE_MS

/** Sessions gardées dans `$.store` pour `--resume` ; les plus anciennes sont effacées. */
const SESSIONS_GARDEES = 30
const cleSession = (id: string) => `session:${id}`

function vide(sessionId: string, startedAt: number): Cumul {
  return { sessionId, startedAt, tours: 0, modeles: {}, agents: {}, enCours: {} }
}

/** Met `$.state` sur la session courante : reprise depuis `$.store`, ou zéro après `/clear`. */
async function synchroniser($: EngineInterface): Promise<Cumul> {
  const [id, usage] = await Promise.all([$.session.id(), $.session.usage()])
  const tenu = await read($, cumulRef)
  if (tenu && tenu.sessionId === id && tenu.startedAt === usage.startedAt) return tenu
  const stocke = (await $.store.get(cleSession(id))) as Cumul | undefined
  // Un cumul relu du store n'a plus rien « en cours » : les sous-agents de l'ancien process sont finis.
  const neuf = stocke && stocke.startedAt === usage.startedAt ? { ...stocke, enCours: {} } : vide(id, usage.startedAt)
  await update($, cumulRef, () => neuf)
  return neuf
}

/**
 * Écrit dans `$.store` le cumul tel que `$.state` le tient au moment d'écrire. `$.store` n'a pas
 * d'écriture conditionnelle : deux fins de tour concurrentes (session et sous-agent en arrière-plan)
 * passent donc l'une après l'autre, et la dernière écriture porte toujours le cumul le plus récent.
 */
let file: Promise<void> = Promise.resolve()
function persister($: EngineInterface): Promise<void> {
  const suite = file.then(() => ecrire($))
  file = suite.catch(() => undefined)
  return suite
}

async function ecrire($: EngineInterface): Promise<void> {
  const cumul = await read($, cumulRef)
  if (!cumul) return
  await $.store.set(cleSession(cumul.sessionId), cumul)
  const index = ((await $.store.get('sessions')) as string[] | undefined) ?? []
  const suite = [...index.filter(id => id !== cumul.sessionId), cumul.sessionId]
  for (const ancien of suite.slice(0, Math.max(0, suite.length - SESSIONS_GARDEES))) {
    await $.store.delete(cleSession(ancien))
  }
  await $.store.set('sessions', suite.slice(-SESSIONS_GARDEES))
}

function compteurs(u: TurnUsage) {
  return {
    input: u.input_tokens,
    output: u.output_tokens,
    cacheRead: u.cache_read_input_tokens,
    cacheWrite: u.cache_creation_input_tokens,
  }
}

function ajouter(c: Cumul, u: TurnUsage, agentId?: string, agent?: { type: string; description: string }): Cumul {
  const tour = compteurs(u)
  const modeles = { ...c.modeles, [u.model]: additionner(c.modeles[u.model] ?? VIDE, tour) }
  if (!agentId) return { ...c, tours: c.tours + 1, modeles }
  const avant = c.agents[agentId] ?? { type: agent?.type ?? 'agent', description: agent?.description ?? '', modeles: {} }
  // Le modèle du tour passe en dernier : c'est lui que reprend une reprise (SendMessage).
  const { [u.model]: dejaVu, ...autres } = avant.modeles
  const fiche = { ...avant, modeles: { ...autres, [u.model]: additionner(dejaVu ?? VIDE, tour) } }
  // Le tour est fini : le sous-agent n'est plus en cours (même écriture, sans rendu intermédiaire).
  const { [agentId]: _fini, ...enCours } = c.enCours ?? {}
  return { ...c, tours: c.tours + 1, modeles, agents: { ...c.agents, [agentId]: fiche }, enCours }
}

/**
 * Rafraîchissement des durées : un seul minuteur par module, démarré au premier sous-agent en cours
 * (lancement ou reprise) et arrêté quand plus rien ne tourne. Un rechargement du mod annule ses
 * minuteurs et remet cette variable à zéro alors que `enCours` survit dans `$.state` :
 * `session.start`, qui suit chaque chargement, le relance.
 */
let minuteur: Timer | undefined
function arreter(): void {
  minuteur?.cancel()
  minuteur = undefined
}
function demarrer($: EngineInterface): void {
  if (!minuteur) minuteur = $.clock.every(PERIODE_MS, () => void battre($))
}

/**
 * Un battement : retire les en-cours que `$.agent.list()` dit finis sans `turn.complete` (tué,
 * échec), écrit l'heure pour redessiner, arrête le minuteur s'il ne reste rien. Hors rendu.
 */
async function battre($: EngineInterface): Promise<void> {
  await sansEchec($, async () => {
    const [cumul, id] = await Promise.all([read($, cumulRef), $.session.id()])
    const ids = cumul && cumul.sessionId === id ? Object.keys(cumul.enCours ?? {}) : []
    if (ids.length === 0) return arreter()
    const [liste, maintenant] = await Promise.all([$.agent.list(), $.clock.now()])
    const statuts = new Map(liste.map(a => [a.id, a.status]))
    const finis = ids.filter(i => {
      const statut = statuts.get(i)
      if (statut === undefined) return maintenant - (cumul!.enCours![i]?.debut ?? 0) >= ABSENT_MS
      return statut === 'completed' || statut === 'failed' || statut === 'killed'
    })
    if (finis.length > 0) await retirer($, finis)
    await update($, maintenantRef, () => maintenant)
    const restant = await read($, cumulRef)
    if (Object.keys(restant?.enCours ?? {}).length === 0) arreter()
  })
}

async function retirer($: EngineInterface, ids: string[]): Promise<void> {
  await update($, cumulRef, c => {
    if (!c?.enCours || !ids.some(i => i in c.enCours!)) return c
    const reste = { ...c.enCours }
    for (const i of ids) delete reste[i]
    return { ...c, enCours: reste }
  })
  const c = await read($, cumulRef)
  if (Object.keys(c?.enCours ?? {}).length === 0) arreter()
}

/** Marque un sous-agent en cours (sans toucher à un début déjà noté) et lance le minuteur. */
async function marquer($: EngineInterface, id: string, fiche: { type: string; description: string; model?: string }) {
  const debut = await $.clock.now()
  await update($, cumulRef, c => (c && !c.enCours?.[id] ? { ...c, enCours: { ...c.enCours, [id]: { ...fiche, debut } } } : c))
  await update($, maintenantRef, () => debut)
  demarrer($)
}

/** Ne laisse jamais une erreur du compteur gêner le tour ou la session. */
async function sansEchec($: EngineInterface, travail: () => Promise<void>): Promise<void> {
  try {
    await travail()
  } catch (erreur) {
    $.ui.log(`couts-session : ${erreur instanceof Error ? erreur.message : String(erreur)}`)
  }
}

/** `suivant` fait le tour (replié, tableau, contexte, replié) ; -1 replie d'un niveau. */
async function changerNiveau($: EngineInterface, pas: 'suivant' | -1): Promise<void> {
  const niveau = await update($, niveauRef, n => (pas === 'suivant' ? (n + 1) % 3 : Math.max(0, n - 1)) as Niveau)
  await $.store.set('niveau', niveau)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await sansEchec($, async () => {
      const { version } = await $.state.get(NIVEAU)
      if (version === 0) {
        const stocke = await $.store.get('niveau')
        if (stocke === 0 || stocke === 1 || stocke === 2) await update($, niveauRef, () => stocke)
      }
      const cumul = await synchroniser($)
      // Rechargement à chaud : des en-cours survivent, le minuteur non.
      if (Object.keys(cumul.enCours ?? {}).length > 0) demarrer($)
    })
    return result
  })

  on('agent.spawn', async ($, e, next) => {
    const result = await next(e)
    const { agentId } = result
    if (agentId) {
      await sansEchec($, async () => {
        await synchroniser($)
        const fiche = { type: e.subagentType, description: e.description, modeles: {} }
        await update($, cumulRef, c => (c && !c.agents[agentId] ? { ...c, agents: { ...c.agents, [agentId]: fiche } } : c))
        await marquer($, agentId, { type: e.subagentType, description: e.description, model: result.model })
      })
    }
    return result
  }).catch(($, e, next) => next(e))

  // Reprise d'un sous-agent déjà connu (SendMessage) : un nouveau tour le remet en cours. Un agent
  // inconnu (fork du moteur, workflow) n'est pas inventé.
  on('turn.start', async ($, e, next) => {
    const result = await next(e)
    const { agentId } = e
    if (agentId) {
      await sansEchec($, async () => {
        const courant = await synchroniser($)
        const connu = courant.agents[agentId]
        const liste = connu ? undefined : (await $.agent.list()).find(a => a.id === agentId)
        const fiche = connu ?? liste
        if (fiche) await marquer($, agentId, { type: fiche.type, description: fiche.description, model: Object.keys(connu?.modeles ?? {}).pop() })
      })
    }
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    // Fin de tour, avec ou sans usage (interrompu, échec) : le sous-agent ne tourne plus. Sans
    // usage la ligne « en cours » disparaît, sans trace chiffrée ni mention « interrompu » ; avec
    // usage, `ajouter` la retire dans la même écriture que les chiffres.
    const usage = e.usage
    if (e.agentId && !usage) await sansEchec($, () => retirer($, [e.agentId!]))
    if (usage) {
      await sansEchec($, async () => {
        const courant = await synchroniser($)
        const { agentId } = e
        let agent: { type: string; description: string } | undefined
        if (agentId && !courant.agents[agentId]) {
          const connu = (await $.agent.list()).find(a => a.id === agentId)
          agent = connu ? { type: connu.type, description: connu.description } : { type: 'interne', description: '' }
        }
        await update($, cumulRef, c => ajouter(c && c.sessionId === courant.sessionId ? c : courant, usage, agentId, agent))
        await persister($)
        if (agentId) await retirer($, [agentId]) // arrête le minuteur s'il ne reste rien
      })
    }
    return result
  })

  // /clear (et /resume en cours de process) change l'id de session sans session.start : on vide
  // le cumul tout de suite, sans attendre la fin du prochain tour pour quitter l'ancienne session.
  on('session.end', async ($, e, next) => {
    const result = await next(e)
    if (e.reason === 'clear' || e.reason === 'resume') {
      await sansEchec($, async () => {
        await update($, cumulRef, c => (c && c.sessionId === e.sessionId ? null : c))
      })
    }
    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    // Ce que dessinent les plugins en dessous (et le moteur) reste affiché sous la bande.
    const dessous = await next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const [tenu, id] = await Promise.all([read($, cumulRef), $.session.id()])
    // Garde-fou au rendu (sans écrire) : un cumul d'une autre session n'est pas montré.
    const cumul = tenu && tenu.sessionId === id ? tenu : null
    const niveau = await read($, niveauRef)
    const maintenant = await read($, maintenantRef)
    const largeur = Math.max(20, e.props.bodyColumns)
    // Hors plein écran, le clic n'est pas rapporté : on rappelle la touche (prompt vide, ou ctrl+x tab).
    const aide = e.viewport?.isFullscreen === false ? (niveau === 0 ? ' (touche 1)' : ' (1 / 2)') : ''
    const place = 3 + colonnes(aide) + (niveau > 0 ? 5 : 0)
    let coutMoteur: number | undefined
    let contexte: Contexte | undefined
    if (niveau > 0) {
      const usage = await $.session.usage(
        niveau === 2 ? { breakdown: 'summary', columns: largeur } : undefined,
      )
      coutMoteur = usage.cost?.usd
      const b = usage.context.breakdown
      if (b) {
        contexte = {
          total: b.totalTokens,
          fenetre: b.rawMaxTokens,
          pourcent: b.percentage,
          categories: b.categories
            .filter(k => k.kind !== 'deferred')
            .map(k => ({ nom: k.name, tokens: k.tokens })),
        }
      }
    }
    const ligneTete = tete(cumul, niveau < 2 ? '▸' : '▾', largeur - place)
    const lignes = corps({ cumul, niveau, largeur, lignesMax: e.props.maxRows, coutMoteur, contexte, maintenant })
    const libelle = niveau === 0 ? 'déplier' : niveau === 1 ? 'contexte' : 'replier'
    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Button key="niveau" label={libelle} plain hotkey="1" dimColor onPress={() => changerNiveau($, 'suivant')}>
            {ligneTete}
            {aide ? <Text dimColor>{aide}</Text> : null}
          </Button>
          {niveau > 0 && (
            <Box marginLeft={1}>
              <Button key="moins" label="−" plain hotkey="2" onPress={() => changerNiveau($, -1)} />
            </Box>
          )}
        </Box>
        {lignes.map((ligne, i) => (
          <Text key={`l${i}`} dimColor wrap="truncate-end">
            {ligne}
          </Text>
        ))}
        {dessous}
      </Box>
    )
  })
}
