# Leverera planen

Klicka på **Leverans och export** (lådan med pil upp). Dialogen kontrollerar planen och har tre val:

- **Leverera till NGP** – skickar planen till Nationella geodataplattformen (knappen *Leverera*).
- **Spara som JSON-fil** – sparar planen i Lantmäteriets format (knappen *Spara fil…*).
- **Skapa arkivpaket** – se [Arkivpaket](arkivpaket.md) (knappen *Skapa arkivpaket…*).

Välj ett av dem och klicka på knappen längst ned, som byter text efter valet. När det valda är gjort stängs dialogen.

<!-- BILD: leverans-och-export.png | Dialogen Leverans och export med kontrollen överst och de tre valen -->

## Kontrollen

Överst, i en **blå ruta**, står vad kontrollen hittade:

- **Fel** – det som Lantmäteriets format kräver men som saknas, till exempel planhändelse eller en innehållstyp som
  inte finns i katalogen.
- **Varningar** – sådant som är värt att se över.

**Dubbelklicka** på en anmärkning för att markera och zooma till objektet.

En anmärkning som kommer från en av Lantmäteriets regler börjar med regelns id, till exempel `[OP-JSON-042]`, så att du
kan slå upp den. Några exempel på vad som kontrolleras:

- planen har minst ett **underlag**,
- en antagen plan har underlagen *Länsstyrelsens granskningsyttrande* och *Miljökonsekvensbeskrivning*, och ett
  beslut,
- *Plangeometri* och *Område* har geometri,
- linjer och ytkanter korsar inte sig själva och har inga **spikar** (vinklar på 12° eller mindre),
- planhandlingen är ett Word-dokument.

> Kontrollen är pluginets tolkning av Lantmäteriets specifikation (test 4). Lantmäteriets egen validering i NGP kan
> hitta mer.

## Spara som JSON-fil

Filen följer Lantmäteriets format **Översiktsplan 2.0**, det format som används vid leverans till NGP. Den innehåller

- **planen**: kommun, titel, planhändelse, datum, underlag och kopplingar till planhandlingen,
- **besluten**: antagandebeslutet och ändringarnas beslut,
- **allt innehåll**: innehållstyp och övriga uppgifter, geometrin i planens koordinatsystem och kopplingarna till
  planhandlingens bokmärken.

Värden ur ÖP-katalogen skrivs med katalogens id:n. Otilldelad geometri följer inte med, men ändringar som inte sparats
gör det.

Du kan spara filen även om kontrollen hittat fel, men då följer filen inte formatet.

## Leverera till NGP

> **Kräver producentbehörighet** för översiktsplan hos Lantmäteriet. Leveransen är **inte provad mot Lantmäteriets
> riktiga miljö**, och specifikationen är i testversion. Prova i verifieringsmiljön först.

<!-- FILM: leverera-ngp | Ställ in leveransen och leverera till verifieringsmiljön, ca 3 min -->

### Ställ in leveransen första gången

1. Klicka på **Inställningar…** i leveransrutan, eller välj **Insticksprogram → Rita Översiktsplan → Inställningar för
   leverans till NGP…**.
2. Välj **miljö**: Lantmäteriets **verifieringsmiljö**, där man provar, eller **produktion**.
3. Välj en **autentiseringskonfiguration** i QGIS med nyckeln och hemligheten från Lantmäteriets API-portal.
   Uppgifterna sparas i QGIS autentiseringsdatabas, inte av pluginet.

Saknas inställningarna, eller kommunen i planens uppgifter, går leveransen inte att välja och rutan säger vad som
saknas. Då är *Spara som JSON-fil* förvalt.

### Leverera

1. Välj **Leverera till NGP**. Rutan visar vart planen skickas och hur många fel kontrollen hittade.
2. Levererar du till **produktion** måste du kryssa i *Jag förstår att en godkänd plan publiceras i
   produktionsmiljön*.
3. Klicka på **Leverera**.

Leveransen körs i bakgrunden. När Lantmäteriet validerat planen visas resultatet med **valideringsrapporten**, med
Lantmäteriets egna texter.

**Får planen valideringsfel** rättar du dem och levererar igen. Planen skickas då på samma mottagning hos
Lantmäteriet.

## Nästa steg

Fortsätt med [Arkivpaket](arkivpaket.md).
