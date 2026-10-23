import { describe, expect, test } from 'claude-code/testing'

import { carbone, cout, dollars, famille, impact, METHODE, nomCourt, tokens, ttft } from '../hooks/calcul'

const sortieSeule = (output: number) => ({ input: 0, output, cacheRead: 0, cacheWrite: 0 })

// Attendus calculés avec scripts/mesurer_couts.py (commit f84b959) : impact(modele, sortie), méthode ecologits.
const ATTENDUS: [string, number, [number, number], [number, number]][] = [
  ['claude-opus-5-5', 1000, [4.778044014590133, 9.792504712723275], [2.289455745431124, 4.676421444182033]],
  ['claude-sonnet-5-5', 2500, [4.165020787724337, 7.076478495470172], [1.9858911460610258, 3.365680617542787]],
  ['claude-haiku-5-5', 10000, [0.8318457433960033, 2.316363904172596], [0.3949932610345876, 1.096090987578126]],
  ['claude-sonnet-4-6', 500, [0.9652627597775498, 1.8210505301638424], [0.46127056109473286, 0.8679811811123594]],
  ['modele-inconnu', 100, [0.46722371328039874, 0.9792504712723276], [0.22381818799251016, 0.4676421444182033]],
  ['acme-fable-x', 300, [4.221154495616751, 10.301919166577328], [2.029978925735758, 4.931435313096153]],
]

const proche = (reel: number, attendu: number) => expect(Math.abs(reel - attendu) / attendu).toBeLessThan(1e-12)

describe('impact EcoLogits', () => {
  test('reproduit mesurer_couts.py', () => {
    for (const [modele, sortie, energie, gwp] of ATTENDUS) {
      const i = impact(modele, { input: 5000, output: sortie, cacheRead: 90000, cacheWrite: 700 }, 'ecologits')
      proche(i.energieWh.min, energie[0])
      proche(i.energieWh.max, energie[1])
      proche(i.gco2e.min, gwp[0])
      proche(i.gco2e.max, gwp[1])
    }
  })

  test('zéro token de sortie, zéro impact', () => {
    expect(impact('claude-opus-5-5', sortieSeule(0), 'ecologits').gco2e).toEqual({ min: 0, max: 0 })
  })
})

// Attendus calculés avec scripts/mesurer_couts.py : impact(modele, sortie, entree=input + cacheWrite, lu=cacheRead,
// appels=0, methode="impactia") (le mod ne connaît pas le nombre d'appels).
const ATTENDUS_IMPACTIA: [string, [number, number, number, number], [number, number], [number, number]][] = [
  ['claude-opus-5-5', [10, 2000, 100000, 3000], [10.115352257908123, 21.749624596715595], [4.938402351424498, 10.680138515922252]],
  ['claude-sonnet-5-5', [2, 250, 25000, 1100], [0.4434458858562845, 0.8566403199437176], [0.21588654044453562, 0.4268288318157826]],
  ['claude-haiku-5-5', [0, 100, 500000, 0], [0.008758762277237786, 0.2320065702514341], [0.0042373343196219476, 0.13553004782685066]],
  ['modele-inconnu', [100, 300, 0, 10000], [1.5775466624967411, 3.208003955409508], [0.7810610271087816, 1.569562213515814]],
]

describe('impact ImpactIA', () => {
  test('méthode par défaut', () => {
    expect(METHODE).toBe('impactia')
    expect(ttft('claude-opus-5-5')).toBe(2.68)
    expect(ttft('claude-opus-4-1')).toBe(2.68)
  })

  test('reproduit mesurer_couts.py', () => {
    for (const [modele, [input, output, cacheRead, cacheWrite], energie, gwp] of ATTENDUS_IMPACTIA) {
      const i = impact(modele, { input, output, cacheRead, cacheWrite })
      proche(i.energieWh.min, energie[0])
      proche(i.energieWh.max, energie[1])
      proche(i.gco2e.min, gwp[0])
      proche(i.gco2e.max, gwp[1])
    }
  })

  test('lecture du cache : 0 en borne basse, prefill complet en borne haute', () => {
    const sans = impact('claude-sonnet-5-5', { input: 10, output: 500, cacheRead: 0, cacheWrite: 2000 })
    const lu = impact('claude-sonnet-5-5', { input: 10, output: 500, cacheRead: 300000, cacheWrite: 2000 })
    expect(lu.gco2e.min).toBe(sans.gco2e.min)
    expect(lu.gco2e.max).toBeGreaterThan(sans.gco2e.max)
    expect(sans.gco2e.max).toBeGreaterThan(impact('claude-sonnet-5-5', sortieSeule(500), 'ecologits').gco2e.max)
  })
})

