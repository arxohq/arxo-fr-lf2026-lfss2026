# LF 2026 et LFSS 2026 : les dispositions modificatives exécutées une à une

Arxo Law · contact : hi@arxo.io

Nous avons appliqué une à une les dispositions modificatives de la loi de financement de la
sécurité sociale pour 2026 (loi n° 2025-1403 du 30 décembre 2025) et de la loi de finances pour
2026 (loi n° 2026-103 du 19 février 2026) aux textes qu'elles modifient, dans leur version
antérieure (base LEGI de la DILA) : 1 781 opérations élémentaires, dont 1 303 exécutées telles
quelles. Nous avons compté les occurrences des mots cités, puis comparé le résultat aux versions
que LEGI rattache à ces lois. Chaque constat ci-dessous a été vérifié à la main sur l'édition
électronique du JORF diffusée par la DILA, sur le texte adopté par l'Assemblée nationale et sur
la base LEGI.

Arxo n'a aucun lien avec le Secrétariat général du Gouvernement, la DILA, la DGFiP, la DSS ou le
Parlement. Ce dossier n'est pas un conseil juridique ou fiscal.

> **English summary.** We parsed the amending provisions of the French 2026 budget acts (LF 2026,
> LFSS 2026) into 1,781 elementary operations, applied them to the prior consolidated text (DILA's
> LEGI database) — 1,303 execute exactly as written — and compared the result with the official
> consolidation. Every finding was checked by hand; the remaining differences are listed but not
> analysed. Open items: a garbled cross-reference in CGI art. 199
> sexdecies that only a corrective provision can fix; two future versions on Légifrance (CGI 1600
> for 2027, CSS L. 162-23-8 from 1 Sept 2027) that drop the 2026 amendments; a typo and a missing
> word in CSS L. 136-4. Back-test: the four places (three items) corrected by the official
> *rectificatif* of 23 May 2026 were found independently, without using it.

## Points principaux

