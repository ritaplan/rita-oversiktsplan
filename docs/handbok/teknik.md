# Under huven

Den här sidan beskriver hur Rita Översiktsplan fungerar tekniskt: hur planen är lagrad, hur databasen och utcheckningen
fungerar, var inställningar sparas och vad som händer när du hämtar underlag, kontrollerar och levererar. Den riktar
sig till GIS-samordnare, databasadministratörer och andra som vill förstå eller felsöka pluginet.

Du behöver inte läsa den för att använda pluginet.

> Tabellerna i detalj, och var de avviker från Boverkets mall, står i [Datamodell](../datamodell.md). Symbolerna
> förklaras i [Symbologi](../symbologi.md). Hur du kör koden och testerna står i [Utveckling](../utveckling.md).

## Översikt

Pluginet är skrivet i Python och körs i QGIS 4. Koden är uppdelad i fyra delar:

```
rita_oversiktsplan/
  plugin.py        meny och kommandon
  core/            logiken: datamodell, lagring, ÖP-katalogen, symboler, export, regler, NGP-klient, arkivpaket
  gui/             verktygsfältet, kartverktygen och dialogerna
  bookmarks/       programmet Skapa bokmärken i planhandling
```

Planen är vanliga QGIS-vektorlager. Allt du ritar går genom QGIS egen redigering, med redigeringsbuffert, ångra och
spara. Delar av koden är kopierade från Rita Detaljplan, till exempel utcheckningen och NGP-klienten.

## Datamodellen

Pluginet följer tre underlag:

| Underlag | Version | Används till |
|---|---|---|
| Boverkets **GIS-databasmodell** för ÖP-modellen | 0.3 | Tabellernas och kolumnernas namn. |
| Boverkets **ÖP-katalog** | 2.2 | Värdena: innehållstyper, planhändelser, avsnittstyper med mera. |
| Lantmäteriets **nationella specifikation** för översiktsplan | test 4 | Exportformatet och reglerna i kontrollen. |

En plan som pluginet skapar har alltså samma struktur som Boverkets mall, med några medvetna avvikelser som beskrivs i
[Datamodell](../datamodell.md).

### Tabellerna

| Tabell | Innehåll |
|---|---|
| `oversiktsplan` | Planens uppgifter, en rad. |
| `innehall_op_<grupp>_polygon`, `_line`, `_point` | Planens innehåll: ett lager per grupp och geometrityp. |
| `innehall_op_plangeometri`, `innehall_op_omrade` | Plangeometri och områden, bara ytor. |
| `*_lookup` | Uppslagstabeller med ÖP-katalogens värden: värde, värdets id, grupp, gruppens id och katalogversion. |
| `beslut_op` | Antagandebeslutet och ändringarnas beslut. |
| `dokumentreferens_op`, `avsnittsbokmärke`, `dokumentavsnitt` | Planhandlingen, dess bokmärken och kopplingarna mellan avsnitt och innehåll. |
| `oversiktsplan_underlag`, `oversiktsplan_underlag_underlag` | Planens underlag och deras dokument. |
| `innehall_op_beror_annat_innehall` | Kopplingarna *berör annat innehåll*. |
| `rita_oversiktsplan_meta` | Pluginets metadata: schemaversion, katalogversion, koordinatsystem, standardvärden, etapper och pågående ändring. |
| `rita_otilldelad_yta`, `_linje`, `_punkt` | Geometri som ritats men ännu inte fått innehåll. Levereras aldrig. |

Pluginets egna tabeller börjar med `rita_` och följer aldrig med i en leverans.

En GeoPackage innehåller **en** översiktsplan. Därför har innehållslagren ingen kolumn som pekar på planen: kopplingen
följer av att de ligger i samma fil.

### Två slags UUID

- **`objektidentitet`** är objektets egen identitet: ett UUID som pluginet sätter när objektet skapas eller får
  innehåll. Det kan inte ändras, eftersom exporten, kopplingarna och planhandlingens bokmärken hänvisar till det.
- **`vardereferens`** och **`gruppreferens`** i uppslagstabellerna är ÖP-katalogens id för ett *värde*, till exempel
  *Bostadsförsörjning*. Det är samma för alla objekt med det värdet.

### Från ritad geometri till innehåll

