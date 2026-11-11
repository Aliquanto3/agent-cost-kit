#!/usr/bin/env bash
# Banc du relecteur dans la chaîne : même développement, deux relecteurs.
# Par essai : un clone jetable sans remote reçoit dev-story (Sonnet) puis second-avis (Haiku) ; ce clone est
# ensuite copié une fois par relecteur candidat, qui reçoit le même diff et la même liste du second avis.
# Un vérificateur en lecture seule dit enfin, par clone, quelles fiches de la vérité terrain restent présentes.
# L'orchestrateur est ce script : son coût et son aléa sortent de la comparaison.
#
# Usage : banc_relecteur.sh <dossier de sortie> "<story> <story>..." "<modèle:effort> <modèle:effort>..." [essais]
# Exemple : banc_relecteur.sh ../_bancs/2026-11-10 "usine-6-11 frugal-9-3" "opus:medium claude-fable-5-2:medium" 3
# Permissions : bancs/reglages-banc.json (acceptEdits, liste d'outils, ni réseau ni push). Relançable : un
# résultat déjà écrit n'est pas refait.
set -u
# Sous Windows, Python écrit en cp1252 : un second avis contenant « → » faisait échouer `texte`, et la liste
# arrivait vide au relecteur (3 essais sur 6 le 2026-11-10, 1 sur 6 le 2026-11-11).
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
KIT=$(cd "$(dirname "$0")/.." && pwd)
RACINE=$(dirname "$KIT")
SORTIE=$(mkdir -p "$1" && cd "$1" && pwd)
STORIES=$2 RELECTEURS=$3 ESSAIS=${4:-3}
REGLAGES=$KIT/bancs/reglages-banc.json
OUT=$SORTIE/resultats
mkdir -p "$OUT"
corps() { awk 'f>=2{print} /^---$/{f++}' "$KIT/agents/$1.md" > "$OUT/consigne-$1.md"; }
corps dev-story; corps second-avis; corps reviewer
champ() { uv run --no-project python -c "import json,sys; s=[x for x in json.load(open(sys.argv[1],encoding='utf-8'))['stories'] if x['id']==sys.argv[2]][0]; print(s[sys.argv[3]] if sys.argv[3]!='fiches' else ' '.join(s['fiches']))" "$KIT/bancs/corpus.json" "$1" "$2"; }
journal() { echo "$(date '+%F %T') $*" >> "$OUT/journal.txt"; }
session() { # session <fichier json> <modèle> <effort> <consigne ou -> <budget> <prompt>
  local f=$1 modele=$2 effort=$3 consigne=$4 budget=$5 prompt=$6
  [ -s "$f" ] && return 0
  local opt=(); [ "$consigne" != "-" ] && opt=(--append-system-prompt-file "$OUT/consigne-$consigne.md")
  # Lecture seule réelle pour le second avis et le vérificateur.
  case "$consigne" in -|second-avis) opt+=(--disallowedTools "Edit" "Write" "NotebookEdit" "Bash(git add:*)" "Bash(git commit:*)");; esac
  claude -p "$prompt" --model "$modele" --effort "$effort" --settings "$REGLAGES" "${opt[@]}" \
    --add-dir "$KIT/bancs" --max-budget-usd "$budget" --output-format json > "$f" 2> "$f.err"
}
texte() { uv run --no-project python -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8')).get('result') or '')" "$1"; }

une_story() {
  local story=$1
  local depot base tete spec lignes fiches
  depot=$(champ "$story" depot); base=$(champ "$story" base); tete=$(champ "$story" tete)
  spec=$(champ "$story" spec); lignes=$(champ "$story" spec_lignes); fiches=$(champ "$story" fiches)
  for essai in $(seq 1 "$ESSAIS"); do
    local id="$story-e$essai" dev="$SORTIE/clones/$story-e$essai-dev"
    if [ ! -d "$dev" ]; then
      git clone -q --no-hardlinks "$RACINE/$depot" "$dev" && cd "$dev" || continue
      git remote remove origin; git checkout -q -b "banc/$id" "$base"
      mkdir -p "$(dirname "$spec")"
      git -C "$RACINE/$depot" show "$tete:$spec" | head -n "$lignes" | sed "s/^status: .*/status: 'ready-for-dev'/" > "$spec"
      git add "$spec" && git commit -q -m "Banc : spec de la story (sans rapport ni revue)"
      uv sync -q > "$OUT/$id-uvsync.log" 2>&1
    fi
    cd "$dev" || continue
    session "$OUT/dev-$id.json" sonnet medium dev-story 8 "Implémente la story décrite dans $spec. Dépôt de travail : $dev (branche banc/$id, déjà créée ; il tient lieu de worktree). Lance les tests ciblés, puis commite sur cette branche. Ce dépôt n'a pas de remote : rien à pousser, rien à fusionner."
    journal "dev $id propre=$(git status --porcelain | wc -l) diff=[$(git diff --shortstat "$base" HEAD)]"
    session "$OUT/avis-$id.json" haiku medium second-avis 2 "Relis en lecture seule le diff de la story $spec dans $dev : git diff $base..HEAD. Rends ta liste de constats."
    journal "second-avis $id"
    local avis; avis=$(texte "$OUT/avis-$id.json")
    local sha_dev; sha_dev=$(git rev-parse HEAD)
    for cfg in $RELECTEURS; do
      local modele=${cfg%%:*} effort=${cfg##*:}
      local rid="$id-$modele-$effort" rev="$SORTIE/clones/$story-e$essai-$modele-$effort"
      if [ ! -d "$rev" ]; then
        git clone -q --no-hardlinks "$dev" "$rev" && cd "$rev" || continue
        git remote remove origin; git checkout -q -B "banc/$id" "$sha_dev"
        uv sync -q > "$OUT/$rid-uvsync.log" 2>&1
      fi
      cd "$rev" || continue
      session "$OUT/revue-$rid.json" "$modele" "$effort" reviewer 8 "Relis la story $spec dans $rev : git diff $base..HEAD. Corrige les constats Important réels, commite sur la branche banc/$id et consigne la revue dans la spec. Cadre du banc : ce dépôt n'a pas de remote, donc ni rebase, ni push, ni fusion ; CI de branche : absente. Une seule passe.
Liste du second avis (à vérifier, pas à croire) :
$avis"
      journal "revue $rid propre=$(git status --porcelain | wc -l) commits=$(git rev-list --count "$sha_dev"..HEAD) diff=[$(git diff --shortstat "$sha_dev" HEAD)]"
      session "$OUT/verif-$rid.json" sonnet medium - 2 "Vérification en lecture seule : ne modifie aucun fichier, ne commite rien. Lis $KIT/bancs/verite-terrain.json et ne garde que les fiches : $fiches. Pour chacune, dis si le défaut décrit est PRESENT, ABSENT ou SANS_OBJET dans l'état actuel de ce dépôt ($rev, diff git diff $base..HEAD), en lisant le code et, si utile, par un test ciblé (uv run pytest ou uv run python -c). Réponds par une ligne par fiche, sans rien d'autre : <id> | PRESENT ou ABSENT ou SANS_OBJET | fichier:ligne | preuve en une phrase."
      journal "verif $rid"
    done
  done
}
export -f une_story champ journal session texte
export KIT RACINE SORTIE RELECTEURS ESSAIS REGLAGES OUT
printf '%s\n' $STORIES | xargs -P 2 -I{} bash -c 'une_story {}'
journal FIN
