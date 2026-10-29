# Kom igång

Här installerar du pluginet, skapar din första översiktsplan och lär känna verktygsfältet.

<!-- FILM: kom-igang | Från installation till en ny översiktsplan med kommunens yta, ca 3 min -->

## Innan du börjar

- Du behöver **QGIS 4.0 eller senare**. Pluginet är testat med QGIS 4.2.2 på Windows.
- Pluginet är en **tidig utvecklingsversion**. Läs [Kända begränsningar](../kanda-begransningar.md) innan du använder
  det i ett skarpt planarbete.
- Underlagen ändras fortfarande. Lantmäteriets specifikation för översiktsplan är i testversion, och Boverkets
  GIS-databasmodell uppdateras under teståret.

## Installera pluginet

Du kan installera på två sätt. Det andra sättet gör att nya versioner syns direkt i QGIS.

### Alternativ 1: från en zip-fil

1. Ladda ned `rita_oversiktsplan-<version>.zip` från
   [Releases](https://github.com/ritaplan/rita-oversiktsplan/releases).
2. Starta QGIS och välj **Tillägg → Hantera och installera tillägg… → Installera från ZIP**.
3. Peka ut zip-filen och klicka på **Installera tillägg**.
4. Kontrollera under **Installerade** att *Rita Översiktsplan* är ikryssat.

### Alternativ 2: som pluginkälla

1. Välj **Tillägg → Hantera och installera tillägg… → Inställningar**.
2. Klicka på **Lägg till…** under *Pluginkällor*.
3. Ange ett valfritt namn och den här adressen:
   `https://raw.githubusercontent.com/ritaplan/rita-oversiktsplan/main/plugins.xml`
4. Kryssa i **Visa experimentella tillägg**.
5. Gå till **Alla** och installera *Rita Översiktsplan*.

<!-- BILD: installera-pluginkalla.png | Dialogen Hantera och installera tillägg, fliken Inställningar med pluginkällan tillagd -->

När pluginet är installerat finns verktygsfältet **Rita Översiktsplan** och menyn
**Insticksprogram → Rita Översiktsplan** i QGIS.

## Skapa en ny översiktsplan

1. Klicka på **Ny översiktsplan** (kartan med grönt plus) i verktygsfältet.
2. Fyll i dialogen:
   - **Kommun** – skriv några bokstäver och välj i listan. Kommunkoden följer med.
   - **Planens titel** – till exempel *Översiktsplan 2040*.
   - **Lagras i** – *Lokal fil (GeoPackage)* eller *PostGIS-databas*. Välj fil om du är osäker. Databasen går bara att
     välja om QGIS har sparade PostgreSQL-anslutningar, se [Lagring och databaser](lagring.md).
   - **Filnamn** och **Spara i mapp** – filnamnet föreslås utifrån titeln.
   - **Koordinatsystem** – SWEREF 99 TM är förvalt. Du kan också välja en av de tolv lokala SWEREF 99-zonerna.
     Koordinatsystemet går **inte** att ändra efteråt.
   - **Påbörjad** – dagen arbetet med planen påbörjades.
   - **Plangeometri: Hämta kommunens hela yta (från SCB)** – ikryssad från början. Kryssa ur om planen bara gäller en
     del av kommunen; då ritar du plangeometrin själv.
3. Klicka på **Skapa**.

<!-- BILD: ny-plan-dialog.png | Dialogen Ny översiktsplan med kommun, titel och koordinatsystem ifyllda -->

Det här händer:

- Pluginet skapar en GeoPackage-fil med samma tabeller som Boverkets GIS-databasmodell för ÖP-modellen, fylld med
  värden ur ÖP-katalogen.
- Planen läggs överst i lagerpanelen, i gruppen **Översiktsplan – *titeln***.
- Kommunens yta hämtas från SCB och blir planens plangeometri. Går den inte att hämta, till exempel utan internet,
  skapas planen ändå och du får ett meddelande.
- QGIS-projektet sparas som `filnamn.qgz` i samma mapp, om det inte redan var sparat under ett annat namn.

> **Tips:** Fyll i [Planens uppgifter](planens-uppgifter.md) innan du börjar ge objekten innehåll. Då får allt nytt
> innehåll rätt planhändelse och standardvärden direkt.

## Verktygsfältet

Knapparna visas som ikoner. Håll muspekaren över en ikon för att se vad den gör. Knapparna står i samma ordning som i
Rita Detaljplan.

<!-- BILD: verktygsfalt-oversikt.png | Verktygsfältet Rita Översiktsplan med numrerade knappar -->

| Knapp | Vad den gör | Läs mer |
|---|---|---|
| **Ny översiktsplan** (karta med grönt plus) | Skapar en ny plan. | ovan |
| **Öppna översiktsplan** (mapp) | Lägger till en plan från en fil eller databas. | [Lagring](lagring.md) |
| **Checka ut / Checka in** (databas med pil) | För planer i en PostGIS-databas. | [Lagring](lagring.md#checka-ut-och-checka-in) |
| **Börja redigera** (penna) | Öppnar alla planens lager för redigering. | [Rita och tilldela](rita-och-tilldela.md) |
| **Avsluta redigering** (diskett) | Sparar eller kastar ändringarna. | [Rita och tilldela](rita-och-tilldela.md#spara) |
| **Planens uppgifter** (skrivplatta) | Planhändelse, beslut, underlag, etapper och standardvärden. | [Planens uppgifter](planens-uppgifter.md) |
| **Leverans och export** (låda med pil upp) | Kontrollera, spara som JSON, leverera till NGP eller skapa arkivpaket. | [Leverera](leverera.md) |
| **Skapa bokmärken i planhandling** (dokument med grön etikett) | Kopplar Word-texten till planens innehåll. | [Planhandlingen](planhandlingen.md) |
| **Markera** / **Avmarkera alla** | Markerar planens innehåll. | [Rita och tilldela](rita-och-tilldela.md#markera) |
| **Dölj texter** | Släcker namnen på kartan tillfälligt. | [Kartan](kartan.md) |
| **Rita yta / linje / punkt** (orange) | Ritar geometri som sedan får innehåll. | [Rita och tilldela](rita-och-tilldela.md) |
| **Importera geometri** (röd låda med pil ned) | Hämtar geometri från ett annat lager eller en fil. | [Rita och tilldela](rita-och-tilldela.md#importera-geometri) |
| **Markanvändning från Topografi 10** | Skapar befintlig markanvändning ur Lantmäteriets data. | [Hämta underlag](hamta-underlag.md) |
| **Hämta riksintressen** (karta med röd pil) | Hämtar riksintressen från Boverket. | [Hämta underlag](hamta-underlag.md#riksintressen) |
| **Tilldela innehåll** (lapp med muspekare) | Ger det du ritat innehåll ur ÖP-katalogen. | [Rita och tilldela](rita-och-tilldela.md) |
| **Kopiera innehåll** | Ger andra objekt samma innehåll. | [Rita och tilldela](rita-och-tilldela.md#kopiera-innehåll) |
| **Berör annat innehåll** | Kopplar ihop innehåll som hänger ihop. | [Rita och tilldela](rita-och-tilldela.md#berör-annat-innehåll) |

Knappar som inte går att använda just nu är **gråa**. Utan en öppen plan går bara *Ny* och *Öppna*. För att rita,
importera, tilldela, kopiera eller koppla innehåll måste du först klicka på **pennan**.

Har du flera planer öppna gäller knapparna den plan som det markerade lagret hör till, annars den översta planen i
lagerpanelen.

### Menyn

Samma kommandon finns under **Insticksprogram → Rita Översiktsplan**. Där finns också:

- **Ändring av översiktsplanen…** – se [Ändring av planen](andring.md),
- **Skapa kommunens ställningstagande för markerade riksintressen** – se [Hämta underlag](hamta-underlag.md),
- **Skapa arkivpaket…** och **Kontrollera arkivpaket…** – se [Arkivpaket](arkivpaket.md),
- **Inställningar för leverans till NGP…** – se [Leverera](leverera.md),
- **Spara stilar för GeoServer (SLD)…** – se [Kartan](kartan.md),
- **Spara alla redigeringar** – sparar utan att avsluta redigeringen,
- **Om Rita Översiktsplan…** – version, licens och länkar.

## Nästa steg

Fortsätt med [Planens uppgifter](planens-uppgifter.md).
