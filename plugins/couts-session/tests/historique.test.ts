import { describe, expect, test, mock } from 'claude-code/testing'
import type { AgentInfo, On } from 'claude-code'

import type { Cumul } from '../types'
import { analyser, nomDossierProjet } from '../hooks/historique'
import { tete } from '../hooks/rendu'

const DEBUT = Date.parse('2026-10-18T10:00:00Z')
const MAINTENANT = Date.parse('2026-10-18T11:00:00Z')
const fenetre = { debut: DEBUT, fin: MAINTENANT }

/** Une ligne de transcription assistant. */
function ligne(id: string, sortie: number, extra: Record<string, unknown> = {}, ts = '2026-10-18T10:30:00Z', modele = 'claude-opus-5-5') {
  return JSON.stringify({
    type: 'assistant',
    isSidechain: false,
    timestamp: ts,
    message: {
      id,
      role: 'assistant',
      model: modele,
      usage: { input_tokens: 2, cache_creation_input_tokens: 100, cache_read_input_tokens: 1000, output_tokens: sortie },
    },
    ...extra,
  })
}

describe('analyser', () => {
  test('lignes multiples d’un même id : une fois, avec la sortie la plus grande', () => {
    const m = analyser([ligne('m1', 5), ligne('m1', 40), ligne('m1', 12)].join('\n'), fenetre, new Set())
    expect(m['claude-opus-5-5']).toEqual({ input: 2, output: 40, cacheRead: 1000, cacheWrite: 100 })
  })

  test('id recopié par une session reprise : compté une fois sur plusieurs textes', () => {
    const vus = new Set<string>()
    analyser(ligne('m1', 10), fenetre, vus)
    expect(analyser([ligne('m1', 10), ligne('m2', 7)].join('\n'), fenetre, vus)['claude-opus-5-5']?.output).toBe(7)
  })

  test('sidechain ignoré dans le fichier principal seulement', () => {
    const l = ligne('m1', 10, { isSidechain: true })
    expect(analyser(l, fenetre, new Set(), true)).toEqual({})
    expect(analyser(l, fenetre, new Set())['claude-opus-5-5']?.output).toBe(10)
  })

  test('hors fenêtre de temps, synthétique, non assistant, sans id et ligne cassée ignorés', () => {
    const texte = [
      ligne('avant', 1, {}, '2026-10-18T09:59:59Z'),
      ligne('apres', 1, {}, '2026-10-18T11:00:01Z'),
      ligne('syn', 1, {}, undefined, '<synthetic>'),
      JSON.stringify({ message: { role: 'user', id: 'u1' } }),
      JSON.stringify({ message: { role: 'assistant', model: 'claude-opus-5-5', usage: {} }, timestamp: '2026-10-18T10:30:00Z' }),
      '{cassée',
      '',
      ligne('ok', 3),
    ].join('\n')
    const m = analyser(texte, fenetre, new Set())
    expect(Object.keys(m)).toEqual(['claude-opus-5-5'])
    expect(m['claude-opus-5-5']?.output).toBe(3)
  })

  test('dossier de projet', () => {
    expect(nomDossierProjet('C:\\Users\\X\\Documents\\GitHub\\agent-cost-kit')).toBe('C--Users-X-Documents-GitHub-agent-cost-kit')
  })
})

type Monde = {
  agents: AgentInfo[]
  fichiers: Record<string, string>
  lus: string[]
  listes: string[]
  logs: string[]
  store: Record<string, unknown>
  tours: number
  env: Record<string, string | undefined>
  /** Message de l'erreur que lève `agent.list`, si posé. */
  panne?: string
}

const DOSSIER = '/home/x/.claude/projects/-w'

