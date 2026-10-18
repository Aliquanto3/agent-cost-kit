import type { Cumul, Niveau } from '../types'
import { bilan, carbone, cout, dollars, impact, nomCourt, tokens, VIDE } from './calcul'
import { TARIFS } from './tarifs'

/** Ce que la bande sait du contexte au niveau 2 (estimation locale, `breakdown: 'summary'`). */
export type Contexte = {
  total: number
  fenetre: number
  pourcent: number
  categories: { nom: string; tokens: number }[]
}

export type Entree = {
  cumul: Cumul | null
  niveau: Niveau
  largeur: number
  lignesMax: number
  coutMoteur?: number
  contexte?: Contexte
}

/** Coupe une ligne à la largeur, avec une ellipse. */
export function couper(texte: string, largeur: number): string {
  const n = Math.max(1, largeur)
  return texte.length <= n ? texte : `${texte.slice(0, n - 1)}…`
}

/** Ligne repliée : coût, tokens, carbone. Sans la place des boutons. */
export function resume(cumul: Cumul | null): string {
  const b = bilan(cumul?.modeles ?? {})
  const prix = `≈ ${dollars(b.usd)}${b.horsTable ? '+?' : ''}`
  return `${prix} · ${tokens(b.tokens)} tok · ${carbone(b.gco2e)} estimé`
}

function tableau(entetes: string[], lignes: string[][]): string[] {
  const largeurs = entetes.map((e, i) => Math.max(e.length, ...lignes.map(l => (l[i] ?? '').length)))
  const format = (l: string[]) =>
    l.map((cellule, i) => (i === 0 ? cellule.padEnd(largeurs[i] ?? 0) : cellule.padStart(largeurs[i] ?? 0))).join('  ')
  return [format(entetes), ...lignes.map(format)]
}

/** Tableau par modèle : complet s'il tient, sinon modèle, coût et carbone seuls. */
export function parModele(cumul: Cumul | null, largeur: number): string[] {
  const modeles = Object.entries(cumul?.modeles ?? {}).sort(
    ([a, ca], [b, cb]) => (cout(b, cb) ?? 0) - (cout(a, ca) ?? 0),
  )
  if (modeles.length === 0) return ['Aucun tour compté pour l’instant.']
  const prix = (m: string, c: typeof VIDE) => {
    const usd = cout(m, c)
    return usd === undefined ? '?' : dollars(usd)
  }
  const g = (m: string, c: typeof VIDE) => carbone(impact(m, c.output).gco2e).replace('CO₂e', '')
  const complet = tableau(
    ['modèle', 'entrée', 'sortie', 'lu', 'écrit', 'coût', 'gCO₂e'],
    modeles.map(([m, c]) => [
      nomCourt(m),
      tokens(c.input),
      tokens(c.output),
      tokens(c.cacheRead),
      tokens(c.cacheWrite),
      prix(m, c),
      g(m, c),
    ]),
  )
  if (Math.max(...complet.map(l => l.length)) <= largeur) return complet
  return tableau(
    ['modèle', 'coût', 'gCO₂e'],
    modeles.map(([m, c]) => [nomCourt(m), prix(m, c), g(m, c)]),
  ).map(l => couper(l, largeur))
}

/** Une ligne par sous-agent, les plus chers d'abord, au plus `place` lignes. */
export function parAgent(cumul: Cumul | null, largeur: number, place: number): string[] {
  const agents = Object.values(cumul?.agents ?? {})
    .map(a => {
      const b = bilan(a.modeles)
      const modeles = Object.keys(a.modeles).map(nomCourt).join('+') || '—'
      return { a, b, modeles }
    })
    .filter(x => x.b.tokens > 0)
    .sort((x, y) => y.b.usd - x.b.usd)
  if (agents.length === 0 || place <= 0) return []
  const montres = agents.length > place ? agents.slice(0, Math.max(0, place - 1)) : agents
  const lignes = montres.map(({ a, b, modeles }) => {
    // La description vient en dernier : c'est elle que la largeur coupe d'abord.
    const description = a.description ? ` « ${couper(a.description, 28)} »` : ''
    return couper(`· ${a.type} · ${dollars(b.usd)} · ${carbone(b.gco2e)} · ${modeles}${description}`, largeur)
  })
  if (montres.length < agents.length) {
    const reste = agents.slice(montres.length).reduce((s, x) => s + x.b.usd, 0)
    lignes.push(couper(`· ${agents.length - montres.length} autres · ${dollars(reste)}`, largeur))
  }
  return lignes
}

export function pied(coutMoteur: number | undefined, largeur: number): string[] {
  const etroit = largeur < 72
  const mix = TARIFS.ecologits.mix_par_defaut
  const moteur =
    coutMoteur === undefined ? '' : etroit ? ` · /cost ${dollars(coutMoteur)}` : ` · /cost du moteur : ${dollars(coutMoteur)}`
  const lignes = etroit
    ? [`EcoLogits, ${mix} : sortie seule, cache non compté`, `Prix API, cache 5 min${moteur}`]
    : [
        `Impact : EcoLogits (ecologits.ai), mix ${mix}, sortie seule, cache non compté`,
        `Coût : prix API, écriture du cache au tarif 5 min${moteur}`,
      ]
  return lignes.map(l => couper(l, largeur))
}

export function contexte(c: Contexte | undefined, largeur: number): string[] {
  if (!c) return ['Contexte : pas encore mesuré.']
  const tete = `Contexte : ${tokens(c.total)} / ${tokens(c.fenetre)} (${c.pourcent} %), estimation locale`
  const rangs = c.categories
    .filter(k => k.tokens > 0)
    .map(k => `  ${k.nom} : ${tokens(k.tokens)} (${Math.round((100 * k.tokens) / Math.max(1, c.fenetre))} %)`)
  return [tete, ...rangs].map(l => couper(l, largeur))
}

/** Les lignes de texte sous la ligne de tête, selon le niveau. */
export function corps(entree: Entree): string[] {
  const { cumul, niveau, largeur, lignesMax } = entree
  if (niveau === 0) return []
  const modeles = parModele(cumul, largeur)
  const basDePage = pied(entree.coutMoteur, largeur)
  const ctx = niveau === 2 ? contexte(entree.contexte, largeur) : []
  const place = lignesMax - 1 - modeles.length - basDePage.length - ctx.length
  return [...modeles, ...parAgent(cumul, largeur, place), ...basDePage, ...ctx]
}
