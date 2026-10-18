// Généré par donnees/generer_tarifs.py depuis donnees/tarifs.json : ne pas modifier à la main.
export const TARIFS = {
  "version": 1,
  "prix": {
    "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    "verifie_le": "2026-10-18",
    "unite": "USD par million de tokens",
    "note": "Prix par famille, la première dont le nom figure dans l'identifiant du modèle l'emporte (ordre de 'familles'). Lecture du cache = 'lecture'. Écriture du cache = entrée x 'ecriture_cache' (5 min ou 1 h).",
    "familles": [
      {
        "nom": "fable",
        "entree": 10.0,
        "sortie": 50.0,
        "lecture": 0.25
      },
      {
        "nom": "opus",
        "entree": 4.0,
        "sortie": 20.0,
        "lecture": 0.2
      },
      {
        "nom": "sonnet",
        "entree": 2.0,
        "sortie": 10.0,
        "lecture": 0.1
      },
      {
        "nom": "haiku",
        "entree": 0.1,
        "sortie": 0.5,
        "lecture": 0.01
      }
    ],
    "ecriture_cache": {
      "5m": 1.25,
      "1h": 2.0
    },
    "haiku_long_contexte": {
      "seuil_tokens": 100000,
      "facteur": 5.0,
      "note": "Prompt de plus de 100 000 tokens (entrée + lecture + écriture du cache) d'une requête Haiku : tous ses prix x 5."
    }
  },
  "ecologits": {
    "source": "https://ecologits.ai/latest/methodology/llm_inference/",
    "donnees": "EcoLogits, commit d0b76e3, données du 2026-10-14",
    "note": "Seuls les tokens de sortie comptent. Paramètres en milliards : [total_min, total_max, actif_min, actif_max] ; le plus long préfixe de l'identifiant l'emporte, sinon repli par famille, sinon opus.",
    "parametres": {
      "claude-opus-5-5": [
        670,
        670,
        70,
        200
      ],
      "claude-opus-5": [
        670,
        670,
        67,
        200
      ],
      "claude-opus-4": [
        670,
        670,
        67,
        200
      ],
      "claude-sonnet-5": [
        293,
        293,
        29,
        88
      ],
      "claude-sonnet-4": [
        440,
        440,
        44,
        132
      ],
      "claude-haiku-5": [
        10,
        35,
        10,
        35
      ],
      "claude-haiku-4": [
        10,
        35,
        10,
        35
      ],
      "claude-fable-5": [
        1340,
        1340,
        134,
        400
      ]
    },
    "parametres_famille": {
      "opus": [
        670,
        670,
        67,
        200
      ],
      "sonnet": [
        293,
        293,
        29,
        88
      ],
      "haiku": [
        10,
        35,
        10,
        35
      ],
      "fable": [
        1340,
        1340,
        134,
        400
      ]
    },
    "famille_par_defaut": "opus",
    "lot": 64,
    "gpu_energie_wh_par_token": [
      1.1665273170451914e-06,
      -0.011205921025579175,
      4.052928146734005e-05
    ],
    "gpu_latence_s_par_token": [
      0.0006785088094353663,
      0.0003119310311688259,
      0.019473717579473387
    ],
    "gpu_memoire_go": 80,
    "serveur_puissance_w": 1200,
    "serveur_gpus": 8,
    "duree_vie_s": 94608000,
    "fabrication_serveur": {
      "kgco2e": 5700.0,
      "mj": 70000.0,
      "kgsbe": 0.37
    },
    "fabrication_gpu": {
      "kgco2e": 273.0,
      "mj": 3721.0,
      "kgsbe": 0.00895
    },
    "pue": [
      1.09,
      1.14
    ],
    "wue_site_l_par_kwh": [
      0.13,
      0.999
    ],
    "mix": {
      "USA": {
        "kgco2e": 0.3844,
        "mj": 9.6884,
        "kgsbe": 9.855e-08,
        "eau_l": 3.1321
      },
      "FRA": {
        "kgco2e": 0.04144,
        "mj": 9.3135,
        "kgsbe": 4.858e-08,
        "eau_l": 3.6737
      },
      "SWE": {
        "kgco2e": 0.03526,
        "mj": 4.73,
        "kgsbe": 7.771e-08,
        "eau_l": 6.0315
      },
      "WOR": {
        "kgco2e": 0.45829,
        "mj": 2.5871,
        "kgsbe": 1.349e-08,
        "eau_l": 3.908
      }
    },
    "mix_par_defaut": "USA"
  }
} as const
