import { describe, expect, test, mock } from 'claude-code/testing'
import type { AgentInfo, On, RenderElement } from 'claude-code'

import type { Cumul } from '../types'
import { colonnes, duree, tete } from '../hooks/rendu'

const PLUGIN = 'couts-session'

type Monde = { sessionId: string; startedAt: number; agents: AgentInfo[] }

/** Le moteur sous le plugin : session, agents (liste modifiable), store en mémoire. */
function monde(on: On, store: Record<string, unknown> = {}): Monde {
  const m: Monde = { sessionId: 'S1', startedAt: 1000, agents: [] }
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }) as RenderElement)
  on('store.get', (_$, e) => ({ value: store[e.key] }))
  on('store.set', (_$, e) => ((store[e.key] = e.value), { value: undefined }))
  on('store.delete', (_$, e) => (delete store[e.key], { value: undefined }))
  on('store.keys', () => ({ value: Object.keys(store) }))
  on('ui.log', () => ({ value: undefined }))
  on('session.id', () => ({ value: m.sessionId }))
  on('session.usage', () => ({
    value: { startedAt: m.startedAt, context: { window: 200000, tokens: 1, percent: 0 }, rateLimits: [], cost: { usd: 1 } },
  }))
  on('agent.list', () => ({ value: m.agents }))
  on('agent.spawn', () => ({ model: 'claude-sonnet-5-5', agentId: 'A1' }))
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.end', (_$, e) => ({ sessionId: e.sessionId }))
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

const fin = (agentId: string, avecUsage = true) => ({
  answer: '',
  durationMs: 10,
  isAborted: !avecUsage,
  turnId: `t-${Math.random()}`,
  reason: avecUsage ? ('answer' as const) : ('aborted' as const),
  agentId,
  usage: avecUsage
    ? {
        model: 'claude-sonnet-5-5',
        input_tokens: 1_000,
        output_tokens: 4_000,
        cache_read_input_tokens: 1_000_000,
        cache_creation_input_tokens: 100_000,
      }
    : undefined,
})

const debut = (agentId: string) => ({ prompt: 'x', turnId: `s-${Math.random()}`, agentId })

const props = (bodyColumns: number) => ({
  hasSurvey: false,
  isWorking: false,
  maxRows: 20,
  bodyColumns,
  scroll: { offset: 0, bodyRows: 19 },
  view: {},
})
const plein = { columns: 120, rows: 40, isFullscreen: true }

async function texte(ui: { findAll: (q: { type: string }) => Promise<{ text: string }[]> }) {
  return (await ui.findAll({ type: 'Text' })).map(t => t.text)
}
const monter = ($: Parameters<Parameters<typeof test>[1]>[0], largeur = 100) =>
  $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: props(largeur), viewport: plein })

const enTete = async (ui: { find: (q: { key: string }) => Promise<unknown> }) => JSON.stringify(await ui.find({ key: 'niveau' }))