```
Rita yta / linje / punkt
        │
        ▼
rita_otilldelad_yta / _linje / _punkt        (orange, gruppen "Att tilldela")
        │
        │  Tilldela innehåll: grupp + innehållstyp
        ▼
innehall_op_<grupp>_polygon / _line / _point (objektidentitet, planhändelse,
                                              standardvärden sätts)
```

När du tilldelar innehåll **flyttas** objektet från den otilldelade tabellen till rätt innehållstabell. Ändringen görs i
redigeringsbufferten och sparas när du avslutar redigeringen. Planens uppgifter sparas däremot direkt när du klickar
på *Spara* i dialogen.

### Kopplingar

| Koppling | Hur den lagras |
|---|---|
| **Berör annat innehåll** | Innehållets `beror_annat_innehall_id` pekar på rader i `innehall_op_beror_annat_innehall`, en per berört innehåll, med det berördas `objektidentitet`. |
| **Riksintressets id** | Kolumnen `objektidentitet_ri` i riksintressenas lager. |
| **Planhandlingen** | `dokumentavsnitt` har en rad per koppling mellan ett avsnitt och ett objekt: avsnittstyp, bokmärke, dokument och objektets `objektidentitet`. |
| **Beslut** | Planens `beslut` pekar på antagandebeslutet. Innehållets `beslut` pekar på en ändrings beslut. |

### Metadata i `rita_oversiktsplan_meta`

Tabellen är en nyckel–värde-tabell. Några nycklar:

| Nyckel | Innehåll |
|---|---|
| `schema_version` | Pluginets schemaversion (nu 4). |
| `epsg` | Planens koordinatsystem. |
| `standard_*` | Standardvärden för nytt innehåll. |
| `utbyggnadsordning` | Planens etapper som JSON: en lista med `{"namn", "period"}`. |
| `andring_beslut`, `andring_paborjat`, `andring_planhandelse`, `andring_planhandelse_datum` | Den pågående ändringen. Tas bort när ändringen antas. |
| `checkout` | Låset, när planen är utcheckad från en databas. |

Etapperna och ändringen ligger i metadatan i stället för i nya tabeller, så att planen behåller samma tabeller som
Boverkets mall.

### ÖP-katalogen

Pluginet har en kopia av ÖP-katalogen i `data/opkatalog.json`. När en plan skapas kopieras katalogens värden in i
planens uppslagstabeller. Planen behåller sedan **sin** katalogversion, även om pluginet senare får en nyare.
Boverket säger att en plan får fortsätta i den katalogversion som arbetet påbörjades i.

## Lagring i GeoPackage

En plan i en GeoPackage är en vanlig `.gpkg`-fil (SQLite) som kan öppnas i vilket GIS-program som helst.

- Koordinatsystemet är SWEREF 99 TM (EPSG:3006) eller en lokal SWEREF 99-zon (EPSG:3007–3018).
- Alla tabeller har `fid` som nyckel och `geom` som geometrikolumn.
- QGIS-projektet (`.qgz`) sparas bredvid och pekar på filen.

## Lagring i PostGIS

### Ett delat schema för flera planer

I PostGIS lagras planerna i ett **schema** som kan delas av många planer. Alla planer i schemat ligger i samma
tabeller, och kolumnen **`plan`** talar om vilken plan en rad hör till.

```
schema "oversiktsplaner"
  rita_oversiktsplan_schema   schemaversion, gemensam för hela schemat
  rita_oversiktsplan_meta     plan | key | value    (även låset)
  oversiktsplan               fid | plan | geom | …
  innehall_op_…_polygon       fid | plan | geom | …
  …_lookup                    fid | plan | …        (varje plan har sin katalogversion)
  …                           samma tabeller som i en GeoPackage, var och en med kolumnen plan
```

- Varje lager i QGIS är tabellen **filtrerad** på planens id, så du ser bara din plans rader.
- Även **uppslagstabellerna** har kolumnen `plan`, så att planer i samma schema kan ha olika katalogversioner.
- Varje tabell har ett index på `plan` och ett rumsligt index (GiST) på `geom`.
- Koordinatsystemet sitter i geometrikolumnens definition och är därför **gemensamt för hela schemat**.
- PostgreSQL tillåter högst 63 tecken i ett tabellnamn. Tabellerna för *Särskilt värdefull kulturmiljö* heter därför
  `innehall_op_sarskiltvardefullkulturmiljo_…` i databasen. I GeoPackage behålls Boverkets längre namn.

