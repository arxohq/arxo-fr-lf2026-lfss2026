# Reproduire

Python 3.12 ou plus récent, bibliothèque standard uniquement. Les archives téléchargées sont des
données : placez-les dans un répertoire à part et lancez les scripts avec `python3 -I`.
Vérifiez chaque archive avec `data/sources.sha256` avant usage.

## 1. Base LEGI

Deux usages différents :

- **Reproduire nos résultats.** Notre base contenait, du fichier global
  `Freemium_legi_global_20250713-140000.tar.gz`, seulement les codes (`code_en_vigueur`,
  `code_non_vigueur`) et les fiches de version de tous les textes (`texte/version`), extraits avec
  `tar --include` puis chargés par `ingest-dir` ; ensuite exactement les 473 incréments listés dans
  `data/raw/legi-archives.tsv` (de `LEGI_20250712-211706` à `LEGI_20261021-213023`), dans l'ordre
  des noms. Les lois non codifiées n'y figurent donc que si un incrément les contient. Avec le
  fichier global complet, la base est plus large et certains statuts (« article absent de
  l'extraction LEGI ») peuvent changer.

  ```bash
  mkdir legi-global && tar -xzf Freemium_legi_global_20250713-140000.tar.gz -C legi-global \
      --include '*/code_en_vigueur/*' --include '*/code_non_vigueur/*' --include '*/texte/version/*'
  python3 -I scripts/legi_index.py --db legi.sqlite ingest-dir legi-global \
      --name Freemium_legi_global_20250713-140000.tar.gz \
      --sha f862b4a2238e11ec3c48ec70f3b1c68bac0bb1985907841666b98608653d4eca --size 1171027316
  python3 -I scripts/legi_index.py --db legi.sqlite ingest $(awk 'NR>1 {print $2}' data/raw/legi-archives.tsv)
  ```

  (Les motifs `--include` ci-dessus décrivent le contenu retenu ; la ligne de commande exacte du
  premier passage n'a pas été conservée.)
- **Vérifier l'état actuel.** Ajouter les incréments postérieurs (par exemple
  `LEGI_20261022-214745`, cf. `data/legi-check-20261022.json`) et relancer `legi_check.py`.

La base SQLite obtenue fait environ 3 Go.

## 2. Textes publiés et opérations

```bash
python3 -I scripts/jorf_text.py --text JORFTEXT000053226384 --out lfss2026.json <archives JORF extraites>
python3 -I scripts/jorf_text.py --text JORFTEXT000053508155 --out lf2026.json <archives JORF extraites>
python3 -I scripts/fr_legistics.py lfss2026.json --law LFSS2026 --out ops-lfss2026.json
python3 -I scripts/fr_legistics.py lf2026.json --law LF2026 --out ops-lf2026.json
```

`an_text.py` lit de la même façon un texte de l'Assemblée nationale (texte adopté, projet de
loi) à partir de son fichier `.raw`.

## 3. Exécution et comparaison avec LEGI

```bash
python3 -I scripts/run.py --db legi.sqlite --law-cid JORFTEXT000053226384 --ops ops-lfss2026.json --out run-lfss2026.json
python3 -I scripts/run.py --db legi.sqlite --law-cid JORFTEXT000053508155 --ops ops-lf2026.json --out run-lf2026.json
python3 -I scripts/build_operations_csv.py run-lfss2026.json run-lf2026.json --slice data/raw/slice.json --out operations.csv
```

## 4. Contrôles

```bash
python3 -I scripts/ta_diff.py --jorf lfss2026.json --ta PRJLANR5L17BTA0199.raw --out ta-diff-lfss.json
python3 -I scripts/cc_check.py --db legi.sqlite --decision cc2025-899.json --law lfss2026.json --law-cid JORFTEXT000053226384 --out cc-lfss.json
python3 -I scripts/cite_check.py --db legi.sqlite --law lfss2026.json --self-num 2025-1403 --out cites-lfss.json
python3 -I scripts/future_check.py --db legi.sqlite --results run-lfss2026.json --out future-lfss.json
python3 -I scripts/refs.py --db legi.sqlite --results run-lfss2026.json --ops ops-lfss2026.json --out refs-lfss.json
```

(Même chose pour la LF 2026 avec T.A. n° 227, la décision 2026-901 DC et `--self-num 2026-103`.)

## 5. Rectificatifs et état actuel de LEGI

```bash
python3 -I scripts/scan_rectificatifs.py <répertoire des archives JORF quotidiennes> scan.jsonl
python3 -I scripts/summarize_scan.py rectificatifs.json scan.jsonl
python3 -I scripts/legi_check.py legi.sqlite legi-check.json
python3 -I scripts/legi_dump.py legi.sqlite legi-texts LEGIARTI000054251333 LEGIARTI000049534935
```

`scan_rectificatifs.py` relève tous les textes dont le titre contient « rectificatif » et, pour
ceux qui visent les lois n° 2025-1403 et n° 2026-103, le texte complet du rectificatif.

Les résultats de nos propres exécutions sont dans `data/raw/`. `operations.csv` en dérive par
`build_operations_csv.py` ; `findings.csv` est rédigé à la main à partir de ces résultats et des
textes cités.
