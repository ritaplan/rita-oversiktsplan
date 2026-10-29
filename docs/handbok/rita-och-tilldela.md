# Rita och tilldela innehåll

Arbetsgången är densamma som i Rita Detaljplan: **rita först, tilldela sedan.** Du ritar en yta, linje eller punkt och
ger den sedan innehåll ur ÖP-katalogen med verktyget *Tilldela innehåll*.

<!-- FILM: rita-och-tilldela | Rita en yta och ge den innehåll ur ÖP-katalogen, ca 3 min -->

## Rita och tilldela

1. Klicka på **pennan** (*Börja redigera*). Alla planens lager öppnas för redigering.
2. Klicka på **Rita yta**, **Rita linje** eller **Rita punkt** och rita som vanligt i QGIS.
   Inget formulär visas. Det du ritar hamnar i gruppen **Att tilldela** överst i planen och syns i orange.
3. Klicka på **Tilldela innehåll** och sedan på det du ritat.
4. Välj i dialogen:
   - **Grupp**, till exempel *Mark- och vattenanvändning* eller *Klimatrelaterade risker*. Bara grupper som kan ha den
     geometrin visas.
   - **Innehållstyp** ur ÖP-katalogen. Katalogens beskrivning visas under.
   - **Namn** och **Precisering** för just det här objektet.
   - För vissa grupper också **Kompletterande innehållstyp**, **Sambandsnivå** och **Utbyggnadsordning**.
5. Klicka på **Tilldela**. Objektet flyttas till rätt lager och ritas med gruppens symbol.
6. Fortsätt med nästa objekt. *Tilldela innehåll* är aktivt tills du väljer ett annat verktyg.

<!-- BILD: tilldela-innehall.png | Dialogen Tilldela innehåll med grupp och innehållstyp valda -->

### Ändra innehåll

Klicka med *Tilldela innehåll* på något som **redan har innehåll**. Samma dialog öppnas, och du kan byta grupp eller
innehållstyp. Objektet behåller sin identitet och sina övriga uppgifter.

Ligger flera objekt på varandra väljer du i en meny vilket du menar. Otilldelad geometri väljs alltid före innehåll
under den.

### Det här sätts automatiskt

| Uppgift | Värde |
|---|---|
| **Objektidentitet** | Ett unikt id (UUID). |
| **Versionen gäller från** | Tidpunkten då objektet fick innehåll. |
| **Illustrativa gränser** | Alltid *ja*, som specifikationen kräver. |
| **Planhändelse** och datum | Planens, eller den pågående ändringens. |
| **Vertikal avgränsning**, **under ersättning**, **datum påbörjat** och **presentationsskala** | Standardvärdena under [Planens uppgifter](planens-uppgifter.md). |

Ett enskilt objekt kan ändras i attributformuläret, med identifieringsverktyget eller i attributtabellen.

### Grupperna

| Grupp | Geometri |
|---|---|
| Plangeometri, Område | Bara ytor |
| Mark- och vattenanvändning | Yta, linje, punkt |
| Utvecklingsinriktning | Yta, linje, punkt |
| Riksintresse, kommunens ställningstagande | Yta, linje, punkt |
| Riksintressen enligt 3 och 4 kap. MB | Yta, linje, punkt |
| Miljökvalitetsnormer, Övriga förhållanden av väsentlig betydelse, Bostadsförsörjning, Mål, planer och program, LIS, Särskilt värdefull kulturmiljö, Klimatrelaterade risker, Avvikelse från regionplan, Mellankommunala och regionala intressen, Länsstyrelsens invändningar, Konsekvenser | Yta, linje, punkt |

> **Samma område med flera innehåll?** En ritad yta får ett innehåll. Ska samma område ha flera, till exempel
> markanvändning och ett riksintresse, ritar du ytan en gång till eller kopierar den.

## Importera geometri

Finns geometrin redan, till exempel i den gällande översiktsplanen, en utredning eller en DWG/DXF-fil, kan du hämta in
den i stället för att rita om den.

1. Klicka på **Importera geometri** (den röda lådan med pil nedåt).
2. Välj ett **lager** som redan finns i QGIS, eller klicka på **Lägg till datakälla…** för att öppna QGIS
   datakällshanterare (GeoPackage, Shape, DXF, databaser, WFS med flera).