### Inloggning och behörighet

Pluginet använder en av **QGIS sparade PostgreSQL-anslutningar**, och inloggningen sköts av QGIS. Databasen måste ha
tillägget PostGIS. Användaren behöver kunna skapa schema och tabeller första gången, och sedan läsa, skriva och ta bort
rader. Ett schema från en äldre version (schema 3) uppgraderas när en plan i det öppnas första gången, vilket kräver
rätt att ändra tabellerna.

## Utcheckning och incheckning

```
  Databas (PostGIS)                         Din dator
  ─────────────────                         ─────────
  planen, skrivskyddad      ── checka ut ──▶  lås i rita_oversiktsplan_meta
                                              + lokal GeoPackage (du ritar här)
  planen, uppdaterad        ◀── checka in ──  allt skrivs i en transaktion,
                                              låset släpps, kopian tas bort
```

- **Låset** är en rad `checkout` i `rita_oversiktsplan_meta` med JSON: en slumpad nyckel (`token`), användarnamn, dator
  och tidpunkt. Medan låset sätts låses metadatatabellen kort (`LOCK TABLE … IN EXCLUSIVE MODE`), så att två personer
  inte kan checka ut samma plan samtidigt.
- **Utcheckningen** kopierar alla planens tabeller till en GeoPackage i QGIS profilmapp under
  `rita_oversiktsplan/checkouts`, och pekar om planens lager dit.
- **Incheckningen** är ett enda SQL-block (`DO $$ … $$`) som körs i en transaktion: kontrollera att låset fortfarande är
  ditt, ta bort planens rader i varje tabell, lägg in de lokala raderna (200 åt gången) och ta bort låset. Går något
  fel rullas allt tillbaka. Andra planers rader rörs aldrig.
- Raderna får nya `fid` i databasen. Det gör ingenting, eftersom alla kopplingar går via `objektidentitet`.
- **Återuppta** efter en krasch: den lokala kopian har samma `token` i sin metadata. När du checkar ut igen erbjuds
  kopian om låset fortfarande är ditt.

## Projektfilen, inställningar och cache

| Vad | Var | Innehåll |
|---|---|---|
| **Planens data** | GeoPackage eller PostGIS | Allt som levereras, plus pluginets `rita_`-tabeller. |
| **Projektet** (`.qgz`) | Där du valde | Lagren, stilarna och formulären. På planens grupp: var planen ligger (fil eller databas) och, när den är utcheckad, den lokala kopians sökväg och låsnyckel. På varje lager: vilken tabell det är. |
| **Inställningar** | QGIS användarprofil | Leveransen till NGP (miljö, adresser, namnet på autentiseringskonfigurationen) och ditt val av omklassning för Topografi 10. Nycklarna börjar med `rita_oversiktsplan/`. |
| **Inloggning till NGP** | QGIS autentiseringsdatabas | Nyckel och hemlighet, krypterade av QGIS. |
| **Utcheckade kopior** | QGIS profilmapp, `rita_oversiktsplan/checkouts/` | Lokala kopior av utcheckade databasplaner. |

## Hämtade underlag

| Underlag | Källa | Behandling |
|---|---|---|
| **Kommunens yta** (Ny översiktsplan) | SCB:s öppna geodata, WFS `geodata.scb.se`, skiktet DeSO 2025. | Alla statistikområden med kommunens kod slås ihop till en yta och räknas om till planens koordinatsystem. |
| **Riksintressen** | Boverkets karttjänst *Riksintressen* (ArcGIS REST, `gis2.boverket.se`). | Hämtas 1 000 objekt åt gången, förenklas med 5 m, hål under 1 000 m² tas bort. Myndighetens id sparas i `objektidentitet_ri`. |
| **Topografi 10 / Marktäcke** | Filer som du laddar ner själv från Lantmäteriets Geotorget. | Skikten känns igen på fältet `objekttyp`. Ytor slås ihop per värde och klipps mot planen, linjer slås ihop, allt förenklas med 5 m. |

