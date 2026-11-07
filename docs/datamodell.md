# Datamodell – Rita Översiktsplan

Pluginet lagrar en översiktsplan i en GeoPackage-fil med samma tabeller och kolumner som Boverkets
[GIS-databasmodell för ÖP-modellen](https://www.boverket.se/sv/om-boverket/oppna-data/gis-databas-op-modell/),
version **0.4** (från pluginets version 0.1.15; tidigare 0.3). Enligt Boverket följer den versionen test 5 av
Lantmäteriets
[nationella specifikation för översiktsplan](https://www.lantmateriet.se/sv/nationella-geodataplattformen/datamangder/oversiktsplan/),
som ännu inte är publicerad; exporten följer fortfarande test 4 (se [Kända begränsningar](kanda-begransningar.md)).
Värdena kommer från Boverkets [ÖP-katalog](https://www.boverket.se/sv/om-boverket/oppna-data/api-for-op-katalogen/),
version **2.3**. Modellen finns i koden i `rita_oversiktsplan/core/model.py`.

## Tabellerna

| Tabell | Innehåll |
|---|---|
| `oversiktsplan` | Planens uppgifter, en rad (kommunkod och kommunnamn, titel, planhändelse, datum, digitalt ursprung, antagandebeslutet) |
| `innehall_op_<typ>_polygon`, `_line`, `_point` | Planens innehåll, ett lager per innehållstyp och geometrityp. Kolumnen `oversiktsplan` pekar på planens objektidentitet |
| `innehall_op_plangeometri`, `innehall_op_omrade` | Plangeometri och områden (bara ytor) |
| `*_lookup` | Värden ur ÖP-katalogen: värde, värdets id, grupp, gruppens id och katalogversion |
| `dokumentreferens_op`, `dokumentavsnitt`, `avsnittsbokmärke` | Hänvisningar till planhandlingen och dess avsnitt (bokmärken i Word) |
| `oversiktsplan_underlag`, `oversiktsplan_underlag_underlag` | Planens underlag (fliken *Underlag* i Planens uppgifter): en rad per underlagstyp med eget `underlag_id`, kopplad till sina dokument i `dokumentreferens_op` (kortnamnet är underlagstypen) |
| `innehall_op_beror_annat_innehall` | *Berör annat innehåll*: en rad per koppling, med innehållet som berör (`objektidentitet`) och innehållet som berörs (`beror_objektidentitet`) |
| `innehall_op_extern_referens_ri` | Ett riksintresse (`objektidentitet`) kopplat till en dokumentreferens (`dokumentreferens_id`); pluginet fyller inte i den än |
| `beslut_op` | Beslut om planen (*beslutOP* i Lantmäteriets specifikation): beslutande organisation (namn och organisationsnummer), instans (kommunfullmäktige), diarienummer. `oversiktsplan.beslut` pekar på antagandebeslutets objektidentitet |
| `beslut_op_handelse` | Beslutets händelser, en rad per händelse: *fattat*, *överklagat* eller *laga kraft*, med datum |
| `beslut_op_dokumentreferens` | Beslutets dokument (till exempel protokollet); pluginet fyller inte i den än |
| `rita_oversiktsplan_meta` | Pluginets egen tabell: schemaversion (5 sedan 0.1.15), databasmodell, katalogversion, koordinatsystem och standardvärdena för nytt innehåll (nycklar som börjar på `standard_`) |
| `rita_otilldelad_yta`, `rita_otilldelad_linje`, `rita_otilldelad_punkt` | Pluginets egna tabeller: geometri som ritats men ännu inte fått innehåll. Ett objekt flyttas till rätt innehållslager när det tilldelas innehåll. Följer inte med i en leverans |

**Två slags UUID.** Varje objekt (planen, varje innehåll, beslutet) har en egen `objektidentitet`: ett UUID som
pluginet sätter när objektet skapas eller tilldelas, unikt för just det objektet. Det syns i formuläret och
attributtabellen men går inte att ändra, eftersom exporten, kopplingarna och planhandlingens bokmärken hänvisar till det.
ÖP-katalogens UUID är något annat: `vardereferens` (och `gruppreferens`) i uppslagstabellerna, som identifierar ett
*värde* i katalogen, till exempel *Bostadsförsörjning*. Det är samma för alla objekt med det värdet, och följer med i
exporten som `innehallstyp.vardereferens`.

**I en PostGIS-databas** (se [Användarhandledning](anvandning.md)) har schemat samma tabeller, med en kolumn `plan`
(planens id) i varje tabell, även uppslagstabellerna och metadatatabellen, så att flera planer kan dela schemat och
ändå ha var sin katalogversion. `fid` är en `serial`-kolumn och geometrin heter `geom` (SRID 3006). PostgreSQL tillåter högst 63 tecken i ett tabellnamn, så tabellerna för *Särskilt värdefull kulturmiljö* heter `innehall_op_sarskiltvardefullkulturmiljo_…` i databasen (i GeoPackage behålls Boverkets längre namn). Tabellen
`rita_oversiktsplan_schema` har schemats version. Låset vid utcheckning är en rad `checkout` i
`rita_oversiktsplan_meta`.

**Planhandlingen** (se [Användarhandledning](anvandning.md)) sparas i Boverkets dokumenttabeller:
`dokumentreferens_op` får en rad för Word-dokumentet (namn, länk till filen, `dokumentreferens_id`, och samma värde i
`identitet` och `producentens_identitet`), `avsnittsbokmärke` en rad per bokmärke (namnet och rubriken), och
`dokumentavsnitt` en rad per koppling mellan ett avsnitt och ett objekt (avsnittstyp, bokmärke, dokumentet och objektets
`objektidentitet`). `dokumentavsnitt.dokument_id` får också objektets objektidentitet. Det är en tolkning: mallen
beskriver inte kolumnen närmare. Kopplingar till hela planen gäller raden i `oversiktsplan`.

**Innehåll utan geometri** (till exempel bostadsförsörjning som bara beskrivs i text) sparas i gruppens ytlager
(`…_polygon`) med tom geometri. Geometrin är frivillig för innehåll i specifikationen, men mark- och
vattenanvändningen ska enligt föreskrifterna vara lägesbestämd och kan inte sakna geometri.

## Uppgradering från databasmodell 0.3 (pluginets version 0.1.14 och äldre)

En plan som skapats med en äldre version av pluginet uppgraderas när den öppnas första gången, enligt Boverkets
*Ändringsförteckning ÖP-mallen, version 0.3 till 0.4* (november 2026). Innan filen ändras sparar pluginet en kopia
bredvid den, `<filnamn>_fore_uppgradering.gpkg`. Uppgraderingen gör det som förteckningen beskriver att man annars gör
för hand:

| I 0.3 | I 0.4 |
|---|---|
| Innehållet hörde till planen genom att ligga i samma fil | Allt innehåll, även plangeometrin, får `oversiktsplan` = planens objektidentitet |
| Innehållets `beror_annat_innehall_id` pekade på rader i `innehall_op_beror_annat_innehall` | Raden får båda objektidentiteterna; kolumnen på innehållet tas bort |
| `beslut_op` hade `beslutande_organisation` och tre datumkolumner | `beslutande_organisation_namn`, och en rad i `beslut_op_handelse` per datum |
| `dokument_id` på innehållet och planen, `underlag_id` på planen, `extern_referens_ri_id` på riksintressena | Borttagna (de användes inte till något) |
| ÖP-katalogen 2.2 i uppslagstabellerna | ÖP-katalogen 2.3. Värden som bytt namn får det nya namnet, även i innehållet: *Fiske* blir *Yrkesfiske*, *Fyndighet av ämnen och material* blir *… eller material*, och kategorierna LIS och särskilt värdefull kulturmiljö heter som i föreskrifterna |

Värdena känns igen på sina id:n i ÖP-katalogen (`vardereferens`), som är oförändrade när ett värde byter namn. Ett
värde vars id inte finns i den nya katalogen lämnas som det är; exporten säger då till. Metadatan får
`opkatalog_version_fore_uppgradering` med katalogversionen före uppgraderingen.

I en PostGIS-databas görs samma sak för alla planer i schemat på en gång, i en transaktion, första gången någon som har
rätt att ändra tabellerna öppnar en plan i schemat.

## Var pluginet avviker från Boverkets mall

- **Nyckel, geometri och koordinatsystem.** Alla tabeller har `fid` som nyckel och `geom` som geometrikolumn, och
  alla lager ligger i samma koordinatsystem: SWEREF 99 TM (EPSG:3006, som i mallen och förvalt) eller en lokal
  SWEREF 99-zon (EPSG:3007–3018), som Lantmäteriets specifikation också tillåter. Det står i metadatan (`epsg`). I
  mallen har några tabeller `OBJECTID` (beslutstabellerna, `oversiktsplan`, `avsnittsbokmärke` och några värdelistor),
  och `dokumentreferens_op` saknar nyckel, vilket Boverket själv varnar för (QGIS och GDAL får då instabila id:n).
- **Plangeometri.** `innehall_op_plangeometri` har kolumnen `vertikal_avgransning`, som mallen saknar men
  specifikationen har för allt innehåll. Precis som i mallen har den `precisering` men inte kompletterande
  innehållstyp. *Område* har varken precisering eller kompletterande innehållstyp, som i mallen.
- **Beslut.** `beslut_op` har även `rubrik` och `arkividentitet`, som finns i specifikationens *beslutOP* men inte i
  mallen. Ändringar känns igen på rubriken (se nedan). Händelsetypen i `beslut_op_handelse` är fritext i mallen; pluginet
  använder specifikationens kodlista (*fattat*, *överklagat*, *laga kraft*).
- **Typer.** Datum lagras som datum, ja/nej-fält som booleska fält, och `digitalt_ursprung` som ja/nej (text i
  mallen). Presentationsskalan är ett heltal, som i specifikationen.
- **Borttaget.** `anvandningsstatus` i mark- och vattenanvändning och utvecklingsinriktning finns kvar i mallen men togs
  bort ur ÖP-katalogen i version 2.0, så pluginet har den inte.
- **Uppslagstabellerna** har samma kolumner överallt (även `grupp_varde` och `gruppreferens`, som mallen har i sex av
  dem) och fylls med värden ur den medföljande ÖP-katalogen 2.3. Värdena är desamma som i mallen.
- **Jämförelse med mallfilen.** Pluginets fil har jämförts med Boverkets `databasmodell_op_0.4.gpkg` (hämtad
  2026-11-07), tabell för tabell, kolumn för kolumn och värde för värde. Alla mallens tabeller och kolumner finns, utom
  det som står i den här listan.
- **Behållet som i mallen:** tabellnamnet `avsnittsbokmärke` (med ä).

## ÖP-katalogen i pluginet

Pluginet har en kopia av ÖP-katalogen i `rita_oversiktsplan/data/opkatalog.json`. Den hämtas från Boverkets öppna API
med `python tools/update_opkatalog.py`. Text och bild i API:et omfattas av CC0 enligt Boverkets användarvillkor.

När en plan skapas kopieras katalogens värden in i planens uppslagstabeller. Planen behåller sedan den
katalogversionen, utom när pluginet uppgraderar planen till en ny databasmodell (som 0.4, som följer ÖP-katalogen 2.3):
då får planen pluginets katalog, med värdena som bytt namn omdöpta (se ovan). Boverket säger att en plan får fortsätta i
den katalogversion som arbetet påbörjades i; i 2.3 har inga värden försvunnit, bara bytt namn.

## Pluginets eget fält i utvecklingsinriktningens linjer

`innehall_op_utvecklingsinriktning_line` har kolumnen `rita_pilar` (från schema 4), som inte finns i Boverkets mall:
pilspetsarna i kartan (*slut*, *start*, *båda* eller *ingen*; tomt betyder temats standard). Den följer inte med i
exporten till Lantmäteriet.

## Kopplingar

- **Berör annat innehåll:** en rad i `innehall_op_beror_annat_innehall` per koppling, med det berörande och det
  berörda innehållets objektidentitet. Ett innehåll som byter typ (Tilldela innehåll) behåller sin objektidentitet och
  därmed sina kopplingar.
- **Riksintressets id** sparas i `objektidentitet_ri` i lagren för riksintressen.
- **Beslut (från 0.1.5):** antagandebeslutet (planens `beslut`) påverkar bara planen. Innehållets `beslut` pekar på en
  ändrings beslut. Äldre planer där innehållet har antagandebeslutets id exporteras utan det (OP-JSON-005).

## Utbyggnadsordning (0.1.5)

Planens etapper står i meta-tabellen under nyckeln `utbyggnadsordning`, som JSON: en lista med `{"namn", "period"}`
i utbyggnadsordning. Innehållets fält `utbyggnadsordning` (mark- och vattenanvändning, utvecklingsinriktning) får
etappens text, `namn (period)`. Ingen ny tabell eller kolumn behövs.

## Ändring av planen (0.1.5)

En ändring är en rad i `beslut_op` med rubriken *Ändring: namn*. Den pågående ändringen står i meta-tabellen:

| Nyckel | Värde |
|---|---|
| `andring_beslut` | ändringsbeslutets objektidentitet |
| `andring_paborjat` | datum påbörjat (blir innehållets `datum_paborjat`) |
| `andring_planhandelse`, `andring_planhandelse_datum` | ändringens planhändelse |

Nytt innehåll får dessa värden och `beslut` = ändringsbeslutet. Ett beslut utan händelser (fattat, överklagat, laga
kraft) som inte är planens räknas som pågående och exporteras inte. När ändringen antas tas nycklarna bort.

**Hämtade riksintressen** (0.1.5) har `objektidentitet_ri` = myndighetens id och `hamtatdatum` = dagen för hämtningen.
