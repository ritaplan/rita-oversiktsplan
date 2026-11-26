# Säkerhetsbeskrivning

Det här dokumentet är till för dig som ska bedöma om Rita Översiktsplan kan användas i en organisation, till exempel en
kommuns IT-säkerhetsfunktion. Det beskriver vad pluginet gör, vilka data som rör sig vart, vad som är granskat och vad
som inte är det. Rapportera säkerhetsbrister enligt [SECURITY.md](../SECURITY.md).

**Omfattning:** version 0.1.27. Första genomgången gjordes för 0.1.13 (2026-11-03). Den bygger på sökningar över hela
koden och på läsning av koden som har nätverk, databas och filhantering. Den 2026-11-25 gicks det igenom som tillkommit
sedan dess: sökningarna nedan kördes om, och koden för databashanteraren (import, export, kopiering, borttagning och
skrivskydd), lagrens adresser och visningen av text ur databasen och filer lästes igenom. Genomgången hittade fynd 9 och
10, som är åtgärdade i 0.1.27. Annat som tillkommit har inte lästs särskilt, men omfattas av sökningarna. Pluginet delar
mycket kod med [Rita Detaljplan](https://github.com/ritaplan/rita-detaljplan), vars
[säkerhetsbeskrivning](https://github.com/ritaplan/rita-detaljplan/blob/main/docs/sakerhet.md) har samma upplägg.

## Läs det här först: vad dokumentet är och inte är

- Pluginet är skrivet med AI-stöd och underhålls av en enskild person på fritiden. Det är en experimentell
  utvecklingsversion.
- Genomgången nedan är en **statisk kodgranskning** (läsning och sökning i källkoden, utförd av underhållaren med AI-stöd).
  Det är **ingen oberoende säkerhetsgranskning** och inget penetrationstest. Sedan 0.1.13 körs dessutom automatisk
  kodanalys (CodeQL och ruff) på GitHub vid varje ändring. De hittar en annan sorts fel än en människa som läser, men
  ersätter inte en oberoende granskning.
- Testsviten (se `tests/`) kontrollerar att funktionerna beter sig rätt. Den bevisar inte att koden är säker.
- En organisation som har krav på säkerhetsgranskning bör låta en oberoende person gå igenom koden. Se
  [Rekommendationer](#rekommendationer-för-en-organisation).

## Kort version för IT-säkerhetsfunktionen

| Fråga | Svar |
| --- | --- |
| Skickas data ut från datorn? | Bara när användaren själv väljer det: leverera planen till Lantmäteriet (*Leverera till NGP*), hämta riksintressen från Boverkets karttjänst, eller hämta kommunens yta från SCB när en ny plan skapas. Ingen telemetri, inga analysverktyg, inga uppdateringskontroller i pluginet. *Kontrollera anslutningen* loggar in mot Lantmäteriet när användaren klickar. |
| Vilka rättigheter behövs? | Inga särskilda. Pluginet körs i QGIS med den inloggade användarens rättigheter. Det installerar inget och ändrar inga systeminställningar. Det startar inga program, förutom att webbläsaren eller filhanteraren öppnas när användaren klickar på en länk. |
| Körs kod som hämtats utifrån? | Nej. Koden använder inte `eval`, `exec`, `subprocess`, `pickle` eller liknande. |
| Vilka beroenden finns? | Bara QGIS (med dess Python, Qt och GDAL). Se materiallistan (SBOM) som följer med varje release. |
| Var lagras lösenord och nycklar? | I QGIS autentiseringsdatabas, aldrig av pluginet. Databaslösenord hanteras av QGIS egna anslutningar. |
| Finns personuppgifter? | Inga i pluginet. Vid utcheckning och skrivskydd i PostGIS lagras användarnamn och datornamn i planens metadata (fynd 2). Planens egna texter kan i sig innehålla personuppgifter, men de stannar på användarens dator tills användaren själv levererar eller exporterar dem. |
| Hur kommer pluginet till användaren? | Som zip-fil från GitHub Releases eller via en pluginkälla som pekar på GitHub. Zip-filen byggs reproducerbart, och en kontrollsumma och en materiallista följer med varje release. |
| Är koden granskad? | Av underhållaren med AI-stöd, och automatiskt med CodeQL. **Inte** av en oberoende part. Ingen certifiering finns. |
| Vem svarar vid en sårbarhet? | Underhållaren, via GitHubs privata rapportering (se [SECURITY.md](../SECURITY.md)). Målet är ett första svar inom 14 dagar. Det är en enskild person på fritiden. |

## Sammanfattning

| Område | Bedömning |
| --- | --- |
| Körning av kod från indata (`eval`, `exec`, `subprocess`, `pickle`) | Förekommer inte i pluginets kod |
| Beroenden utanför QGIS och Pythons standardbibliotek | Inga (se [Beroenden](#beroenden)) |
| Nätverksmål | Fyra: Lantmäteriet (verifiering/produktion) eller en adress som användaren själv anger, Boverkets karttjänst och SCB:s karttjänst |
| Hemligheter | Sparas inte av pluginet, utan i QGIS autentiseringsdatabas |
| Databasåtkomst | Via QGIS sparade anslutningar, med användarens egna databasrättigheter |
| Öppna fynd | 5 informativa (fynd 2–5 och 7). Åtgärdade: fynd 8 (medel) i 0.1.24, fynd 6, 9 och 10 (låga) och fynd 1 (felaktig dokumentation) |
| Distribution | Osignerade zip-filer med kontrollsumma och materiallista, och en pluginkälla som pekar på GitHub (se [Leveranskedja](#leveranskedja-och-distribution)) |

## Vad pluginet är och vilka rättigheter det har

Pluginet är ett Python-plugin i QGIS (QGIS 4.0 eller senare). Det körs i QGIS egen process med **samma rättigheter som
den inloggade användaren**. QGIS har ingen sandlåda för plugin, så detta gäller varje QGIS-plugin, oavsett hur det är
skrivet. Pluginet gör inget vid installation utom att QGIS importerar modulen; ingen kod körs från installationsskript.

Omfång: cirka 16 000 rader Python under `rita_oversiktsplan/` (utan tester).

## Dataflöden

| Vad | Varifrån | Vart | Hur |
| --- | --- | --- | --- |
| Planleverans (JSON) | Lokal plan | Lantmäteriets API (`api-ver.` eller `api.lantmateriet.se`), eller en adress användaren anger | Bara när användaren väljer *Leverera till NGP*. Via QGIS nätverksstack, https. Klienten (`core/ngp_client.py`) är en kopia av den i Rita Detaljplan och är inte provad mot Lantmäteriets riktiga miljö |
| Planleverans (fil) | Lokal plan | En JSON-fil som användaren pekar ut | Skrivs av användaren själv |
| Kontroll av anslutningen | Nyckeln | Lantmäteriets tokentjänst och API:ets hälsoadress | Bara när användaren klickar *Kontrollera anslutningen* |
| Databashanteraren | Planer i PostGIS, eller en fil användaren väljer | Databasen, eller GeoPackage- och JSON-filer i en mapp användaren väljer | Import, export, kopiering och borttagning (`core/transfer.py`, `json_transfer.py`). Före borttagning föreslås en säkerhetskopia |
| Riksintressen | Boverkets karttjänst (`gis2.boverket.se`, ArcGIS REST) | Planens lager för riksintressen | Bara när användaren väljer *Hämta riksintressen*. Frågan innehåller planens utsnitt (koordinater) och inget annat. Via QGIS nätverksstack. Svaret är GeoJSON som läggs in som underlag |
| Kommunens yta | SCB:s karttjänst (`geodata.scb.se`, WFS) | Planens plangeometri | Bara när en ny plan skapas med rutan *kommunens yta* ikryssad. Frågan innehåller kommunkoden (fyra siffror) |
| Topografi 10 / Marktäcke | GeoPackage- eller zip-filer som användaren själv laddat ner | Underlag i planen | Läses lokalt med GDAL. Inget nätverk |
| Plandata | Lokal GeoPackage eller PostGIS-schema | QGIS lager | GDAL/SQLite respektive QGIS PostgreSQL-leverantör |
| Planhandling (Word) | Word-fil som användaren väljer | Ny Word-fil eller webbsida (HTML) som användaren sparar | Läses lokalt med Pythons `zipfile` och `xml.etree`. Originalet ändras inte. Inget nätverk |
| Arkivpaket | Filer som användaren väljer | En ny mapp med kopior, PREMIS-metadata och scheman | Skrivs lokalt av `core/archive.py`. Originalen rörs inte |

Nätverksanrop finns bara i `core/ngp_client.py` och i de funktioner som skickas `qgis_get` (`gui/riksintressen_dialog.py`),
alltså hämtningen av riksintressen och av kommunens yta. Pythons `urllib` används enbart för att tolka och bygga adresser
(`urllib.parse`), inte för att hämta något. Pluginet skickar ingen telemetri, och det finns inga andra nätverksmål i koden.

## Hemligheter och inloggning

- **Lantmäteriets nyckel och hemlighet** sparas inte av pluginet. Användaren väljer en autentiseringskonfiguration i QGIS
  autentiseringsdatabas (typen *Grundläggande autentisering*). Pluginet sparar bara konfigurationens id i QGIS
  inställningar, tillsammans med miljö och adresser.
- **Åtkomsttoken** hämtas med `client_credentials`, hålls bara i minnet i klientobjektet och sparas inte på disk.
  Den förnyas vid 401.
- **Databaslösenord** hanteras av QGIS egna PostgreSQL-anslutningar. Pluginet frågar aldrig efter lösenord och väljer en
  befintlig anslutning ur QGIS lista.
- **Projektfiler (.qgz)** får av pluginet anslutningens *namn*, schema, plan-id, ett utcheckningslås (slumpmässig
  token) och, efter en leverans, mottagningens och planens id hos Lantmäteriet samt miljöns namn. Sedan 0.1.24 innehåller
  lagrens adresser **inget databaslösenord** (fynd 8). En hänvisning till QGIS krypterade inloggning (`authcfg`) står kvar. Leveransinställningarna (adresser, vald autentisering) ligger i användarens profil,
  inte i projektet. Se fynd 5.
- Adresser till API:et och tokentjänsten måste börja med `https://`. Bara `http://` mot `localhost` och `127.0.0.1`
  tillåts (för tester). Omdirigeringar följs inte vid leverans.
- QGIS egna inställningar för proxy och certifikat gäller, så TLS-kontrollen är QGIS standard. Pluginet stänger aldrig av
  certifikatkontroll och använder inte certifikatfästning.

## Filer

Pluginet skriver:

- planens GeoPackage och projektfil (`.qgz`) i den mapp användaren väljer,
- en lokal arbetskopia (GeoPackage) vid utcheckning från PostGIS,
- leveransfilen, en planhandling (Word eller HTML) och stilfiler (SLD) på den plats användaren väljer (originalfilen
  skrivs inte över),
- arkivpaket (en ny mapp med kopior och metadata) under en mapp användaren väljer,
- exporterade planer och säkerhetskopior från databashanteraren (en befintlig fil skrivs aldrig över), och tillfälliga
  filer i operativsystemets temporärmapp under kopiering, import och export,
- inställningar via `QgsSettings`.

Pluginet raderar bara filer det självt har skapat: den lokala arbetskopian när en plan checkas in eller utcheckningen
hävs (`core/checkout.py`), en halvfärdig plan- eller exportfil när skapandet misslyckas (`core/geopackage.py`,
`core/transfer.py`), tillfälliga filer, och en halvfärdig arkivpaketmapp (`core/archive.py`). Det raderar aldrig filer
som användaren valt.

## Databaser

**GeoPackage** nås med Pythons `sqlite3` och GDAL. Tabellnamn kommer från pluginets egen modell, inte från indata.

**PostGIS** nås med QGIS anslutningsobjekt. SQL byggs som text, eftersom gränssnittet inte har bundna parametrar.
Skydden är:

- identifierare (schema, plan-id) som pluginet skapar valideras mot `^[a-z][a-z0-9_]{0,62}$`, och schemat får inte
  vara `public`, `information_schema` eller börja med `pg_`. Namn som **läses** ur databasen valideras inte, utan
  citeras i SQL (`quote()`) och görs ofarliga när de blir filnamn (`storage.file_name`, fynd 9),
- textvärden skrivs som SQL-literaler med fördubblade enkla citattecken (`literal()`),
- tal skrivs via `int()` och `float()`.

Det här är korrekt förutsatt att databasen har `standard_conforming_strings = on` (förvalt sedan PostgreSQL 9.1). Se fynd 3.

Pluginet kör `DROP SCHEMA ... CASCADE` bara för att städa bort ett schema som just skapades i samma anrop och där
skapandet misslyckades halvvägs. Det rör aldrig ett schema som fanns innan. Databashanterarens *Ta bort plan* tar bort
de valda planernas rader i en transaktion, efter en bekräftelse, och inte om planen är utcheckad eller skrivskyddad.

**Behörighet:** pluginet har ingen egen åtkomstkontroll. Vem som kan läsa och ändra planer avgörs helt av
databasrollen i QGIS-anslutningen. Utcheckningens lås (se fynd 2) och skrivskyddet är samarbetsmekanismer för att
undvika samtidig redigering och ändringar av misstag, inte säkerhetsfunktioner.

## Beroenden

Pluginet importerar bara QGIS (`qgis`, `osgeo`/GDAL) och Pythons standardbibliotek. Det installerar inga paket med
`pip` och har ingen `requirements`-fil. Uppdateringar av beroenden följer därför QGIS egna.

En medföljande kopia av ÖP-katalogen, kommunlistan, Lantmäteriets JSON-scheman och PREMIS-schemat ligger som filer i
`rita_oversiktsplan/data/` (se [NOTICE.md](../NOTICE.md)).

**Materiallista (SBOM).** `tools/build_sbom.py` skapar en materiallista i CycloneDX-format
(`rita_oversiktsplan-<version>.sbom.cdx.json`) med pluginet, de medföljande datafilerna (med kontrollsummor) och det som
krävs men inte levereras (QGIS med Python, PyQt och GDAL). Skriptet läser alla importer i koden och avbryter om ett nytt
paket dyker upp som inte är listat, så listan kan inte tyst bli ofullständig. Den följer med varje release.

Testerna kräver bara QGIS och Pythons `unittest`.

## Leveranskedja och distribution

- Koden ligger öppet på GitHub under GPL-2.0-eller-senare. Commits och taggar är **inte signerade**.
- Release-filen (`rita_oversiktsplan-<version>.zip`) byggs reproducerbart av `tools/build_zip.py` (samma innehåll ger samma
  zip). Från och med 0.1.13 följer en **SHA-256-kontrollsumma** (`.zip.sha256`) och en **materiallista**
  (`.sbom.cdx.json`) med varje release. Zip-filen är **inte signerad**. Du kan själv kontrollera den: kontrollera taggen i
  repot, kör `python tools/build_zip.py` och jämför kontrollsumman med den som publicerats.
- Det finns automatiska kontroller på GitHub (`.github/workflows/`): CodeQL (statisk kodanalys, vid varje ändring och en
  gång i veckan), ruff (kodkontroll), en kontroll att zip-filen blir identisk vid två byggen och att koden inte fått nya
  beroenden, samt OpenSSF Scorecard. Dependabot håller de fastlåsta versionerna av dessa verktyg uppdaterade. Testsviten
  (`tests/`) kräver QGIS 4 och körs inte på GitHub utan lokalt före varje release.
- Pluginkällan (`plugins.xml`) läses från `main` på GitHub. Den som kan skriva till repot kan alltså få kod installerad hos
  alla som uppdaterar via pluginkällan. Skyddet är kontot på GitHub. Läget 2026-11-25 (kontrollerat via GitHubs API): en regel för `main` stoppar radering och tvångspush, GitHubs
  hemlighetsskanning och Dependabot-varningar är på, privat rapportering av sårbarheter är på och organisationen kräver
  tvåfaktorsinloggning. Regeln kräver varken pull request eller gröna kontroller, eftersom underhållaren pushar direkt till
  `main`. Push-skyddet, som stoppar en push som innehåller en hemlighet, är påslaget. Samma inställningar gäller
  organisationens övriga repon, bland annat webbkartan [rita-detaljplan-origomap](https://github.com/ritaplan/rita-detaljplan-origomap).
- Pluginet är **inte** publicerat i QGIS officiella pluginarkiv och har därför inte genomgått dess granskning.

## Fynd

Allvarlighetsgrad: *medel* = kan ge någon annan tillgång de inte ska ha, *låg* = kan missbrukas men med liten effekt,
*information* = bra att känna till, ingen åtgärd krävs.

### 1. Dokumentationen sa att inget skickas till Lantmäteriet eller Boverket (information, rättad)

Den tidigare `SECURITY.md` påstod att databasen var det enda pluginet kontaktar över nätverket och att leverans till NGP
inte fanns. Det stämde inte: pluginet kan leverera till Lantmäteriets API (sedan 0.1.1) och hämta riksintressen från
Boverket och kommunens yta från SCB. En läsare som bedömde pluginet utifrån det påståendet fick en felaktig bild.
*Åtgärd:* `SECURITY.md` och det här dokumentet beskriver nu alla nätverksmål. Alla anrop görs bara på användarens begäran.

### 2. Låset och skrivskyddet avslöjar användarnamn och datornamn (information)

Vid utcheckning från PostGIS skrivs operativsystemets användarnamn och datorns namn (`getpass.getuser()`,
`platform.node()`, i `core/checkout.py`) i planens metadatatabell, så att andra kan se vem som har planen. Detsamma
gäller den som skrivskyddar en plan, tillsammans med det skäl som skrivits. Det syns för alla som kan läsa schemat. Räkna
det som personuppgift i er bedömning.

### 3. SQL byggs som text (information)

Se avsnittet [Databaser](#databaser). Skyddet bygger på validerade identifierare och korrekt citering. Det finns
enhetstester för `quote()` och `literal()`, men inget test med avsiktligt illasinnade indata mot en riktig databas. Mönstret
är mer sårbart för framtida ändringar än bundna parametrar skulle vara.

### 4. Egen API-adress (information)

I inställningarna går adresserna till API:et och tokentjänsten att ändra, för Produktion och Verifiering var för sig.
Nyckel och hemlighet från den valda autentiseringskonfigurationen skickas då till den tokentjänst som användaren själv
har skrivit in. Det är avsiktligt (för test och andra miljöer) men innebär att en vilseledd användare kan skicka sina
uppgifter till fel adress. Adressen måste vara `https://`, och knappen *Standardadresser* återställer Lantmäteriets.
Bekräftelsen före leveransen visar miljö och adress, och texten kodas innan den visas så att planens namn inte kan
förvränga den.

### 5. Leveransmottagning lagras i projektfilen (information)

Efter en leverans sparas mottagningens id, planens id och miljöns namn i projektet (`remember_delivery`), så att nästa
leverans uppdaterar samma mottagning. En manipulerad projektfil skulle kunna peka en senare leverans mot ett annat
mottagnings-id. Om det lyckas avgörs av Lantmäteriets behörighetskontroll mot användarens nyckel; det har inte testats
här. Öppna därför inte projektfiler från okända källor och leverera, som alltid, först till verifieringsmiljön.

### 6. Hämtning av riksintressen kunde pågå utan slut (låg, åtgärdad i 0.1.13)

Riksintressen hämtas sida för sida (`core/riksintressen.py`, `fetch_layer`) så länge tjänsten svarar att det finns fler
objekt. En tjänst, eller ett svar som någon lyckats förvanska, som alltid sa "fler" skulle få hämtningen att fortsätta
för alltid och fylla minnet med objekt, så att QGIS låste sig.
*Effekt:* En driftstörning på den egna datorn. Ingen kod körs och inga data läcker. Kräver att Boverkets tjänst eller
anslutningen dit är komprometterad (anslutningen är https med QGIS certifikatkontroll).
*Åtgärd:* hämtningen avbryts efter 200 sidor (200 000 objekt per lager) med ett felmeddelande. Det finns ett test.

### 7. Filer läses utan storleksgräns (information)

Planhandlingen (`core/planhandling.py`, `planhandling_html.py`) och arkivpaketet (`core/archive.py`) läser filer som
användaren själv valt. Word-filer (zip) läses helt till minnet och deras XML tolkas med
Pythons `xml.etree.ElementTree`. En avsiktligt konstruerad fil (en zip-bomb eller en mycket stor XML-del) kan därför ta
mycket minne och tid. `ElementTree` hämtar inga externa entiteter eller dokumenttyper, så filer kan inte få programmet att
läsa andra filer eller anropa nätverket. Skyddet mot "entitetsexplosioner" ligger i XML-biblioteket expat (version 2.4 och
senare har gränser); vilken version som följer med din QGIS har inte kontrollerats här. Ingenting skrivs ut ur en zip-fil
till disk (inga `extractall`), så sökvägsangrepp via filnamn i zip-filen är inte möjliga. Topografidata läses av GDAL
(`/vsizip/`), vars egna gränser gäller.
Webbversionen av planhandlingen kodar all text och gör bara länkar till `http(s)://`, e-post och ankare klickbara.
*Rekommendation:* öppna inte Word-filer, projekt eller GeoPackage från okända avsändare. Ingen åtgärd planeras.

### 8. Databaslösenordet sparades i projektfilen (medel, åtgärdad i 0.1.24)

Lagrens adresser innehöll användarnamn och lösenord i klartext och sparades i projektfilen (`.qgz`). Alla som fick
filen kunde läsa lösenordet till databasen.
*Åtgärd:* adresserna innehåller inget lösenord sedan 0.1.24 (`storage.layer_address`).
**Projektfiler som sparats med en äldre version har fortfarande lösenordet:** spara om dem och byt lösenord på
databaskontot.

### 9. Namn ur databasen kunde styra var en fil skrevs (låg, åtgärdad i 0.1.27)

Vid export och säkerhetskopiering i databashanteraren blev planens id ur databasen filnamn utan kontroll. Den som kunde
skriva i databasen kunde lägga in ett id som `..\..\namn`, så att filen hamnade utanför den valda mappen hos den som
sedan exporterade. Befintliga filer skrevs inte över, och filerna var planfiler (`.gpkg` eller `.json`). Bekräftat med
prov. *Åtgärd:* `storage.file_name` ersätter tecken som byter mapp. Test: `tests/test_untrusted_text.py`.

### 10. Text ur databasen och filer kunde tolkas som formaterad text (låg, åtgärdad i 0.1.27)

Verktygstips, etiketter, meddelanderutor och meddelandefältet visade bland annat skälet till ett skrivskydd och
användarnamn utan att kontrollera innehållet. Text som såg ut som HTML tolkades, och en bild som den pekade på lästes in
(bekräftat med en lokal fil). På Windows kan en sådan sökväg sannolikt även peka på en server i nätverket och då avslöja
inloggningsuppgifter (inte provat). Kräver skrivrätt i databasen eller att användaren öppnar en fil från någon annan.
Ingen kod kunde köras. *Åtgärd:* sådan text visas som ren text eller kodas (`gui/richtext.py`). Test:
`tests/test_untrusted_text.py`. Ställena har letats upp genom sökning, men det kan finnas fler med samma beteende och
låga effekt.

## Det som inte omfattas

- Ingen dynamisk analys, ingen fuzzning och inget penetrationstest.
- Ingen skanning av beroenden i verktyg: det finns inga externa Python-beroenden i QGIS att skanna, men QGIS, GDAL och
  PostgreSQL ligger utanför pluginets kontroll. Materiallistan gör att en organisation kan göra den kontrollen själv.
- QGIS och GDAL:s egna sårbarheter, till exempel vid inläsning av hotfyllda filer, bedöms inte här.
- Att Boverkets och SCB:s tjänster är pålitliga. Pluginet litar på svaren som på all annan öppen data och lägger in dem
  som underlag; en användare ska granska det som hämtats.
- Dataskydd (GDPR) bedöms inte, förutom att fynd 2 pekar på att användarnamn kan lagras.
- Tillgänglighet, drift och support.

## Rekommendationer för en organisation

1. **Låt en oberoende person granska koden** innan produktionsanvändning. Börja med `core/ngp_client.py`,
   `core/storage.py`, `core/checkout.py` och `core/riksintressen.py`. Det är där nätverk, inloggning och databas finns.
   Fortsätt med filläsarna (`core/planhandling*.py`, `core/archive.py`), som tolkar filer från andra (fynd 7).
2. **Använder ni PostGIS och har projektfiler sparade före 0.1.24:** spara om dem och byt lösenord (fynd 8).
3. **Installera en fast, granskad version** centralt (zip-filen), och använd inte den öppna pluginkällan i
   produktionsmiljön. Jämför filens innehåll med taggen i repot innan den godkänns.
4. **Börja i Lantmäteriets verifieringsmiljö** (`api-ver`), inte i produktion, och kontrollera leveransen där först.
   Leveransen är inte provad mot Lantmäteriets riktiga miljö (se [Kända begränsningar](kanda-begransningar.md)).
5. **Begränsa databasrollen** som används i PostGIS-anslutningen till det schema och de tabeller som behövs, eftersom
   pluginet inte har någon egen behörighetskontroll.
6. **Bestäm vem som äger underhållet.** En enskild frivillig underhållare är en verksamhetsrisk. Ett kommunalt samarbete
   eller en organisation som tar över repot minskar den.
7. **Skydda GitHub-kontot** med tvåfaktorsinloggning om ni använder repot som källa, och överväg en egen kopia (fork)
   som ni själva kontrollerar.
8. **Läs in materiallistan** (`.sbom.cdx.json`) i ert eget verktyg för sårbarhetsbevakning, så att QGIS-versionen som
   pluginet körs i följs upp tillsammans med övriga program.

## Så kan du verifiera uppgifterna

Kontrollera att en nedladdad zip-fil är den som publicerats (från och med 0.1.13, i PowerShell):

```
Get-FileHash rita_oversiktsplan-<version>.zip -Algorithm SHA256
```

Värdet ska vara detsamma som i filen `rita_oversiktsplan-<version>.zip.sha256` på releasesidan. Vill du inte lita på att
filen är oförändrad sedan den laddades upp, hämta taggen `v<version>` från repot, kör `python tools/build_zip.py` och
jämför kontrollsumman: bygget är reproducerbart, så samma källkod ger exakt samma zip-fil.

Sökningar mot källkoden (kör i repots rot):

```
# Inga dynamiska kodkörningar eller processer (träffar i dialogrutor är Qts egna .exec())
grep -rnE "\b(eval|exec|compile|__import__|subprocess|os\.system|pickle|marshal)\b" rita_oversiktsplan --include=*.py

# Alla nätverksanrop
grep -rnE "QNetwork|QgsNetworkAccessManager|QgsBlockingNetworkRequest|urlopen|socket" rita_oversiktsplan --include=*.py

# Alla importer som inte är QGIS eller standardbibliotek
grep -rhE "^\s*(import|from) " rita_oversiktsplan --include=*.py
```