/** Le moteur sous le plugin, avec un système de fichiers en mémoire (clés = chemins absolus). */
function monde(on: On, fichiers: Record<string, string>, store: Record<string, unknown> = {}): Monde {
  const m: Monde = { agents: [], fichiers, lus: [], listes: [], logs: [], store, tours: 4, env: { USERPROFILE: '/home/x' } }
  const TROP_GROS = 'TROP_GROS'
  // Le moteur de test rend les chemins absolus à la mode de Windows (C:\...).
  const norme = (p: string) => p.split(String.fromCharCode(92)).join("/").replace(/^[A-Za-z]:/, "")
  on('store.get', (_$, e) => ({ value: store[e.key] }))
  on('store.set', (_$, e) => ((store[e.key] = e.value), { value: undefined }))
  on('store.delete', (_$, e) => (delete store[e.key], { value: undefined }))
  on('ui.log', (_$, e) => (m.logs.push(String((e as { message?: string }).message ?? JSON.stringify(e))), { value: undefined }))
  on('session.id', () => ({ value: 'S1' }))
  on('session.cwd', () => ({ value: '/w' }))
  on('session.root', () => ({ value: '/w' }))
  on('session.turns', () => ({ value: m.tours }))
  on('session.usage', () => ({
    value: { startedAt: DEBUT, context: { window: 200000, tokens: 1, percent: 0 }, rateLimits: [], cost: { usd: 1 } },
  }))
  on('env.get', (_$, e) => ({ value: m.env[e.name] }))
  on('fs.exists', (_$, e) => ({
    value: norme(e.path) in m.fichiers || Object.keys(m.fichiers).some(k => k.startsWith(`${norme(e.path)}/`)),
  }))
  on('fs.list', (_$, e) => {
    const noms = new Map<string, 'file' | 'dir'>()
    const dossier = norme(e.path)
    m.listes.push(dossier)
    for (const k of Object.keys(m.fichiers)) {
      if (!k.startsWith(`${dossier}/`)) continue
      const [nom, ...reste] = k.slice(dossier.length + 1).split('/')
      noms.set(nom!, reste.length > 0 ? 'dir' : 'file')
    }
    return { value: [...noms].map(([name, kind]) => ({ name, kind, size: 0, mtimeMs: 0, isLink: false })) }
  })
  on('fs.read', (_$, e) => {
    m.lus.push(norme(e.path))
    const texte = m.fichiers[norme(e.path)]
    if (texte === undefined || texte === TROP_GROS) throw new Error('over 4 MiB')
    return { value: texte }
  })
  on('agent.list', () => {
    if (m.panne) throw new Error(m.panne)
    return { value: m.agents }
  })
  on('turn.complete', () => ({ text: '' }))
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  return m
}

type Moteur = { session: { start: (a: object) => Promise<unknown> }; turn: { complete: (a: object) => Promise<unknown> } }
/** Un aller-retour avec le moteur (fin de tour sans usage : le mod n'en fait rien). */
const passer = ($: Moteur) => $.turn.complete({ answer: '', durationMs: 0, isAborted: false, turnId: 'x', reason: 'answer' })
const demarrer = ($: Moteur) =>
  $.session.start({ cwd: '/w', surface: 'terminal', isInteractive: true })

/** Laisse la reprise (lancée sans attente) se terminer : attend que le store porte la marque. */
async function attendre($: Moteur, store: Record<string, unknown>, ok = (c?: Cumul) => c?.reprise !== undefined) {
  for (let i = 0; i < 5000 && !ok(store['session:S1'] as Cumul | undefined); i++) await passer($) // un aller-retour avec le moteur laisse avancer la reprise
  return store['session:S1'] as Cumul | undefined
}

const principal = `${DOSSIER}/S1.jsonl`
const sous = `${DOSSIER}/S1/subagents`

