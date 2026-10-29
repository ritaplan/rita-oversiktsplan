# Hämta underlag

Pluginet kan hämta två slags underlag åt dig, så att du slipper rita dem:

- **befintlig mark- och vattenanvändning** ur Lantmäteriets Topografi 10 eller Marktäcke,
- **riksintressen** enligt 3 och 4 kap. miljöbalken ur Boverkets karttjänst.

## Markanvändning från Topografi 10

<!-- FILM: topografi-10 | Skapa befintlig markanvändning ur Topografi 10, ca 3 min -->

### Så gör du

1. **Ladda ner Topografi 10 för kommunen** från Lantmäteriets Geotorget. Det kräver ett konto där; pluginet kan inte
   hämta filen själv. Nedladdningen är en GeoPackage per tema, ofta i en zip-fil. Marktäcke går också.
2. Klicka på **Markanvändning från Topografi 10** i verktygsfältet eller menyn, och välj zip-filen eller en enskild
   GeoPackage.
3. Gå igenom tabellen. Den visar allt i filen som kan omklassas: skikt, geometri, objekttyp och vilken mark- och
   vattenanvändning det blir. Ändra där du vill. Ditt val sparas till nästa gång, och **Återställ förslaget** tar
   tillbaka pluginets förslag.
4. Klicka på **Skapa markanvändning**.
5. Spara med **disketten**.

<!-- BILD: topografi-dialog.png | Dialogen Markanvändning från Topografi 10 med omklassningstabellen -->

### Det här skapas

- **Ytor** med samma användning slås ihop och läggs i *Mark- och vattenanvändning (yta)*. Anläggningsområden
  (golfbanor, parker, skolor …), flygplatser och transformatorområden går före markslagen under dem.
- **Vägar, järnvägar, vattendrag och ledningar** slås ihop till sammanhängande linjer i *Mark- och vattenanvändning
  (linje)*.
- **Punkter**, till exempel vindkraftverk och järnvägsstationer, hamnar i *Mark- och vattenanvändning (punkt)*, om du
  väljer en användning för dem i tabellen.

Allt klipps mot planens avgränsning, förenklas med 5 m, får ingen utbyggnadsordning (det är befintlig användning) och
får preciseringen *Från Lantmäteriet (…)* med objekttyperna.

Kör du igen ersätts det som skapades förra gången. Det du ritat själv rörs inte.

### Pluginets förslag till omklassning

| Topografi 10 | Mark- och vattenanvändning |
|---|---|
| Sluten bebyggelse, Torg | Funktionsblandad bebyggelse |
| Hög och låg bebyggelse | Bostadsbebyggelse |
| Industri- och handelsbebyggelse, industriområden (gruva, täkt …) | Verksamheter |
| Öppen mark, Åker, Barr- och blandskog, Lövskog | Landsbygd |
| Fruktodling | Jordbruk |
| Kalfjäll, Fjällbjörkskog, Glaciär | Natur- och kulturlandskap |
| Hav, Sjö, Vattendragsyta, Anlagt vatten; Vattendrag (linje) | Vatten |
| Parkområde, Koloniområde, Begravningsplats | Grönområde |
| Övriga rekreationsområden och idrottsplatser | Friluftsliv och rekreation |
| Samhällsfunktion (skola, sjukhus …) | Service |
| Energiproduktion (område) | Energiproduktion |
| Avfallsanläggning, Transformatorområde, Kraftledning stam och region | Teknisk infrastruktur |
| Flygplatsområde | Luftfart |
| Motorväg, motortrafikled, mötesfri väg, landsväg, övergripande länk, huvudgata | Vägtrafik (linje) |
| Järnväg, Spårväg, Tunnelbana | Järnväg |
| Färjeled | Sjöfart (linje) |
| Rengärde | Renskötsel |
| Mindre vägar, gator, stigar, sankmark | Tas inte med |
| Byggnader och alla punkter | Föreslås inte; välj själv i tabellen |

> **Tänk på:** Topografi 10 visar vad som finns på marken, inte alltid vad den används till. Låg bebyggelse kan vara
> fritidshus och öppen mark kan vara en park. Se resultatet som en grund att rätta: ändra innehållstyp med *Tilldela
> innehåll* och rita det som saknas.

## Riksintressen

<!-- FILM: riksintressen | Hämta riksintressen och skapa kommunens ställningstagande, ca 3 min -->

### Hämta riksintressena

1. Klicka på **Hämta riksintressen** (kartan med röd pil) i verktygsfältet eller menyn.
2. Kryssa i vilka riksintressen du vill ha. Alla är ikryssade från början.
3. Välj område: **planens avgränsning** eller **kartans utsnitt**.
4. Kryssa i **Klipp riksintressena mot planens avgränsning** om du bara vill ha den del som ligger i planen.
5. Kryssa i **Lägg också in dem som kommunens ställningstagande** om du vill ha en kopia av varje riksintresse som
   kommunens ställningstagande (se nedan).
6. Klicka på **Hämta**.
7. Spara med **disketten**.

<!-- BILD: riksintressen-dialog.png | Dialogen Hämta riksintressen med riksintressena ikryssade -->

Riksintressena läggs i gruppen *Riksintressen enligt 3 och 4 kap. MB*. Varje objekt får myndighetens id (till exempel
Naturvårdsverkets riksintresse-id eller Trafikverkets identifieringskod), namnet och dagens datum som *hämtat datum*.
Hämtar du igen läggs bara nya riksintressen in.

> Boverket sammanställer myndigheternas underlag men kan inte garantera att det är aktuellt. Det är länsstyrelsen som
> ansvarar för planeringsunderlaget. Påverkansområden, till exempel buller- och hinderytor kring flygplatser, hämtas
> inte.

### Kommunens ställningstagande

De två riksintressegrupperna betyder olika saker:

| Grupp | Betyder |
|---|---|
| **Riksintressen enligt 3 och 4 kap. MB** | Statens anspråk. Underlag som du hämtar och inte ändrar i. |
| **Riksintresse, kommunens ställningstagande** | Kommunens svar: hur kommunen ser på riksintresset och tänker tillgodose det. Preciserar kommunen gränsen ritas den här. |

Så här arbetar du:

1. Hämta riksintressena (ovan).
2. Markera de riksintressen kommunen tar ställning till med **Markera**.
3. Välj **Insticksprogram → Rita Översiktsplan → Skapa kommunens ställningstagande för markerade riksintressen**.
   Varje markerat riksintresse kopieras med samma värde, namn, id och geometri, och kopian kopplas till riksintresset
   med *berör annat innehåll*. Ett riksintresse som redan har ett ställningstagande hoppas över.
4. Justera gränsen där kommunen preciserar den.
5. Skriv kommunens ställningstagande i planhandlingen under en rubrik med avsnittstypen *Ställningstagande*, och koppla
   avsnittet till objektet, se [Planhandlingen](planhandlingen.md).

Pågår en ändring av planen hör nya ställningstaganden till den, som annat nytt innehåll.

## Nästa steg

Fortsätt med [Kartan](kartan.md).
