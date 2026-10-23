import type { EngineInterface, Register, Timer, TurnUsage } from 'claude-code'

import type { Cumul, Niveau } from '../types'
import { additionner, VIDE } from './calcul'
import { analyser, fusionner, idSousAgent, nombre, nomDossierProjet, retrancher } from './historique'
import type { Historique, ParModele } from './historique'
import { colonnes, corps, tete } from './rendu'
import type { Contexte } from './rendu'

/**
 * État éphémère du module (une instance par processus, remis à zéro à chaque rechargement du mod) :
 * `$` n'a plus de notion d'état partagé (`atom`/`read`/`update` n'existent plus depuis 2.1.280), donc
 * tout ce qui doit survivre entre deux événements, mais pas forcément entre deux processus, est une
 * simple variable de module plutôt qu'une lecture/écriture de `$`. Ce qui doit survivre au processus
 * (pour `--resume`) reste dans `$.store`, via `cumul` lui-même (persisté par `persister`/`ecrire`) et
 * `niveau` (persisté par `changerNiveau`).
 */
let cumul: Cumul | null = null
let niveau: Niveau = 0
/** Pose à la première `session.start` du processus : au-delà, `niveau` ne revient plus du store. */
let niveauCharge = false
/** Heure (ms) du dernier rafraîchissement : la poser hors cycle de rendu appelle `$.ui.invalidate`. */
let maintenant = 0

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

/**
 * Une fin de tour dont ce module n'a pas entendu le début (`turn.start`) : son tour a commencé avant
 * le chargement du mod, donc ses requêtes figurent peut-être déjà dans l'historique relu.
 */
type Orphelin = { usage: TurnUsage; agentId?: string }

/**
 * La reprise de l'historique de la session que ce process a trouvée sans cumul (ni state ni store).
 * `lues` : boucles (`''` principale, sinon l'id du sous-agent) dont l'historique a compté au moins une
 * requête ; `orphelins` : fins de tour orphelines comptées en direct avant la fin de la lecture, que la
 * fusion retranche de l'historique si leur boucle a été relue. Après la fusion, une orpheline d'une
 * boucle relue est écartée.
 */
type Reprise = { cle: string; lancee: boolean; finie: boolean; lues: Set<string>; orphelins: Orphelin[] }
let reprise: Reprise | undefined
/** Boucles dont ce module a entendu un `turn.start` : leurs fins de tour se comptent en direct. */
const entendues = new Set<string>()
/** Après /clear ou /resume dans le process, la nouvelle session naît sous le mod : rien à reprendre. */
let sessionNeeDuMod = false

/** Pose `cumul` (variable de module) sur la session courante : reprise depuis `$.store`, ou zéro après `/clear`. */
async function synchroniser($: EngineInterface): Promise<Cumul> {
  const [id, usage] = await Promise.all([$.session.id(), $.session.usage()])
  if (cumul && cumul.sessionId === id && cumul.startedAt === usage.startedAt) return cumul
  const stocke = (await $.store.get(cleSession(id))) as Cumul | undefined
  const relu = stocke && stocke.startedAt === usage.startedAt
  // Un sous-agent du cumul relu n'est gardé « en cours » que si le moteur le confirme encore : ça
  // distingue une reprise après --resume (processus neuf, rien à vérifier, tout est fini) d'un
  // rechargement du mod en cours de session (même processus, l'agent tourne peut-être toujours).
  let enCours: NonNullable<Cumul['enCours']> = {}
  if (relu && stocke!.enCours && Object.keys(stocke!.enCours).length > 0) {
    const liste = await $.agent.list()
    const tournent = new Set(liste.filter(a => EN_TOUR.includes(a.status)).map(a => a.id))
    for (const [agentId, fiche] of Object.entries(stocke!.enCours)) if (tournent.has(agentId)) enCours[agentId] = fiche
  }
  // Un synchroniser concurrent a pu poser (et enrichir) le cumul pendant les await : ne pas l'écraser.
  if (cumul && cumul.sessionId === id && cumul.startedAt === usage.startedAt) return cumul
  const neuf = relu ? { ...stocke, enCours } : vide(id, usage.startedAt)
  const cle = `${id}:${usage.startedAt}`
  if (!relu && !sessionNeeDuMod && reprise?.cle !== cle) reprise = { cle, lancee: false, finie: false, lues: new Set(), orphelins: [] }
  cumul = neuf
  return neuf
}

