import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, TurnUsage } from 'claude-code'

import type { Cumul, Niveau } from '../types'
import { additionner, VIDE } from './calcul'
import { colonnes, corps, couper, resume } from './rendu'
import type { Contexte } from './rendu'

const cumulRef = atom({ plugin: 'couts-session', key: 'cumul' } as const, null)
const NIVEAU = { plugin: 'couts-session', key: 'niveau' } as const
const niveauRef = atom(NIVEAU, 0)

/** Sessions gardées dans `$.store` pour `--resume` ; les plus anciennes sont effacées. */
const SESSIONS_GARDEES = 30
const cleSession = (id: string) => `session:${id}`

function vide(sessionId: string, startedAt: number): Cumul {
  return { sessionId, startedAt, tours: 0, modeles: {}, agents: {} }
}

/** Met `$.state` sur la session courante : reprise depuis `$.store`, ou zéro après `/clear`. */
async function synchroniser($: EngineInterface): Promise<Cumul> {
  const [id, usage] = await Promise.all([$.session.id(), $.session.usage()])
  const tenu = await read($, cumulRef)
  if (tenu && tenu.sessionId === id && tenu.startedAt === usage.startedAt) return tenu
  const stocke = (await $.store.get(cleSession(id))) as Cumul | undefined
  const neuf = stocke && stocke.startedAt === usage.startedAt ? stocke : vide(id, usage.startedAt)
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
  const fiche = {
    ...avant,
    modeles: { ...avant.modeles, [u.model]: additionner(avant.modeles[u.model] ?? VIDE, tour) },
  }
  return { ...c, tours: c.tours + 1, modeles, agents: { ...c.agents, [agentId]: fiche } }
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
      await synchroniser($)
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
      })
    }
    return result
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const usage = e.usage
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
    const tete = couper(`${resume(cumul)} ${niveau < 2 ? '▸' : '▾'}`, largeur - place)
    const lignes = corps({ cumul, niveau, largeur, lignesMax: e.props.maxRows, coutMoteur, contexte })
    const libelle = niveau === 0 ? 'déplier' : niveau === 1 ? 'contexte' : 'replier'
    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Button key="niveau" label={libelle} plain hotkey="1" dimColor onPress={() => changerNiveau($, 'suivant')}>
            {tete}
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
