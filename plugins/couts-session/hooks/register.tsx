import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, TurnUsage } from 'claude-code'

import type { Cumul, Niveau } from '../types'
import { additionner, VIDE } from './calcul'
import { corps, resume } from './rendu'
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

async function persister($: EngineInterface, cumul: Cumul | null): Promise<void> {
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

async function changerNiveau($: EngineInterface, delta: 1 | -1): Promise<void> {
  const niveau = await update($, niveauRef, n => Math.min(2, Math.max(0, n + delta)) as Niveau)
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
  })

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
        const neuf = await update($, cumulRef, c => ajouter(c ?? courant, usage, agentId, agent))
        await persister($, neuf)
      })
    }
    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const cumul = await read($, cumulRef)
    const niveau = await read($, niveauRef)
    const largeur = Math.max(20, e.props.bodyColumns)
    const boutons = niveau === 0 ? ['plus'] : niveau === 1 ? ['plus', 'moins'] : ['moins']
    const place = boutons.length * 6
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
    const tete = resume(cumul)
    const lignes = corps({ cumul, niveau, largeur, lignesMax: e.props.maxRows, coutMoteur, contexte })
    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Text key="resume" dimColor wrap="truncate-end">
            {tete.length + place > largeur ? `${tete.slice(0, Math.max(1, largeur - place - 1))}…` : tete}
          </Text>
          {boutons.includes('plus') && (
            <Button key="plus" label="+" hotkey="d" onPress={() => changerNiveau($, 1)} />
          )}
          {boutons.includes('moins') && (
            <Button key="moins" label="−" hotkey="r" onPress={() => changerNiveau($, -1)} />
          )}
        </Box>
        {lignes.map((ligne, i) => (
          <Text key={`l${i}`} dimColor wrap="truncate-end">
            {ligne}
          </Text>
        ))}
      </Box>
    )
  })
}