/** Statuts d'un sous-agent dont le tour courant n'est pas fini : son `turn.complete` portera tout ce tour. */
const EN_TOUR = ['pending', 'running', 'waiting']

/** Dossier des transcriptions de la session : celui du cwd ou de la racine, sinon le premier de `projects/` qui la contient. */
async function dossierTranscriptions($: EngineInterface, id: string): Promise<string | undefined> {
  const config = await $.env.get('CLAUDE_CONFIG_DIR')
  const maison = (await $.env.get('USERPROFILE')) || (await $.env.get('HOME'))
  if (!config && !maison) return undefined
  const racine = `${config || `${maison}/.claude`}/projects`
  for (const dir of new Set([await $.session.cwd(), await $.session.root()])) {
    const direct = `${racine}/${nomDossierProjet(dir)}`
    if (await $.fs.exists(`${direct}/${id}.jsonl`)) return direct
  }
  if (!(await $.fs.exists(racine))) return undefined
  for (const entree of await $.fs.list(racine)) {
    if (entree.kind === 'dir' && (await $.fs.exists(`${racine}/${entree.name}/${id}.jsonl`))) return `${racine}/${entree.name}`
  }
  return undefined
}

/**
 * Relit les transcriptions de la session (principale et sous-agents) jusqu'à `fin`, l'instant du
 * chargement : tokens par modèle et par sous-agent. `enTour` : sous-agents au milieu d'un tour à cet
 * instant, sautés (leur `turn.complete` à venir porte tout ce tour). `lues` reçoit les boucles comptées.
 */
async function lireHistorique(
  $: EngineInterface,
  id: string,
  fenetre: { debut: number; fin: number },
  tours: number,
  enTour: Set<string>,
  lues: Set<string>,
): Promise<Historique | undefined> {
  const dossier = await dossierTranscriptions($, id)
  if (!dossier) return undefined
  const h: Historique = { tours, modeles: {}, agents: {}, partielle: false, jusqua: fenetre.fin }
  const vus = new Set<string>()
  const lire = async (chemin: string): Promise<string | undefined> => {
    try {
      const texte = await $.fs.read(chemin)
      return typeof texte === 'string' ? texte : undefined
    } catch (erreur) {
      h.partielle = true
      const motif = erreur instanceof Error ? erreur.message : String(erreur)
      $.ui.log(`couts-session : historique partiel, ${chemin} illisible (${motif})`)
      return undefined
    }
  }
  const principal = await lire(`${dossier}/${id}.jsonl`)
  if (principal !== undefined) h.modeles = analyser(principal, fenetre, vus, true)
  if (Object.keys(h.modeles).length > 0) lues.add('')

  const sous = `${dossier}/${id}/subagents`
  const fichiers = (await $.fs.exists(sous)) ? await $.fs.list(sous) : []
  for (const f of fichiers) {
    const agentId = f.kind === 'file' ? idSousAgent(f.name) : undefined
    if (!agentId || enTour.has(agentId)) continue
    const texte = await lire(`${sous}/${f.name}`)
    if (texte === undefined) continue
    const modeles: ParModele = analyser(texte, fenetre, vus)
    if (Object.keys(modeles).length === 0) continue
    let meta: { agentType?: unknown; description?: unknown } = {}
    try {
      meta = JSON.parse((await $.fs.read(`${sous}/agent-${agentId}.meta.json`)) as string)
    } catch {
      // pas de fiche : repli sur « agent »
    }
    h.agents[agentId] = {
      type: typeof meta.agentType === 'string' ? meta.agentType : 'agent',
      description: typeof meta.description === 'string' ? meta.description : '',
      modeles,
    }
    lues.add(agentId)
    for (const [m, c] of Object.entries(modeles)) h.modeles[m] = additionner(h.modeles[m] ?? VIDE, c)
    h.tours += 1
  }
  return h
}

