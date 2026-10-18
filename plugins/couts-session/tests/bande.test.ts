import { describe, expect, test } from 'claude-code/testing'
import type { On, RenderElement, SessionContextBreakdown } from 'claude-code'

import type { Cumul } from '../types'

const PLUGIN = 'couts-session'
const SURFACES = ['terminal', 'desktop'] as const

const BREAKDOWN = {
  categories: [
    { name: 'System prompt', tokens: 3000, color: 'promptBorder', isDeferred: false, kind: 'used' },
    { name: 'Messages', tokens: 47000, color: 'permission', isDeferred: false, kind: 'used' },
    { name: 'MCP tools (deferred)', tokens: 9000, color: 'inactive', isDeferred: true, kind: 'deferred' },
    { name: 'Free space', tokens: 150000, color: 'inactive', isDeferred: false, kind: 'free' },
  ],
  totalTokens: 50000,
  maxTokens: 200000,
  rawMaxTokens: 200000,
  percentage: 25,
} as unknown as SessionContextBreakdown

type Monde = { sessionId: string; startedAt: number; breakdowns: number; fulls: number }

/** Le moteur sous le plugin : session, usage, agents, fin de tour, store en mémoire (lisible). */
function monde(on: On, store: Record<string, unknown> = {}): Monde {
  const m: Monde = { sessionId: 'S1', startedAt: 1000, breakdowns: 0, fulls: 0 }
  on('store.get', (_$, e) => ({ value: store[e.key] }))
  on('store.set', (_$, e) => ((store[e.key] = e.value), { value: undefined }))
  on('store.delete', (_$, e) => (delete store[e.key], { value: undefined }))
  on('store.keys', () => ({ value: Object.keys(store) }))
  on('ui.log', () => ({ value: undefined }))
  on('session.id', () => ({ value: m.sessionId }))
  on('session.usage', (_$, e) => {
    if (e.breakdown === 'summary') m.breakdowns += 1
    if (e.breakdown === 'full') m.fulls += 1
    return {
      value: {
        startedAt: m.startedAt,
        context: { window: 200000, tokens: 50000, percent: 25, breakdown: e.breakdown ? BREAKDOWN : undefined },
        rateLimits: [],
        cost: { usd: 1.5 },
      },
    }
  })
  on('agent.list', () => ({ value: [] }))
  on('agent.spawn', () => ({ model: 'claude-sonnet-5-5', agentId: 'A1' }))
  on('turn.complete', () => ({ text: '' }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  return m
}

const lancement = (description: string, subagentType: string) => ({
  tool_use_id: 'tu1',
  prompt: 'x',
  description,
  subagentType,
  provider: { plugin: 'engine', tier: 'core' as const },
  parentModel: 'claude-opus-5-5',
  background: false,
  fork: false,
})

const tour = (model: string, sortie: number, agentId?: string) => ({
  answer: '',
  durationMs: 10,
  isAborted: false,
  turnId: `t-${Math.random()}`,
  reason: 'answer' as const,
  agentId,
  usage: {
    model,
    input_tokens: 1_000,
    output_tokens: sortie,
    cache_read_input_tokens: 1_000_000,
    cache_creation_input_tokens: 100_000,
  },
})

const props = (bodyColumns: number) => ({
  hasSurvey: false,
  isWorking: false,
  maxRows: 20,
  bodyColumns,
  scroll: { offset: 0, bodyRows: 19 },
  view: {},
})

async function texte(ui: { findAll: (q: { type: string }) => Promise<{ text: string }[]> }) {
  return (await ui.findAll({ type: 'Text' })).map(t => t.text)
}

describe('cumuls', () => {
  test('main et sous-agent, par modèle, gardés dans le store de la session', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, store)
    await $.agent.spawn(lancement('Implémente la story 3', 'dev-story'))
    await $.turn.complete(tour('claude-opus-5-5', 2000))
    await $.turn.complete(tour('claude-sonnet-5-5', 5000, 'A1'))
    await $.turn.complete(tour('claude-sonnet-5-5', 1000, 'A1'))
    const value = store['session:S1'] as Cumul | undefined
    expect(value?.tours).toBe(3)
    expect(value?.modeles['claude-sonnet-5-5']).toEqual({
      input: 2000,
      output: 6000,
      cacheRead: 2_000_000,
      cacheWrite: 200_000,
    })
    expect(value?.agents['A1']?.type).toBe('dev-story')
    expect(value?.agents['A1']?.description).toBe('Implémente la story 3')
    expect(Object.keys(value?.agents['A1']?.modeles ?? {})).toEqual(['claude-sonnet-5-5'])
    expect(store['sessions']).toEqual(['S1'])
  })

  test('un tour sans usage (interrompu) ne compte pas', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, store)
    await $.turn.complete({ ...tour('claude-opus-5-5', 10), usage: undefined, isAborted: true, reason: 'aborted' })
    expect(store['session:S1']).toBeUndefined()
  })

  test('reprise depuis le store, remise à zéro quand startedAt change (/clear)', async ($, on) => {
    const avant = {
      sessionId: 'S1',
      startedAt: 1000,
      tours: 1,
      modeles: { 'claude-opus-5-5': { input: 1, output: 1, cacheRead: 1, cacheWrite: 1 } },
      agents: {},
    }
    const store: Record<string, unknown> = { 'session:S1': avant }
    const m = monde(on, store)
    await $.turn.complete(tour('claude-opus-5-5', 10))
    expect((store['session:S1'] as Cumul).tours).toBe(2)
    m.startedAt = 5000
    await $.turn.complete(tour('claude-opus-5-5', 10))
    expect((store['session:S1'] as Cumul).tours).toBe(1)
    expect((store['session:S1'] as Cumul).startedAt).toBe(5000)
  })
})