describe('reprise de l’historique', () => {
  test('mod chargé en cours de session : modèles, sous-agents avec fiche, tours', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, {
      [principal]: [ligne('m1', 10), ligne('m1', 30), ligne('m2', 5, {}, '2026-10-18T10:40:00Z', 'claude-sonnet-5-5')].join('\n'),
      [`${sous}/agent-A1.jsonl`]: ligne('s1', 20, { isSidechain: true }),
      [`${sous}/agent-A1.meta.json`]: JSON.stringify({ agentType: 'dev-story', description: 'Story 3' }),
      [`${sous}/agent-A2.jsonl`]: ligne('s2', 8),
    }, store)
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    await attendre($, store)
    const c = (await attendre($, store))!
    expect(c.modeles['claude-opus-5-5']).toEqual({ input: 2 + 2 + 2, output: 30 + 20 + 8, cacheRead: 3000, cacheWrite: 300 })
    expect(c.modeles['claude-sonnet-5-5']?.output).toBe(5)
    expect(c.agents.A1).toMatchObject({ type: 'dev-story', description: 'Story 3' })
    expect(c.agents.A1?.modeles['claude-opus-5-5']?.output).toBe(20)
    expect(c.agents.A2).toMatchObject({ type: 'agent', description: '' })
    expect(c.tours).toBe(4 + 2)
    expect(c.reprise).toEqual({ jusqua: MAINTENANT })
  })

  test('cumul déjà en store : aucune lecture de transcription', async ($, on) => {
    const stocke: Cumul = { sessionId: 'S1', startedAt: DEBUT, tours: 1, modeles: {}, agents: {}, enCours: {} }
    const m = monde(on, { [principal]: ligne('m1', 10) }, { 'session:S1': stocke })
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    for (let i = 0; i < 50; i++) await passer($)
    expect(m.lus).toEqual([])
    expect(m.store['session:S1']).toMatchObject({ tours: 1, modeles: {} })
  })

  test('sous-agent en cours sauté', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10), [`${sous}/agent-A1.jsonl`]: ligne('s1', 20), [`${sous}/agent-A2.jsonl`]: ligne('s2', 8) }, store)
    m.agents = [
      { id: 'A1', description: '', type: 'dev-story', status: 'running' },
      { id: 'A2', description: '', type: 'dev-story', status: 'completed' },
    ]
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    const c = (await attendre($, store))!
    expect(Object.keys(c.agents)).toEqual(['A2'])
    expect(c.modeles['claude-opus-5-5']?.output).toBe(18)
    expect(m.lus).not.toContain(`${sous}/agent-A1.jsonl`)
  })

  test('fichier trop gros : partiel, log, le reste compté', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10), [`${sous}/agent-A1.jsonl`]: 'TROP_GROS', [`${sous}/agent-A2.jsonl`]: ligne('s2', 8) }, store)
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    const c = (await attendre($, store))!
    expect(c.reprise).toEqual({ jusqua: MAINTENANT, partielle: true })
    expect(c.modeles['claude-opus-5-5']?.output).toBe(18)
    expect(m.logs.some(l => l.includes('historique partiel') && l.includes('agent-A1.jsonl'))).toBe(true)
  })

  test('un turn.complete après la reprise s’ajoute sans doubler', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, { [principal]: ligne('m1', 10) }, store)
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    await attendre($, store)
    await $.turn.start({ prompt: 'x', turnId: 't1' })
    await $.turn.complete(finTour(100))
    const c = (await attendre($, store, x => x?.tours === 5))!
    expect(c.modeles['claude-opus-5-5']?.output).toBe(110)
    expect(c.tours).toBe(5)
  })

  test('fin du tour du chargement (début non entendu) après la reprise : écartée, déjà relue', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, { [principal]: ligne('m1', 10) }, store)
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    await attendre($, store)
    await $.turn.complete(finTour(10))
    for (let i = 0; i < 20; i++) await passer($)
    const c = store['session:S1'] as Cumul
    expect(c.modeles['claude-opus-5-5']?.output).toBe(10)
    expect(c.tours).toBe(4)
  })

  test('fin du tour du chargement avant session.start : comptée une fois', async ($, on) => {
    const store: Record<string, unknown> = {}
    monde(on, { [principal]: ligne('m1', 10) }, store)
    mock.clock(on, { now: MAINTENANT })
    await $.turn.complete(finTour(10))
    await demarrer($)
    const c = (await attendre($, store))!
    expect(c.modeles['claude-opus-5-5']?.output).toBe(10)
    expect(c.tours).toBe(4)
  })

  test('sous-agent en cours au chargement qui finit pendant la lecture : compté en direct, une fois', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10), [`${sous}/agent-A1.jsonl`]: ligne('s1', 20) }, store)
    m.agents = [{ id: 'A1', description: 'Story', type: 'dev-story', status: 'running' }]
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    m.agents = [{ id: 'A1', description: 'Story', type: 'dev-story', status: 'completed' }]
    await $.turn.complete(finTour(20, 'A1'))
    const c = (await attendre($, store, x => x?.reprise !== undefined && x.tours === 5))!
    expect(c.modeles['claude-opus-5-5']?.output).toBe(30)
    expect(c.agents.A1?.modeles['claude-opus-5-5']?.output).toBe(20)
  })

  test('sous-agent fini au chargement dont la fin de tour arrive tard : compté une fois', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10), [`${sous}/agent-A1.jsonl`]: ligne('s1', 20) }, store)
    m.agents = [{ id: 'A1', description: 'Story', type: 'dev-story', status: 'completed' }]
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    await $.turn.complete(finTour(20, 'A1'))
    await attendre($, store)
    for (let i = 0; i < 20; i++) await passer($)
    const c = store['session:S1'] as Cumul
    expect(c.modeles['claude-opus-5-5']?.output).toBe(30)
    expect(c.agents.A1?.modeles['claude-opus-5-5']?.output).toBe(20)
  })

  test('sous-agent idle (entre deux tours) : relu', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10), [`${sous}/agent-A1.jsonl`]: ligne('s1', 20) }, store)
    m.agents = [{ id: 'A1', description: '', type: 'dev-story', status: 'idle' }]
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    const c = (await attendre($, store))!
    expect(c.agents.A1?.modeles['claude-opus-5-5']?.output).toBe(20)
  })

  test('CLAUDE_CONFIG_DIR vide : repli sur le dossier de l’utilisateur', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10) }, store)
    m.env = { CLAUDE_CONFIG_DIR: '', USERPROFILE: '', HOME: '/home/x' }
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    const c = (await attendre($, store))!
    expect(c.modeles['claude-opus-5-5']?.output).toBe(10)
  })

  test('session à froid (aucun prompt ni sous-agent) : aucun parcours de projects/', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, {}, store)
    m.tours = 0
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    for (let i = 0; i < 50; i++) await passer($)
    expect(m.listes).toEqual([])
    expect(m.lus).toEqual([])
  })

  test('erreur pendant la reprise : marquée partielle, journalisée, la bande continue', async ($, on) => {
    const store: Record<string, unknown> = {}
    const m = monde(on, { [principal]: ligne('m1', 10) }, store)
    m.panne = 'liste indisponible'
    mock.clock(on, { now: MAINTENANT })
    await demarrer($)
    const c = (await attendre($, store))!
    expect(c.reprise?.partielle).toBe(true)
    expect(m.logs.some(l => l.includes('historique non repris'))).toBe(true)
  })
})

/** Fin de tour avec usage (Opus), de la session principale ou d'un sous-agent. */
function finTour(sortie: number, agentId?: string) {
  return {
    answer: '',
    durationMs: 1,
    isAborted: false,
    turnId: `t-${sortie}-${agentId ?? ''}`,
    reason: 'answer',
    ...(agentId ? { agentId } : {}),
    usage: { model: 'claude-opus-5-5', input_tokens: 1, output_tokens: sortie, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
  }
}

describe('rendu d’une reprise partielle', () => {
  const base: Cumul = { sessionId: 'S1', startedAt: DEBUT, tours: 1, modeles: { 'claude-opus-5-5': { input: 1, output: 1, cacheRead: 0, cacheWrite: 0 } }, agents: {} }
  test('« ≥ » remplace « ≈ » devant le coût', () => {
    expect(tete({ ...base, reprise: { jusqua: MAINTENANT, partielle: true } }, '▸', 200)).toMatch(/💰 ≥ /)
    expect(tete({ ...base, reprise: { jusqua: MAINTENANT } }, '▸', 200)).toMatch(/💰 ≈ /)
  })
})