describe('sous-agents en cours', () => {
  test('lancement : en cours aux niveaux 1 et 2, durée rafraîchie, puis les chiffres au turn.complete', async ($, on) => {
    const m = monde(on)
    const horloge = mock.clock(on, { now: 10_000 })
    await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
    await $.agent.spawn(lancement('Implémente la story 3', 'dev-story'))
    m.agents = [{ id: 'A1', description: 'Implémente la story 3', type: 'dev-story', status: 'running' }]
    const ui = await monter($)

    // Niveau 0 : mention discrète à la fin de la ligne, avant la flèche.
    expect(await enTete(ui)).toMatch(/estimé · ⏳ 1 en cours ▸/)
    expect(await texte(ui)).toHaveLength(0)

    // Niveau 1 : ligne en cours à la place du coût et de l'impact.
    await ui.press({ key: 'niveau' })
    let lignes = await texte(ui)
    expect(lignes).toContain('· dev-story · ⏳ en cours · 0 s · sonnet-5-5 « Implémente la story 3 »')

    // 30 s plus tard le battement redessine avec la durée écoulée.
    await horloge.advance(30_000)
    lignes = await texte(ui)
    expect(lignes.some(l => l.includes('⏳ en cours · 30 s'))).toBe(true)
    await ui.press({ key: 'niveau' }) // niveau 2 : même liste
    expect((await texte(ui)).some(l => l.includes('⏳ en cours · 30 s'))).toBe(true)

    // Fin avec usage : plus de ⏳, la ligne prend les chiffres.
    await $.turn.complete(fin('A1'))
    lignes = await texte(ui)
    expect(lignes.some(l => l.includes('⏳'))).toBe(false)
    expect(lignes.some(l => l.startsWith('· dev-story · ') && l.includes('$') && l.includes('CO₂e'))).toBe(true)
    expect(await enTete(ui)).not.toContain('en cours')
  })

  test('le minuteur s’arrête quand plus rien ne tourne', async ($, on) => {
    monde(on)
    const horloge = mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('x', 'Explore'))
    await $.turn.complete(fin('A1'))
    const ui = await monter($)
    await horloge.advance(120_000)
    expect(await enTete(ui)).not.toContain('en cours')
  })

  test('interrompu ou en échec (tour sans usage) : plus en cours, sans ligne chiffrée', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, store)
    mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('Relit', 'reviewer'))
    const ui = await monter($)
    expect(await enTete(ui)).toContain('⏳ 1 en cours')
    await $.turn.complete(fin('A1', false))
    expect(await enTete(ui)).not.toContain('en cours')
    await ui.press({ key: 'niveau' })
    const lignes = await texte(ui)
    expect(lignes.some(l => l.includes('reviewer') || l.includes('⏳'))).toBe(false)
  })

  test('fin sans turn.complete : le battement retire un agent que la liste dit tué', async ($, on) => {
    const m = monde(on)
    const horloge = mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('Long', 'general-purpose'))
    const ui = await monter($)
    expect(await enTete(ui)).toContain('⏳ 1 en cours')
    m.agents = [{ id: 'A1', description: 'Long', type: 'general-purpose', status: 'killed' }]
    await horloge.advance(30_000)
    expect(await enTete(ui)).not.toContain('en cours')
  })

  test('absent de la liste : tenu pour fini après un délai, pas avant', async ($, on) => {
    monde(on)
    const horloge = mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('Long', 'general-purpose'))
    const ui = await monter($)
    await horloge.advance(30_000)
    expect(await enTete(ui)).toContain('⏳ 1 en cours') // pas encore listé : on attend
    await horloge.advance(30_000)
    expect(await enTete(ui)).not.toContain('en cours')
    await horloge.advance(120_000) // minuteur arrêté, rien ne revient
    expect(await enTete(ui)).not.toContain('en cours')
  })

  test('rechargement : session.start relance le battement des en-cours survivants', async ($, on) => {
    // État tel qu'un rechargement le laisse : un en-cours dans $.store (persisté par `marquer`),
    // aucun minuteur du module (aucun lancement vu par ce module). `synchroniser` le garde « en cours »
    // puisque `$.agent.list()` le dit encore actif : un rechargement du mod, pas une reprise --resume.
    const store: Record<string, unknown> = {
      'session:S1': {
        sessionId: 'S1',
        startedAt: 1000,
        tours: 0,
        modeles: {},
        agents: {},
        enCours: { B7: { type: 'Explore', description: 'Cherche', debut: 0 } },
      },
    }
    const m = monde(on, store)
    const horloge = mock.clock(on, { now: 0 })
    m.agents = [{ id: 'B7', description: 'Cherche', type: 'Explore', status: 'running' }]
    await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
    const ui = await monter($)
    expect(await enTete(ui)).toContain('⏳ 1 en cours')
    m.agents = [{ id: 'B7', description: 'Cherche', type: 'Explore', status: 'killed' }]
    await horloge.advance(30_000)
    expect(await enTete(ui)).not.toContain('en cours')
  })

  test('reprise : le modèle affiché est le dernier utilisé', async ($, on) => {
    const m = monde(on)
    mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('Étape 1', 'dev-story'))
    await $.turn.complete(fin('A1'))
    const opus = fin('A1')
    await $.turn.complete({ ...opus, usage: { ...opus.usage!, model: 'claude-opus-5-5' } })
    await $.turn.complete(fin('A1')) // sonnet de nouveau : il redevient le dernier
    await $.turn.start(debut('A1'))
    m.agents = [{ id: 'A1', description: 'Étape 1', type: 'dev-story', status: 'running' }]
    const ui = await monter($)
    await ui.press({ key: 'niveau' })
    expect((await texte(ui)).some(l => l.includes('⏳ en cours') && l.includes('sonnet-5-5'))).toBe(true)
  })

  test('reprise (SendMessage) : un tour de plus le remet en cours ; un agent inconnu n’est pas inventé', async ($, on) => {
    monde(on)
    mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('Étape 1', 'dev-story'))
    await $.turn.complete(fin('A1'))
    const ui = await monter($)
    expect(await enTete(ui)).not.toContain('en cours')
    await $.turn.start(debut('A1'))
    expect(await enTete(ui)).toContain('⏳ 1 en cours')
    await $.turn.complete(fin('A1'))
    await $.turn.start(debut('FORK-DU-MOTEUR'))
    expect(await enTete(ui)).not.toContain('en cours')
  })

  test('/clear : les en-cours de l’ancienne session disparaissent', async ($, on) => {
    const m = monde(on)
    mock.clock(on, { now: 0 })
    await $.agent.spawn(lancement('x', 'Explore'))
    const ui = await monter($)
    expect(await enTete(ui)).toContain('en cours')
    await $.session.end({ reason: 'clear', sessionId: 'S1', resume: {} as never })
    m.sessionId = 'S2'
    m.startedAt = 5000
    const apres = await monter($)
    expect(await enTete(apres)).not.toContain('en cours')
  })

  test('largeur étroite : la mention tombe la première, les lignes tiennent', async ($, on) => {
    monde(on, { niveau: 2 })
    mock.clock(on, { now: 0 })
    await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
    await $.agent.spawn(lancement('Une description assez longue pour être coupée', 'dev-story'))
    const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: props(36) })
    const lignes = await texte(ui)
    expect(lignes.some(l => l.includes('⏳ en cours'))).toBe(true)
    for (const l of lignes) expect(colonnes(l)).toBeLessThanOrEqual(36)
    const cumul: Cumul = {
      sessionId: 'S1',
      startedAt: 1,
      tours: 0,
      modeles: {},
      agents: {},
      enCours: { A1: { type: 'x', description: '', debut: 0 }, A2: { type: 'y', description: '', debut: 0 } },
    }
    expect(tete(cumul, '▸', 200)).toMatch(/· ⏳ 2 en cours ▸$/)
    const court = tete(cumul, '▸', 52)
    expect(court).not.toContain('⏳')
    expect(colonnes(court)).toBeLessThanOrEqual(52)
  })

  test('ordre de coupe : mention, 🧠, libellés ; coût et carbone restent', () => {
    const cumul: Cumul = {
      sessionId: 'S1',
      startedAt: 1,
      tours: 1,
      modeles: { 'claude-opus-5-5': { input: 1000, output: 62_000, cacheRead: 17_000_000, cacheWrite: 0 } },
      agents: {},
      enCours: { A1: { type: 'x', description: '', debut: 0 } },
    }
    const plein = tete(cumul, '▸', 300, 238_000)
    expect(plein).toMatch(/💰 ≈ .+ \$ · 📖 17 M lus · 🪶 62 k écrits · 🧠 238 k · 🌱 .+ estimé · ⏳ 1 en cours ▸$/)
    const sans = (l: number) => tete(cumul, '▸', l, 238_000)
    const w = colonnes(plein)
    expect(sans(w - 1)).not.toContain('⏳')
    expect(sans(w - 1)).toContain('🧠 238 k')
    const sansMention = colonnes(sans(w - 1))
    expect(sans(sansMention - 1)).not.toContain('🧠')
    expect(sans(sansMention - 1)).toContain('lus')
    const sansCtx = colonnes(sans(sansMention - 1))
    const etroit = sans(sansCtx - 1)
    expect(etroit).toMatch(/📖 17 M · 🪶 62 k · 🌱/)
    expect(etroit).toContain('💰')
    expect(etroit).not.toContain('lus')
    expect(colonnes(etroit)).toBeLessThan(sansCtx)
  })

  test('emoji du plan de base à présentation emoji : deux colonnes', () => {
    for (const e of ['⏳', '⌛', '⚡', '✅', '❌', '⭐']) expect(colonnes(e)).toBe(2)
    expect(colonnes('▸ ▾ ₂ é')).toBe(7)
    expect(colonnes('💰')).toBe(2)
  })

  test('durées lisibles', () => {
    expect(duree(0)).toBe('0 s')
    expect(duree(45_000)).toBe('45 s')
    expect(duree(185_000)).toBe('3 min 05')
    expect(duree(3_900_000)).toBe('1 h 05')
  })
})