3. Kryssa i **Bara markerade objekt** om du bara vill ta med det du markerat i källan.
4. Klicka på **Importera**.

<!-- BILD: importera-geometri.png | Dialogen Importera geometri med ett lager valt -->

Det här händer:

- Bara **geometrin** följer med, inga attribut.
- Ytor, linjer och punkter hamnar i *Otilldelad yta*, *Otilldelad linje* och *Otilldelad punkt* under **Att
  tilldela**. Ge dem sedan innehåll med *Tilldela innehåll*.
- Geometrin omvandlas till planens koordinatsystem, kurvor görs raka och höjdvärden tas bort. En multipunkt blir en
  punkt per del.
- Källan ändras inte.
- Ogiltiga geometrier, till exempel ytor som korsar sig själva, importeras ändå, men du får veta hur många de är.

Spara med **Avsluta redigering**, eller ångra med QGIS Ångra.

## Markera

**Markera** markerar planens innehåll och det som ska tilldelas, oavsett vilket lager som är valt i lagerpanelen.

- Klicka på ett objekt, eller dra en rektangel.
- Ligger flera objekt på varandra väljer du i en meny.
- **Ctrl-klick** eller **Skift-klick** lägger till i markeringen.
- **Högerklick** eller **Avmarkera alla** tar bort markeringen.

Objektets lager blir aktivt, så att QGIS egna verktyg (flytta, dela, brytpunkter) fungerar direkt.

> **Plangeometrin** täcker hela planen och kommer därför inte med när du klickar eller drar en rektangel inne i planen.
> Vill du ändra den klickar du på dess kant, eller drar en rektangel som går över kanten. Det gäller också *Tilldela
> innehåll*, *Kopiera innehåll* och *Berör annat innehåll*.

## Kopiera innehåll

**Kopiera innehåll** fungerar som *Kopiera bestämmelser* i Rita Detaljplan.

1. Klicka på verktyget.
2. Klicka på ett objekt med innehåll. Det visas i grönt.
3. Klicka på de objekt som ska få samma innehåll. Verktyget ligger kvar, så att du kan klicka på flera i rad.
4. Högerklicka eller tryck **Esc** för att välja ett nytt objekt att kopiera från.

Det som kopieras är grupp, innehållstyp, kompletterande innehållstyp, sambandsnivå, precisering och
utbyggnadsordning, men **inte namnet**. Målet kan vara otilldelad geometri, som då får innehållet, eller annat
innehåll, som byter typ men behåller sin identitet.

## Berör annat innehåll

**Berör annat innehåll** kopplar ihop innehåll som hänger ihop, till exempel en klimatrisk som berör ett område för
bostadsbebyggelse.

1. Klicka på verktyget.
2. Klicka på innehållet du utgår från. Det visas i grönt, och det som det redan berör visas i blått.
3. Klicka på det innehåll det berör. Klicka på samma innehåll igen för att ta bort kopplingen.
4. Högerklicka eller tryck **Esc** för att välja ett nytt innehåll att utgå från.

Kopplingen går åt **ett håll**: att klimatrisken berör bostadsområdet säger inget om bostadsområdet. Otilldelad geometri
kan inte kopplas. Kopplingarna sparas när du sparar redigeringen.

<!-- FILM: beror-annat-innehall | Koppla en klimatrisk till de områden den berör, ca 1 min -->

## Riksintressets id

För riksintressen, både kommunens ställningstagande och riksintressen enligt 3 och 4 kap. MB, har *Tilldela
innehåll* ett fält för **riksintressets id** hos den myndighet som pekat ut det. Det blir en extern referens i
exporten. Hämtar du riksintressena med pluginet fylls id:t i automatiskt, se [Hämta underlag](hamta-underlag.md).

## Spara

**Avsluta redigering** (disketten) frågar vad som ska hända med ändringarna:

- **Spara och avsluta**,
- **Förkasta och avsluta**, eller
- **Avbryt**.

Vill du spara mitt i arbetet utan att avsluta väljer du **Insticksprogram → Rita Översiktsplan → Spara alla
redigeringar**. QGIS egen knapp *Spara lagerändringar* fungerar också.

## Nästa steg

- [Hämta underlag](hamta-underlag.md) – befintlig markanvändning och riksintressen
- [Kartan](kartan.md) – hur planen visas