/**
 * Reconstitue l'historique d'une session que le mod rejoint en cours de route, une fois par session
 * et par process. Tout ce qui borne la lecture (instant, prompts, sous-agents en cours de tour) est
 * relevé d'abord, au chargement, avant toute lecture de fichier : un tour commencé ensuite est compté
 * en direct seulement. Les fins de tour orphelines déjà comptées en direct sont retranchées de
 * l'historique de leur boucle si elle a été relue. Une erreur marque la reprise partielle.
 */
async function reprendre($: EngineInterface, depart: Cumul, r: Reprise): Promise<void> {
  let h: Historique | undefined
  let echec = false
  try {
    const [fin, tours, liste] = await Promise.all([$.clock.now(), $.session.turns(), $.agent.list()])
    const enTour = new Set(liste.filter(a => EN_TOUR.includes(a.status)).map(a => a.id))
    // Session sans prompt ni sous-agent (démarrage à froid) : rien à relire, pas de parcours de `projects/`.
    if (tours > 0 || liste.length > 0) {
      h = await lireHistorique($, depart.sessionId, { debut: depart.startedAt, fin }, tours, enTour, r.lues)
    }
  } catch (erreur) {
    echec = true
    r.lues.clear()
    $.ui.log(`couts-session : historique non repris (${erreur instanceof Error ? erreur.message : String(erreur)})`)
  }
  r.finie = true
  const deja = r.orphelins.splice(0)
  if (h) for (const o of deja) if (r.lues.has(o.agentId ?? '')) retrancher(h, o.usage.model, compteurs(o.usage), o.agentId)
  const meme = (c: Cumul | null): c is Cumul => !!c && c.sessionId === depart.sessionId && c.startedAt === depart.startedAt
  if (meme(cumul)) cumul = h ? fusionner(cumul, h) : echec ? { ...cumul, reprise: { jusqua: 0, partielle: true } } : cumul
  await persister($)
}

/**
 * Écrit dans `$.store` le cumul tel que la variable de module `cumul` le tient au moment d'écrire.
 * `$.store` n'a pas d'écriture conditionnelle : deux fins de tour concurrentes (session et sous-agent
 * en arrière-plan) passent donc l'une après l'autre, et la dernière écriture porte le cumul le plus récent.
 */
let file: Promise<void> = Promise.resolve()
function persister($: EngineInterface): Promise<void> {
  const suite = file.then(() => ecrire($))
  file = suite.catch(() => undefined)
  return suite
}

async function ecrire($: EngineInterface): Promise<void> {
  // Instantané avant tout await : un /clear pendant l'écriture remet `cumul` à null.
  const c = cumul
  if (!c) return
  await $.store.set(cleSession(c.sessionId), c)
  const index = ((await $.store.get('sessions')) as string[] | undefined) ?? []
  const suite = [...index.filter(id => id !== c.sessionId), c.sessionId]
  for (const ancien of suite.slice(0, Math.max(0, suite.length - SESSIONS_GARDEES))) {
    await $.store.delete(cleSession(ancien))
  }
  await $.store.set('sessions', suite.slice(-SESSIONS_GARDEES))
}

