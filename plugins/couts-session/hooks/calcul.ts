import type { Compteurs } from '../types'
import { TARIFS } from './tarifs'

const PRIX = TARIFS.prix
const ECO = TARIFS.ecologits

export const VIDE: Compteurs = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }

export function additionner(a: Compteurs, b: Compteurs): Compteurs {
  return {
    input: a.input + b.input,
    output: a.output + b.output,
    cacheRead: a.cacheRead + b.cacheRead,
    cacheWrite: a.cacheWrite + b.cacheWrite,
  }
}

export function totalTokens(c: Compteurs): number {
  return c.input + c.output + c.cacheRead + c.cacheWrite
}

/** La première famille de la table dont le nom figure dans l'identifiant, comme mesurer_couts.py. */
export function famille(modele: string): string | undefined {
  return Object.keys(PRIX.familles).find(nom => modele.includes(nom))
}

type Tarif = { entree: number; sortie: number; lecture: number }

/** Tarif du modèle : plus long préfixe de l'identifiant, sinon repli par famille (comme mesurer_couts.py). */
export function tarif(modele: string): Tarif | undefined {
  const table: Record<string, Tarif> = PRIX.modeles
  const candidats = Object.keys(table).filter(cle => modele.startsWith(cle))
  if (candidats.length > 0) return table[candidats.reduce((a, b) => (b.length > a.length ? b : a))]
  const nom = famille(modele)
  const familles: Record<string, Tarif> = PRIX.familles
  return nom ? familles[nom] : undefined
}

/**
 * Coût API estimé en dollars, ou undefined pour un modèle hors table. L'usage ne ventile pas
 * l'écriture du cache entre 5 min et 1 h : tarif 5 min. Deux limites : le palier Haiku 5.5 au-delà
 * de 100 k tokens de prompt se juge requête par requête, l'usage d'un tour les additionne, il n'est
 * donc pas appliqué ; et l'usage du tour (ModelUsage) ne porte pas inference_geo, le multiplicateur
 * x 1,1 de `inference_geo: "us"` n'est donc pas appliqué non plus.
 */
export function cout(modele: string, c: Compteurs): number | undefined {
  const f = tarif(modele)
  if (!f) return undefined
  const ecriture = PRIX.ecriture_cache['5m']
  return (
    (c.input * f.entree + c.output * f.sortie + c.cacheRead * f.lecture + c.cacheWrite * ecriture * f.entree) / 1e6
  )
}

type Parametres = readonly [number, number, number, number]

/** (total_min, total_max, actif_min, actif_max) : plus long préfixe, sinon famille, sinon opus. */
export function parametres(modele: string): Parametres {
  const table: Record<string, Parametres> = ECO.parametres
  const candidats = Object.keys(table).filter(cle => modele.startsWith(cle))
  if (candidats.length > 0) {
    const cle = candidats.reduce((a, b) => (b.length > a.length ? b : a))
    return table[cle] as Parametres
  }
  const familles: Record<string, Parametres> = ECO.parametres_famille
  return (familles[famille(modele) ?? ECO.famille_par_defaut] ?? familles[ECO.famille_par_defaut]) as Parametres
}

export type Fourchette = { min: number; max: number }
export type Impact = { energieWh: Fourchette; gco2e: Fourchette }

/** Impact de `sortie` tokens générés, méthode EcoLogits reprise de mesurer_couts.py (mix USA). */
export function impact(modele: string, sortie: number): Impact {
  const mix = ECO.mix[ECO.mix_par_defaut]
  const [tMin, tMax, aMin, aMax] = parametres(modele)
  const [alpha, beta, gamma] = ECO.gpu_energie_wh_par_token
  const [la, lb, lg] = ECO.gpu_latence_s_par_token
  const lot = ECO.lot
  const borne = (total: number, actif: number, pue: number) => {
    const fEnergie = alpha * Math.exp(beta * lot) * actif + gamma
    const duree = sortie * (la * actif + lb * lot + lg)
    const gpus = 2 ** Math.ceil(Math.log2(Math.max(1, Math.ceil((1.2 * total * 16) / 8 / ECO.gpu_memoire_go))))
    const part = gpus / ECO.serveur_gpus
    const eTiWh = (duree / 3600) * ECO.serveur_puissance_w * part / lot + gpus * sortie * fEnergie
    const eWh = pue * eTiWh
    const fab =
      (duree / (lot * ECO.duree_vie_s)) * (part * ECO.fabrication_serveur.kgco2e + gpus * ECO.fabrication_gpu.kgco2e)
    return { eWh, g: ((eWh / 1000) * mix.kgco2e + fab) * 1000 }
  }
  const bas = borne(tMin, aMin, ECO.pue[0])
  const haut = borne(tMax, aMax, ECO.pue[1])
  return { energieWh: { min: bas.eWh, max: haut.eWh }, gco2e: { min: bas.g, max: haut.g } }
}

/** Somme sur un ensemble de modèles. */
export function bilan(modeles: Record<string, Compteurs>) {
  let usd = 0
  let horsTable = false
  let tokens = 0
  const g = { min: 0, max: 0 }
  for (const [modele, c] of Object.entries(modeles)) {
    const prix = cout(modele, c)
    if (prix === undefined) horsTable = horsTable || totalTokens(c) > 0
    else usd += prix
    tokens += totalTokens(c)
    const i = impact(modele, c.output)
    g.min += i.gco2e.min
    g.max += i.gco2e.max
  }
  return { usd, horsTable, tokens, gco2e: g }
}

// Formats français, courts.

function decimal(x: number, chiffres: number): string {
  return x.toFixed(chiffres).replace('.', ',')
}

export function dollars(x: number): string {
  return `${decimal(x, x < 10 ? 2 : x < 100 ? 1 : 0)} $`
}

export function tokens(n: number): string {
  if (n < 1000) return `${Math.round(n)}`
  if (n < 1e6) return `${decimal(n / 1e3, n < 1e4 ? 1 : 0)} k`
  return `${decimal(n / 1e6, n < 1e7 ? 1 : 0)} M`
}

/** Une fourchette de gCO2e, en g ou en kg, mêmes unité et décimales aux deux bornes. */
export function carbone(f: Fourchette): string {
  const enKg = f.max >= 1000
  const [bas, haut] = enKg ? [f.min / 1000, f.max / 1000] : [f.min, f.max]
  const chiffres = haut < 1 ? 2 : haut < 10 ? 1 : 0
  return `${decimal(bas, chiffres)}–${decimal(haut, chiffres)} ${enKg ? 'kg' : 'g'}CO₂e`
}

/** claude-sonnet-5-5-20261001[1m] -> sonnet-5-5 */
export function nomCourt(modele: string): string {
  return modele.replace(/^claude-/, '').replace(/\[.*\]$/, '').replace(/-\d{8}$/, '')
}