describe('coût API', () => {
  test('prix par famille, écriture du cache au tarif 5 min', () => {
    const million = { input: 1e6, output: 0, cacheRead: 0, cacheWrite: 0 }
    expect(cout('claude-opus-5-5', million)).toBe(4)
    expect(cout('claude-sonnet-5-5', { ...million, input: 0, cacheWrite: 1e6 })).toBe(2.5)
    expect(cout('claude-haiku-5-5', { input: 0, output: 1e6, cacheRead: 1e6, cacheWrite: 0 })).toBe(0.51)
    expect(cout('claude-fable-5-1', { ...million, input: 0, cacheRead: 1e6 })).toBe(0.25)
    expect(cout('gpt-x', million)).toBeUndefined()
  })

  test('prix par génération : un ancien modèle ne prend pas le tarif du 5.5', () => {
    const entree = { input: 1e6, output: 0, cacheRead: 0, cacheWrite: 0 }
    const sortie = { input: 0, output: 1e6, cacheRead: 0, cacheWrite: 0 }
    const lecture = { input: 0, output: 0, cacheRead: 1e6, cacheWrite: 0 }
    expect(cout('claude-opus-4-6', entree)).toBe(5)
    expect(cout('claude-opus-4-6-20260101', sortie)).toBe(25)
    expect(cout('claude-opus-4-6', lecture)).toBe(0.5)
    expect(cout('claude-opus-4-1', sortie)).toBe(75)
    expect(cout('claude-sonnet-4-5', sortie)).toBe(15)
    expect(cout('claude-sonnet-5', lecture)).toBe(0.2)
    expect(cout('claude-sonnet-5-5', lecture)).toBe(0.1)
    expect(cout('claude-haiku-4-5', sortie)).toBe(5)
    expect(cout('claude-fable-5', lecture)).toBe(1)
    expect(cout('claude-opus-5-5', sortie)).toBe(20)
    expect(cout('claude-opus-9', sortie)).toBe(20) // inconnu : repli par famille, tarif le plus récent
    expect(cout('claude-opus-4-6[1m]', sortie)).toBe(25)
    expect(cout('claude-opus-4-50', sortie)).toBe(75) // frontière de numéro : pas le tarif de claude-opus-4-5
    expect(cout('claude-mythos-5-1', lecture)).toBe(0.25)
    expect(cout('claude-mythos-5', lecture)).toBe(1)
    expect(famille('claude-sonnet-5-5')).toBe('sonnet')
  })
})

describe('formats', () => {
  test('nombres à la française, courts', () => {
    expect(dollars(1.234)).toBe('1,23 $')
    expect(dollars(42.25)).toBe('42,3 $')
    expect(tokens(850)).toBe('850')
    expect(tokens(8500)).toBe('8,5 k')
    expect(tokens(2_100_000)).toBe('2,1 M')
    expect(carbone({ min: 400, max: 900 })).toBe('400–900 gCO₂e')
    expect(carbone({ min: 400, max: 1900 })).toBe('0,4–1,9 kgCO₂e')
    expect(carbone({ min: 0.12, max: 0.5 })).toBe('0,12–0,50 gCO₂e')
    expect(nomCourt('claude-haiku-4-5-20251001')).toBe('haiku-4-5')
    expect(nomCourt('claude-opus-5-5[1m]')).toBe('opus-5-5')
  })
})