Hämtningen går via QGIS nätverksinställningar, så proxy och certifikat från QGIS gäller. Byter SCB eller Boverket
tjänst slutar hämtningen fungera tills pluginet uppdateras.

## Symbolerna

Symbolerna byggs bara av QGIS **enkla symboler** (enkel yta, enkel linje, enkel punkt), eftersom de finns i SLD och kan
ritas av alla webbkartor. Klassningen görs direkt på fältet, så att SLD-filtren blir vanliga jämförelser.

- **Gruppen** avgör kantlinje och punktform. **Värdet** avgör färgen.
- Mark- och vattenanvändningens färger utgår från detaljplanens färger, och värdena skiljs åt med minst ΔE00 8,5.
- Utvecklingsinriktningens pilspetsar sparas i pluginets egen kolumn `rita_pilar`, som inte följer med i exporten.
- **Spara stilar för GeoServer (SLD)** gör om pilspetsarna från QGIS sätt till GeoServers (`endPoint`, `endAngle`).

Mer i [Symbologi](../symbologi.md).

## Exporten till Lantmäteriets format

Exporten (`core/export_lm.py`) läser planen, med ändringar som inte sparats, och skriver en `FeatureCollection` i
formatet **Översiktsplan 2.0** (mediatyp `application/vnd.lm.oversiktsplan.v2+json`):

- ett `oversiktsplan`-objekt med planens uppgifter, underlag och kopplingar till planhandlingen,
- ett `beslutOP`-objekt per beslut,
- ett `innehallOP`-objekt per innehåll, med geometrin i fältet `geometri`.

Under exporten

- har alla objekt `geometry: null` på GeoJSON-nivå, som schemat kräver,
- skrivs värden ur ÖP-katalogen som `{varde, vardereferens, grupp, gruppreferens}` ur planens uppslagstabeller,
- skrivs koordinaterna i planens koordinatsystem med millimeters precision och ytterringarna **moturs**,
- påverkar ett beslut antingen planen eller innehåll, aldrig båda (OP-JSON-005),
- utelämnas tomma fält, otilldelad geometri och pluginets egna kolumner.

Exporten ändrar ingenting i planen.

## Kontrollen

Kontrollen har två delar:

1. **Exporten** listar det som saknas för att filen ska följa schemat, till exempel obligatoriska fält och värden som
   inte finns i planens katalog.
2. **Reglerna** (`core/rules.py`) kontrolleras på den färdiga exportfilen: Lantmäteriets kvalitetskrav ÖP-X01–X07 och
   reglerna OP-JSON-001–044. Varje fynd har regelns id.

Spikar räknas som hörn där vinkeln mellan två linjesegment är högst 12° (ÖP-X05). Kontrollen validerar inte mot
JSON-schemat (ÖP-X01).

## Leveransen till NGP

NGP-klienten är kopierad från Rita Detaljplan och följer Lantmäteriets specifikation för Uppdatering-API 1.1. En
leverans går i fyra steg:

1. `POST /mottagning` – registrerar en mottagning för informationstypen `oversiktsplan`.
2. `POST /mottagning/{id}/forandringar` – registrerar en förändring med planens `objektidentitet`.
3. `POST …/forandringar/{objekt}/leverans` – laddar upp hela `FeatureCollection` från exporten.
4. `GET /mottagning/{id}` – följer statusen och hämtar valideringsrapporten.

Inloggningen är OAuth 2 (`client_credentials`), med nyckel och hemlighet från QGIS autentiseringsdatabas. Anropen körs i
en bakgrundsuppgift via QGIS nätverkslager.

> **Antaganden:** att informationstypen heter `oversiktsplan`, att mediatypen v2 tas emot och tokentjänstens adress.
> Alla kan ändras i inställningarna. Klienten är testad mot en låtsasserver men inte mot Lantmäteriets miljö.

## Arkivpaketet

Arkivpaketet (`core/archive.py`) skapar en mapp med `metadata/PREMIS.xml`, `schemas/` och `content/`. Planen är en
*representation* i PREMIS och filerna är filer som den har som delar. Kontrollsummorna är SHA-256. Mer om
modelleringen finns i Rita Detaljplans
[revision av arkivpaketet](https://github.com/ritaplan/rita-detaljplan/blob/main/docs/arkivpaket-revision.md).
