# Planhandlingen

Översiktsplanens text, planhandlingen, skriver du i Word som vanligt. Med **Skapa bokmärken i planhandling** kopplar du
textavsnitten till planens innehåll, så som Boverkets ÖP-modell och Lantmäteriets specifikation beskriver.

- Varje avsnitt får ett Word-**bokmärke**.
- Bokmärkets namn sparas tillsammans med innehållet det gäller.
- Ett avsnitt kan gälla flera objekt, och ett objekt kan beskrivas i flera avsnitt.

**Originaldokumentet ändras aldrig.**

<!-- FILM: planhandlingen | Skapa bokmärken och koppla avsnitten till planens innehåll, ca 4 min -->

## Börja med mallen

[`exempel/Planhandling_mall_ÖP-katalogen_2.2.docx`](../../exempel/Planhandling_mall_ÖP-katalogen_2.2.docx) är en
planhandling med en rubrik för allt innehåll i ÖP-katalogen, katalogens vägledning i grått och plats för kommunens
text. Ta bort de rubriker planen inte behöver. Rubrikerna är valda så att programmet föreslår rätt avsnittstyp.

## Öppna programmet

Klicka på **Skapa bokmärken i planhandling** (dokumentet med grön etikett). Programmet öppnas i ett eget fönster med
fyra steg i toppfältet.

Fönstret låser inte QGIS: du kan markera och rita i kartan medan det är öppet. Klickar du på knappen igen läses planen
om, till exempel efter att du ritat mer.

## De fyra stegen

### 1. Filer

Planen är redan vald. Välj planhandlingen (`.docx`) eller dra den till fönstret. **Öppna senaste** öppnar dokumentet
du arbetade med senast i den här planen.

### 2. Avsnitt

Varje **rubrik** (formatmallarna Rubrik 1, 2 och 3) blir ett avsnitt som räcker till nästa rubrik. Texten visas som ett
papper, med ett kort per avsnitt.

Programmet föreslår en **avsnittstyp** ur ÖP-katalogen utifrån rubriken och förklarar varför under *Varför*. En rubrik
som *Ställningstaganden* blir Ställningstagande, och underrubrikerna ärver typen. Annars blir det Beskrivning.

Granska varje förslag:

- byt typ i listan,
- klicka på **Godkänn** (eller tryck Enter), eller
- klicka på **Inget bokmärke** för text som inte ska ha bokmärke.

Rubriker utan egen text får inget bokmärke från början. **J** och **K** bläddrar mellan avsnitten.

<!-- BILD: bokmarken-steg-2.png | Steg 2: avsnitten med föreslagna avsnittstyper -->

### 3. Koppling

Välj ett avsnitt till vänster. I mitten syns texten och det avsnittet är kopplat till. Koppla genom att

- **klicka på innehållet i kartan** till höger (klicka igen för att ta bort kopplingen),
- **kryssa i listan** under kartan, som också visar hur många avsnitt varje objekt redan är kopplat till,
- klicka på **Hämta markerat i QGIS** för det som är markerat i QGIS karta,
- klicka på **Gäller hela planen**, till exempel för syftet och sammanfattningen,
- klicka på **Nytt innehåll utan geometri…** för innehåll som bara beskrivs i text, till exempel bostadsförsörjning
  eller planens konsekvenser.

I kartan zoomar du med rullhjulet, flyttar genom att dra och ser allt genom att dubbelklicka. **Visa i QGIS** markerar
avsnittets innehåll i QGIS karta, och krysset på en koppling tar bort den.

> Mark- och vattenanvändning måste ha en geometri enligt föreskrifterna, och kan därför inte läggas in utan geometri.

<!-- BILD: bokmarken-steg-3.png | Steg 3: ett avsnitt kopplat till innehåll i kartan -->

### 4. Kontroll och spara

Kontrollen visar

- **fel**: koppling till något som inte längre finns i planen,
- **varningar**: avsnitt som inte är granskade, och mark- och vattenanvändning som inte är kopplad till något avsnitt,
- **information**.

**Gå till** visar var. Till höger syns raderna som sparas i planen.

Klicka på **Spara…** vid *Kopia med bokmärken och kopplingar*. Det här sparas:

| Vad | Var |
|---|---|
| **Kopia med bokmärken** | *namn*_bokmarken.docx bredvid originalet. |
| **Kopplingarna** | Direkt i planens dokumenttabeller. |
| **Webbversion** (om rutan är ikryssad, som standard) | *namn*_bokmarken.html bredvid kopian. |
| **Översikt över kopplingarna** (valfritt) | En CSV-fil för Excel. |

## Webbversionen

Webbversionen är texten med rubriker, listor, tabeller och länkar, där varje avsnitt har sitt bokmärke som adress, till
exempel *namn*_bokmarken.html#op_3f2a…. Dokumentets titel blir sidans huvudrubrik. Bilder visas som sin alternativtext.

En webbkarta kan länka från planens innehåll till texten: raderna i `dokumentavsnitt` säger vilket bokmärke som hör
till vilket objekt, och bokmärket är adressen till avsnittet i webbversionen.

## Arbeta vidare genom skedena

1. Skapa bokmärken första gången när **samrådsunderlaget** är klart.
2. Fortsätt sedan att skriva i **kopian med bokmärken**.
3. Öppna kopian igen inför **granskning** och **antagande**. Avsnitten behåller sina bokmärken, så bara nya rubriker
   och ändrat innehåll behöver ses över. Webbversionen görs om när du sparar.

Öppnar du originalet, utan bokmärken, i en plan som redan har bokmärken varnar programmet och erbjuder att öppna kopian
i stället. Stänger du fönstret med ändringar som inte är sparade frågar programmet först.

> Innehåll utan geometri syns inte i QGIS karta, men finns i gruppens ytlager (i attributtabellen) och i listan i
> programmet.

## Nästa steg

Fortsätt med [Leverera planen](leverera.md).