describe('bande', () => {
  for (const surface of SURFACES) {
    test(`trois niveaux, boutons et niveau gardé (${surface})`, async ($, on) => {
      const store: Record<string, unknown> = {}
      const m = monde(on, store)
      await $.agent.spawn(lancement('Relit la story', 'reviewer'))
      await $.turn.complete(tour('claude-opus-5-5', 2000))
      await $.turn.complete(tour('claude-sonnet-5-5', 3000, 'A1'))
      const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: props(100) })

      // 1. replié : une ligne, sans tableau.
      let lignes = await texte(ui)
      expect(lignes).toHaveLength(1)
      expect(lignes[0]).toMatch(/^≈ .+ \$ · .+ tok · .+CO₂e estimé$/)
      expect(await ui.find({ key: 'plus' })).toBeDefined()
      expect(await ui.find({ key: 'moins' })).toBeUndefined()

      // 2. déplié : tableau par modèle, sous-agent, pied.
      await ui.press({ key: 'plus' })
      expect(store['niveau']).toBe(1)
      lignes = await texte(ui)
      expect(lignes.some(l => l.startsWith('modèle') && l.includes('écrit') && l.includes('gCO₂e'))).toBe(true)
      expect(lignes.some(l => l.startsWith('opus-5-5'))).toBe(true)
      expect(lignes.some(l => l.startsWith('· reviewer · ') && l.endsWith('sonnet-5-5 « Relit la story »'))).toBe(true)
      expect(lignes.some(l => l.includes('EcoLogits') && l.includes('sortie seule'))).toBe(true)
      expect(lignes.some(l => l.includes('/cost du moteur : 1,50 $'))).toBe(true)
      expect(lignes.some(l => l.startsWith('Contexte'))).toBe(false)
      expect(m.breakdowns).toBe(0)

      // 3. déplié deux fois : contexte, estimation locale, jamais « full ».
      await ui.press({ key: 'plus' })
      lignes = await texte(ui)
      expect(lignes.some(l => l.startsWith('Contexte : 50 k / 200 k (25 %)'))).toBe(true)
      expect(lignes.some(l => l.includes('Messages : 47 k'))).toBe(true)
      expect(lignes.some(l => l.includes('deferred'))).toBe(false)
      expect(m.breakdowns).toBeGreaterThan(0)
      expect(m.fulls).toBe(0)
      expect(await ui.find({ key: 'plus' })).toBeUndefined()

      await ui.press({ key: 'moins' })
      await ui.press({ key: 'moins' })
      expect(await texte(ui)).toHaveLength(1)
      expect(store['niveau']).toBe(0)
    })

    test(`largeur étroite (${surface})`, async ($, on) => {
      monde(on, { niveau: 2 })
      await $.session.start({ cwd: '/', surface, isInteractive: true })
      await $.turn.complete(tour('claude-opus-5-5', 2000))
      const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: props(36) })
      const lignes = await texte(ui)
      expect(lignes.some(l => l.startsWith('Contexte'))).toBe(true)
      for (const l of lignes.slice(1)) expect(l.length).toBeLessThanOrEqual(36)
      expect(lignes.some(l => l.startsWith('modèle') && !l.includes('écrit'))).toBe(true)
    })
  }

  test('cède la place à un sondage', async ($, on) => {
    monde(on)
    on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
      const { Text } = $.ui.resolve(e)
      return h(Text, {}, 'sondage') as RenderElement
    })
    const ui = await $.ui.mount({
      plugin: PLUGIN,
      surface: 'terminal',
      component: 'AbovePrompt',
      props: { ...props(80), hasSurvey: true },
    })
    expect(await ui.find({ key: 'resume' })).toBeUndefined()
    expect(await texte(ui)).toEqual(['sondage'])
  })
})