1. **Article 199 sexdecies du CGI : une référence à corriger.** L'article 29, 2°, de la LF 2026
   insère d'abord une seconde occurrence des mots « de l'article D. 7231-1 du même code », puis
   remplace ces mots par « du même II » sans dire laquelle. La phrase en vigueur vise les services
   « mentionnés au 16° du II **du même II** ». Le texte adopté (T.A. n° 227) porte la même
   rédaction : un rectificatif ne peut pas corriger cette erreur ; il faut une disposition de
   coordination (« du II du même II » → « du même II »). Ni le rectificatif du 10 octobre 2026
   à la LF 2026, ni la loi n° 2026-492 du 12 juin 2026 (qui a pourtant modifié l'article), ni le
   PLF 2027 déposé n'y touchent. Aucun effet sur le montant du crédit n'a été identifié.
   *Statut : ouvert.*
2. **Légifrance : deux versions futures ne contiennent pas les modifications de 2026.**
   - Article 1600 du CGI, version du 1er janvier 2027 au 1er janvier 2028
     (LEGIARTI000049534935) : l'insertion de l'article 135, VI, A, de la LF 2026 (« et
     l'établissement public du commerce et de l'industrie de Corse ») manque ; elle figure dans
     les versions de 2026 et de 2028 à 2030.
   - Article L. 162-23-8 du CSS, version à compter du 1er septembre 2027 (LEGIARTI000048971734) :
     elle reprend le texte d'avant la LFSS 2026 et perd les deux changements de l'article 72, I,
     5°.
   *Statut : ouvert (erreur de consolidation ; le JO n'est pas en cause).*
3. **Article L. 136-4 du CSS, IV : une coquille et un mot manquant.** La version en vigueur porte « des
   bénéfices déterminés articles 50-0, 64 bis, 76 et 102 ter » et « du champ définiaux
   articles » ; le texte de la LFSS donne « déterminés aux articles » et « défini aux articles ».
   *Statut : ouvert (consolidation).*
4. **Contrôle de la méthode : quatre emplacements corrigés par le rectificatif du 23 mai 2026,
   retrouvés sans lui.** Le programme ne connaissait pas ce rectificatif (JO n° 0120,
   JORFTEXT000054125097). Il a signalé comme erreurs du texte publié l'article 18, II, de la LFSS
   (la loi de finances citée sous le numéro de la LFSS elle-même) et l'article 99, V, 4°, b et c,
   et 6° (« après le mot » là où le mot figure deux fois). Ce sont exactement les quatre
   emplacements, regroupés en trois points, que le rectificatif corrige. Voir [notes/exemple-rectificatif-2026-05-23.md](notes/exemple-rectificatif-2026-05-23.md).
5. **Six erreurs de citation**, sans incertitude sur le texte visé (dates, intitulés, mots
   cités). La consolidation a chaque fois exécuté le texte voulu. Aucun rectificatif ne les
   corrige au 23 octobre 2026.

## Tous les constats

Détail, identifiants et empreintes : [data/findings.csv](data/findings.csv).

| Code | Où | Constat | Statut |
|---|---|---|---|
| A2 | LF art. 29, 2°, b → CGI 199 sexdecies | « au 16° du II du même II » | ouvert ; disposition de coordination |
| B2 | CGI 1600, version 2027 | insertion de LF art. 135, VI, A absente | ouvert (consolidation) |
| B3 | CSS L. 162-23-8, version 01/09/2027 | changements de LFSS art. 72, I, 5° absents | ouvert (consolidation) |
| B1 | CSS L. 136-4, IV | « déterminés articles », « définiaux » | ouvert (consolidation) |
| B4 | CIBS L. 312-37, version du 01/02/2026 au 01/08/2026 | lien « Modifié par » vers LF art. 71 absent ; texte juste | ouvert (métadonnées) ; réduit le 26/10/2026 |
| A1 | LFSS art. 18, II | loi de finances citée sous le numéro de la LFSS | corrigé le 23/05/2026 |
| A8 | LFSS art. 99, V, 4°, b et c ; 6° | « après le mot » au lieu de « après la première occurrence du mot » | corrigé le 23/05/2026 |
| A3 | LF art. 183, II | « loi n° 2020-1721 du 9 décembre 2020 » (29 décembre) | ouvert (citation) |
| A4 | LFSS art. 12, II, 1° | « de financement rectificative pour 2016 » | ouvert (citation) |
| A5 | LFSS art. 102, II, 3° | « de financement pour la sécurité sociale pour 2025 » | ouvert (citation) |
| A6 | LF art. 81, V | « code général des collectivité territoriales » | ouvert (citation) |
| A7 | LF art. 105, I, E, 8°, a ; art. 113, I, 4°, a | mots cités différents du texte modifié | ouvert (citation) |
| B5 | CGI 220 quinquies | coquille ancienne de la consolidation, corrigée par la DILA | sans objet |
| D1–D4 | voir data/findings.csv | ambiguïté sans effet, renvois à des articles abrogés, versions futures | possible ; lecture juridique nécessaire |
| E | 34 opérations | numérotation selon le texte d'avant l'instruction précédente | observation de méthode |

## Exécution

| | LFSS 2026 | LF 2026 |
|---|---:|---:|
| Opérations élémentaires (dispositions qui modifient un autre texte) | 483 | 1 298 |
| Exécutées telles quelles sur la version LEGI antérieure | 353 | 950 |
| Abrogation confirmée par LEGI | 15 | 24 |
| Rattachées à une version LEGI d'une autre date | 29 | 77 |
| Hors périmètre : article absent de l'extraction LEGI utilisée | 32 | 28 |
| Non résolues par l'analyseur (cible, subdivision, construction) | 36 | 155 |
| Mots cités introuvables ou nombre d'occurrences différent | 15 | 40 |
| Autres (pas de version LEGI rattachée, rétablissement existant, lien absent) | 3 | 24 |

Toutes les opérations, avec leur statut : [data/operations.csv](data/operations.csv). La colonne
`revue` dit ce qui a été vu à la main : « constat » (renvoie à `findings.csv`), « revue manuelle
(échantillon) », « conforme à LEGI » (exécutée et identique à la version LEGI). **« non analysé »
signifie seulement que la ligne n'a pas été revue à la main. Ce n'est ni un constat, ni une
anomalie.** La plupart de ces lignes relèvent des limites de l'analyseur (tableaux, intitulés,
renvois complexes, renumérotation du CIBS).

## Méthode et limites

- **Analyse.** Chaque article modificatif est découpé en énumérations (I, A, 1°, a, tirets) et en
  opérations : remplacer, supprimer, insérer, compléter, rédiger, abroger, renuméroter, créer.
  Le nombre d'occurrences vient de l'instruction (« à chaque occurrence », « la première
  occurrence », « deux fois ») ; sans précision, une seule occurrence est attendue.
- **Exécution.** Pour chaque article modifié, l'opération est appliquée à la version LEGI qui
  précède celle que LEGI rattache à la loi. Le résultat est comparé à cette version, sans tenir
  compte des espaces, des guillemets, des tirets et de la ponctuation finale.
- **Contrôles supplémentaires.** JORF / texte adopté (T.A. n° 199 rect. et n° 227) ;
  dispositions censurées par le Conseil constitutionnel / versions LEGI ; citations de lois
  (numéro, date, intitulé) ; versions futures ; renvois vers des articles abrogés.
- **Rectificatifs.** Nous avons lu les 551 archives du JORF diffusées par la DILA du 31 décembre
  2025 au 23 octobre 2026 (293 dates d'archive ; plusieurs archives par date). Elles contiennent
  154 textes dont le titre porte « rectificatif » ; deux portent sur ces lois : 23 mai 2026 (LFSS)
  et 10 octobre 2026 (LF, article 198 seulement). Ce dépouillement porte sur les rectificatifs :
  il ne dit pas qu'aucune autre loi ou ordonnance n'a modifié ces passages. Pour A2 et B1 à B4,
  l'état retenu est celui des versions LEGI au 22 octobre 2026.
- **État de LEGI.** Fichier global du 13 juillet 2025 et incréments jusqu'au 22 octobre 2026
  (`LEGI_20261022-214745`).
- **Limites.** Ont été revus à la main : un échantillon de 71 opérations (articles du CSS et du
  CGI sur les prestations familiales, la revalorisation, le barème de l'IR, la CSG) et tous les
  constats. Le reste des écarts n'a pas été revu : 142 étapes de comparaison de la LF et 44 de
  la LFSS qui diffèrent de LEGI, et les opérations que l'analyseur n'a pas résolues (786 lignes
  « non analysé » dans `operations.csv`). Les lois non
  codifiées ne sont couvertes que si les incréments LEGI les contiennent. Les dates
  d'application viennent de LEGI. Le JO authentique (PDF) n'a pas été consulté : les textes
  publiés sont lus dans l'édition électronique du JORF diffusée par la DILA.

## Ce que nous n'affirmons pas

- Aucune affirmation n'est faite sur les montants effectivement liquidés, versés ou mis en
  recouvrement.
- Une erreur de consolidation (B) n'est pas une erreur de la loi : le texte publié au Journal
  officiel n'est pas en cause.
- Nous ne prétendons pas connaître l'intention du législateur. Quand le texte et une intention
  probable divergent, nous le disons et laissons la question à ceux qui peuvent y répondre.

## Registre

Les constats de ce dossier inscrits au [registre des constats d'Arxo](https://arxo.io/findings/)
(données : dépôt GitHub arxohq/arxo-findings). La fiche du registre indique l'état à jour, les
destinataires informés et, le cas échéant, la correction officielle.

| Code | Registre | Disposition |
|---|---|---|
| A1 | [ARXO-2026-0013](https://arxo.io/findings/ARXO-2026-0013/) | LFSS 2026, art. 18, II — corrigé par le rectificatif du 23 mai 2026 |
| A8 | [ARXO-2026-0014](https://arxo.io/findings/ARXO-2026-0014/) | LFSS 2026, art. 99, V — corrigé par le rectificatif du 23 mai 2026 |
| A2 | [ARXO-2026-0015](https://arxo.io/findings/ARXO-2026-0015/) | LF 2026, art. 29, 2° — CGI, art. 199 sexdecies |
| A3 | [ARXO-2026-0016](https://arxo.io/findings/ARXO-2026-0016/) | LF 2026, art. 183, II |
| A4 | [ARXO-2026-0017](https://arxo.io/findings/ARXO-2026-0017/) | LFSS 2026, art. 12, II, 1° |
| A5 | [ARXO-2026-0018](https://arxo.io/findings/ARXO-2026-0018/) | LFSS 2026, art. 102, II, 3° |
| A6 | [ARXO-2026-0019](https://arxo.io/findings/ARXO-2026-0019/) | LF 2026, art. 81, V |
| B1 | [ARXO-2026-0020](https://arxo.io/findings/ARXO-2026-0020/) | CSS, art. L. 136-4, IV (Légifrance) |
| B2 | [ARXO-2026-0021](https://arxo.io/findings/ARXO-2026-0021/) | CGI, art. 1600, version 2027 (Légifrance) |
| B3 | [ARXO-2026-0022](https://arxo.io/findings/ARXO-2026-0022/) | CSS, art. L. 162-23-8, version du 1er septembre 2027 (Légifrance) |

## Qui a été informé

Le 23 octobre 2026, par courrier électronique :
- la Direction de la législation fiscale (DGFiP), avec copie au Secrétariat général du
  Gouvernement — article 199 sexdecies du CGI et erreurs de citation (A2 à A7) ;
- les rapporteurs généraux des commissions des finances de l'Assemblée nationale et du Sénat —
  proposition de rédaction pour l'article 199 sexdecies ;
- la DILA, avec copie à la DGFiP (fiscalité locale) — points de consolidation (B1 à B4).

Le 23 octobre 2026, par le formulaire Légifrance :
- la DILA — B1, B2, B3 et B4 (pour B4, uniquement la version LEGIARTI000053593049,
  après vérification des liens affichés sur le site).

Le 23 octobre 2026, un message a été envoyé par le formulaire du ministère de la Santé,
à l'attention de la DSS (bureaux 5B et 1A) et de la DGOS — B1, B3, A4, A5.

D'autres services seront ajoutés ici à mesure des envois.

## Reproduire

Voir [scripts/README.md](scripts/README.md). Les archives DILA se téléchargent sur
https://echanges.dila.gouv.fr/OPENDATA/ et se vérifient avec [data/sources.sha256](data/sources.sha256).
Les résultats bruts sont dans [data/raw/](data/raw/).

## Sources

| Source | Où | SHA-256 |
|---|---|---|
| LFSS 2026, loi n° 2025-1403 (JO n° 0306 du 31/12/2025), JORFTEXT000053226384 | archive `JORF_20251231-020917.tar.gz` | `d96fc1758b86262ccdf06eac1e9db81d62daaa006817170ac29d48a5618d6d8a` |
| LF 2026, loi n° 2026-103 (JO n° 0043 du 20/02/2026), JORFTEXT000053508155 | archive `JORF_20260220-015513.tar.gz` | `91df4f307c5964b8bcd0aeae229849b9c8df12cf7fc2b5ed9766ca0087fe16c8` |
| Rectificatif LFSS, JO n° 0120 du 23/05/2026, JORFTEXT000054125097 | archive `JORF_20260523-002456.tar.gz` | `7d84c80ce524a9f73fba682b87efecbdb974b1e004f504016081a507408b036a` |
| Rectificatif LF, JO n° 0237 du 10/10/2026, JORFTEXT000054969274 | archive `JORF_20261010-002617.tar.gz` | `652798c004800c0ced2bb7b14f101178237344906fc9ef04b0a2aabe467779cf` |
| LEGI, fichier global du 13/07/2025 | `Freemium_legi_global_20250713-140000.tar.gz` | `f862b4a2238e11ec3c48ec70f3b1c68bac0bb1985907841666b98608653d4eca` |
| LEGI, dernier incrément | `LEGI_20261022-214745.tar.gz` | `b231b37e62830b528f13b45cdde0eaf379bffcbb99896e25c5b64aba2a67662d` |
| T.A. n° 199 rect. (LFSS, texte définitif) | https://www.assemblee-nationale.fr/dyn/docs/PRJLANR5L17BTA0199.raw | `66f4a4194077dae044acf7dc8b0cb41fe0dac18911e3d30a30fca74736031e30` |
| T.A. n° 227 (LF, texte définitif) | https://www.assemblee-nationale.fr/dyn/docs/PRJLANR5L17BTA0227.raw | `4d919684661ca4e48be82be7c2b7af2fc9f9b681df8645b7b919a1b18ed780c4` |
| PLF 2027 n° 3210 (texte déposé) | https://www.assemblee-nationale.fr/dyn/docs/PRJLANR5L17B3210.raw | `3d59bc73dd9aaefde9767940de3c484944dc7b1fa395fb429a4fded89f381a97` |

Liste complète : [data/sources.sha256](data/sources.sha256) ; les 551 archives du JORF et leurs
empreintes : [data/rectificatifs-jorf-20251231-20261023.json](data/rectificatifs-jorf-20251231-20261023.json).

## Corrections

Si vous trouvez une erreur dans ce dossier, écrivez à hi@arxo.io. Les corrections seront
notées ici.

- 2026-10-26 — **B4 réduit à une version.** Quatre des cinq versions citées le 23 octobre ont bien
  un lien vers la loi qui les modifie : CGI 1679 A (LEGIARTI000053278878), CGI 1600
  (LEGIARTI000053578862) et CIBS L. 312-37 (LEGIARTI000053592986, LEGIARTI000053593023). Dans le
  XML LEGI, ce lien est de type MODIFIE (1679 A) ou MODIFICATION (les trois autres) ; notre contrôle
  ne lisait pas les liens MODIFICATION et a aussi manqué celui de 1679 A. La DILA nous l'a signalé
  le 26 octobre pour les deux versions de L. 312-37. Reste la version de L. 312-37 du 1er février
  au 1er août 2026 (LEGIARTI000053593049) : aucun lien vers la loi
  n° 2026-103 depuis sa première diffusion (`LEGI_20260227-215222`) jusqu'à `LEGI_20261025-211638`.
  Archives et empreintes : [data/sources.sha256](data/sources.sha256).

## Historique

- 2026-10-23 — première publication.
- 2026-10-25 — registre : identifiants de dix constats.
- 2026-10-26 — B4 réduit à une version (voir Corrections).

## Licence

Code et notes : Apache License 2.0 ([LICENSE](LICENSE)). Les données issues de la DILA (JORF,
LEGI) sont réutilisées sous Licence Ouverte 2.0 ; source : DILA. Les comparaisons avec les textes
adoptés utilisent les documents publiés par l'Assemblée nationale ; source : Assemblée nationale.
`data/findings.csv` est rédigé à la main ; `data/operations.csv` est produit par
`scripts/build_operations_csv.py`.