function compteurs(u: TurnUsage) {
  return {
    input: nombre(u.input_tokens),
    output: nombre(u.output_tokens),
    cacheRead: nombre(u.cache_read_input_tokens),
    cacheWrite: nombre(u.cache_creation_input_tokens),
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
 * minuteurs et remet cette variable à zéro ; `session.start`, qui suit chaque chargement, le relance
 * si `synchroniser` a retrouvé des en-cours encore actifs dans `$.store` (confirmés par `$.agent.list`).
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
 * échec), pose `maintenant` et appelle `$.ui.invalidate` pour redessiner (minuteur hors cycle de
 * rendu), arrête le minuteur s'il ne reste rien.
 */
async function battre($: EngineInterface): Promise<void> {
  await sansEchec($, async () => {
    const id = await $.session.id()
    const ids = cumul && cumul.sessionId === id ? Object.keys(cumul.enCours ?? {}) : []
    if (ids.length === 0) return arreter()
    const [liste, instant] = await Promise.all([$.agent.list(), $.clock.now()])
    const statuts = new Map(liste.map(a => [a.id, a.status]))
    const finis = ids.filter(i => {
      const statut = statuts.get(i)
      if (statut === undefined) return instant - (cumul!.enCours![i]?.debut ?? 0) >= ABSENT_MS
      return statut === 'completed' || statut === 'failed' || statut === 'killed'
    })
    if (finis.length > 0) retirer(finis)
    maintenant = instant
    await $.ui.invalidate('ui.render')
    if (Object.keys(cumul?.enCours ?? {}).length === 0) arreter()
  })
}

function retirer(ids: string[]): void {
  if (!cumul?.enCours || !ids.some(i => i in cumul!.enCours!)) return
  const reste = { ...cumul.enCours }
  for (const i of ids) delete reste[i]
  cumul = { ...cumul, enCours: reste }
  if (Object.keys(cumul.enCours).length === 0) arreter()
}

/** Marque un sous-agent en cours (sans toucher à un début déjà noté) et lance le minuteur. */
async function marquer($: EngineInterface, id: string, fiche: { type: string; description: string; model?: string }) {
  const debut = await $.clock.now()
  if (cumul && !cumul.enCours?.[id]) cumul = { ...cumul, enCours: { ...cumul.enCours, [id]: { ...fiche, debut } } }
  maintenant = debut
  await $.ui.invalidate('ui.render')
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
  niveau = (pas === 'suivant' ? (niveau + 1) % 3 : Math.max(0, niveau - 1)) as Niveau
  await $.store.set('niveau', niveau)
  await $.ui.invalidate('ui.render')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await sansEchec($, async () => {
      // Une seule fois par processus : au-delà, `niveau` ne revient plus du store (un changement de
      // niveau en session l'aurait déjà mis à jour en mémoire).
      if (!niveauCharge) {
        niveauCharge = true
        const stocke = await $.store.get('niveau')
        if (stocke === 0 || stocke === 1 || stocke === 2) niveau = stocke
      }
      const cumulCourant = await synchroniser($)
      // Rechargement à chaud : des en-cours encore actifs survivent (via $.store), le minuteur non.
      if (Object.keys(cumulCourant.enCours ?? {}).length > 0) demarrer($)
      // Mod chargé en cours de session (ni store à jour ni en-cours) : l'historique se relit sans bloquer la bande.
      const r = reprise
      if (r && !r.lancee && r.cle === `${cumulCourant.sessionId}:${cumulCourant.startedAt}` && !cumulCourant.reprise) {
        r.lancee = true
        void sansEchec($, () => reprendre($, cumulCourant, r))
      }
    })
    return result
  })

  on('agent.spawn', async ($, e, next) => {
    const result = await next(e)
    const { agentId } = result
    if (agentId) {
      entendues.add(agentId)
      await sansEchec($, async () => {
        await synchroniser($)
        const fiche = { type: e.subagentType, description: e.description, modeles: {} }
        if (cumul && !cumul.agents[agentId]) cumul = { ...cumul, agents: { ...cumul.agents, [agentId]: fiche } }
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
    entendues.add(agentId ?? '')
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
    if (e.agentId && !usage) {
      await sansEchec($, async () => {
        retirer([e.agentId!])
        await $.ui.invalidate('ui.render')
      })
    }
    if (usage) {
      await sansEchec($, async () => {
        const courant = await synchroniser($)
        const { agentId } = e
        let agent: { type: string; description: string } | undefined
        if (agentId && !courant.agents[agentId]) {
          const connu = (await $.agent.list()).find(a => a.id === agentId)
          agent = connu ? { type: connu.type, description: connu.description } : { type: 'interne', description: '' }
        }
        // Tour commencé avant le chargement, dans une session en reprise : peut-être déjà relu.
        const boucle = agentId ?? ''
        const orphelin = !entendues.has(boucle)
        entendues.add(boucle)
        const r = reprise
        if (orphelin && r && r.cle === `${courant.sessionId}:${courant.startedAt}`) {
          if (!r.finie) r.orphelins.push({ usage, agentId })
          else if (r.lues.has(boucle)) {
            if (agentId) {
              retirer([agentId])
              await $.ui.invalidate('ui.render')
            }
            return
          }
        }
        cumul = ajouter(cumul && cumul.sessionId === courant.sessionId ? cumul : courant, usage, agentId, agent)
        await persister($)
        if (agentId) retirer([agentId]) // arrête le minuteur s'il ne reste rien
        await $.ui.invalidate('ui.render')
      })
    }
    return result
  })

  // /clear (et /resume en cours de process) change l'id de session sans session.start : on vide
  // le cumul tout de suite, sans attendre la fin du prochain tour pour quitter l'ancienne session.
  on('session.end', async ($, e, next) => {
    const result = await next(e)
    if (e.reason === 'clear' || e.reason === 'resume') {
      sessionNeeDuMod = true
      if (cumul && cumul.sessionId === e.sessionId) {
        cumul = null
        await sansEchec($, () => $.ui.invalidate('ui.render'))
      }
    }
    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    // Ce que dessinent les plugins en dessous (et le moteur) reste affiché sous la bande.
    const dessous = await next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const id = await $.session.id()
    // Garde-fou au rendu : un cumul d'une autre session n'est pas montré.
    const cumulAffiche = cumul && cumul.sessionId === id ? cumul : null
    const largeur = Math.max(20, e.props.bodyColumns)
    // Hors plein écran, le clic n'est pas rapporté : on rappelle la touche (prompt vide, ou ctrl+x tab).
    const aide = e.viewport?.isFullscreen === false ? (niveau === 0 ? ' (touche 1)' : ' (1 / 2)') : ''
    const place = 3 + colonnes(aide) + (niveau > 0 ? 5 : 0)
    let coutMoteur: number | undefined
    let contexte: Contexte | undefined
    // Lecture seule, sans `breakdown` (gratuite) : `context.tokens` est l'entrée de la dernière réponse
    // de la session principale (le `total_input_tokens` de la status line), absente après /compact
    // jusqu'à la réponse suivante. En cas d'erreur, la bande s'affiche sans 🧠 ni total moteur.
    let usage: Awaited<ReturnType<typeof $.session.usage>> | undefined
    try {
      usage = await $.session.usage(niveau === 2 ? { breakdown: 'summary', columns: largeur } : undefined)
    } catch {
      usage = undefined
    }
    const ctxTokens = usage?.context.tokens
    if (usage && niveau > 0) {
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
    const ligneTete = tete(cumulAffiche, niveau < 2 ? '▸' : '▾', largeur - place, ctxTokens)
    const lignes = corps({ cumul: cumulAffiche, niveau, largeur, lignesMax: e.props.maxRows, coutMoteur, contexte, maintenant })
    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          {/* Un <Button> prend soit `label`, soit un seul enfant texte, jamais les deux : `aide` est fondue dedans. */}
          <Button key="niveau" plain hotkey="1" dimColor onPress={() => changerNiveau($, 'suivant')}>
            {`${ligneTete}${aide}`}
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
