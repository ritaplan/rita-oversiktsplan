# Bilder och filmer i handboken

Det här är en arbetsbeskrivning för dig som skriver handboken. Den visas inte på ritaplan.xyz.

Handboken skrivs som Markdown i `docs/`. Samma filer visas på GitHub och på
[ritaplan.xyz/handbok-op.html](https://ritaplan.xyz/handbok-op.html), som hämtar dem direkt från GitHub. Ändrar du i `docs/`
och pushar till `main` syns ändringen på webbplatsen inom en kvart.

## Platshållare

Där en bild eller film ska in finns en kommentar. Den syns inte, varken på GitHub eller på webbplatsen:

```
<!-- BILD: ny-plan-dialog.png | Dialogen Ny översiktsplan med kommun och titel ifyllda -->
<!-- FILM: kom-igang | Från installation till ett ritat planområde, ca 3 min -->
```

Texten efter `|` beskriver vad bilden eller filmen ska visa. Lista alla platshållare som återstår med:

```bash
grep -rn "<!-- \(BILD\|FILM\):" docs/
```

## Lägga in en skärmbild

1. Ta skärmbilden i QGIS och spara den som PNG i `docs/images/handbok/`, med namnet från platshållaren.
2. Byt ut kommentaren mot en vanlig bildlänk. Skriv en alternativtext som beskriver vad bilden visar:

   ```markdown
   ![Dialogen Ny översiktsplan med kommun och titel ifyllda](../images/handbok/ny-plan-dialog.png)
   ```

Tips:

- Beskär bilden till det som är viktigt, till exempel bara dialogen.
- Bredd omkring 1200–1600 pixlar räcker. Komprimera gärna med till exempel [Squoosh](https://squoosh.app/).
- Använd en exempelplan utan känsliga uppgifter.

## Lägga in en film

Filmerna ligger på ritaplan.xyz, inte i repot. Lägg varje film och en stillbild (poster) i mappen `film/oversiktsplan/` på
webbplatsen:

```
ritaplan.xyz/film/oversiktsplan/kom-igang.mp4     filmen (H.264, MP4)
ritaplan.xyz/film/oversiktsplan/kom-igang.jpg     stillbild som visas innan filmen startar
ritaplan.xyz/film/oversiktsplan/kom-igang.vtt     undertexter (frivilligt men rekommenderat)
```

Byt sedan ut kommentaren mot en bild som länkar till filmen:

```markdown
[![Film: Från installation till en ny översiktsplan (3 min)](https://ritaplan.xyz/film/oversiktsplan/kom-igang.jpg)](https://ritaplan.xyz/film/oversiktsplan/kom-igang.mp4)
```

- **På GitHub** syns stillbilden. Ett klick öppnar filmen.
- **På ritaplan.xyz** byts länken automatiskt ut mot en spelare (video.js). Finns en `.vtt`-fil med samma namn visas
  den som svenska undertexter.

Regeln är att en länk till en `.mp4`- eller `.webm`-fil på ritaplan.xyz blir en spelare.

Tips:

- Spela in i 1920 × 1080 och håll filmerna korta, helst under 3 minuter. Hellre flera korta än en lång.
- Exportera som MP4 (H.264) så fungerar filmen i alla webbläsare.
- Undertexter hjälper den som inte kan lyssna och gör filmen sökbar.

## Platshållare som återstår

| Sida | Bilder | Filmer |
|---|---|---|
| [Startsidan](../anvandning.md) | | oversikt |
| [Kom igång](kom-igang.md) | installera-pluginkalla, ny-plan-dialog, verktygsfalt-oversikt | kom-igang |
| [Planens uppgifter](planens-uppgifter.md) | planens-uppgifter, utbyggnadsordning-karta | planens-uppgifter |
| [Rita och tilldela](rita-och-tilldela.md) | tilldela-innehall, importera-geometri | rita-och-tilldela, beror-annat-innehall |
| [Hämta underlag](hamta-underlag.md) | topografi-dialog, riksintressen-dialog | topografi-10, riksintressen |
| [Kartan](kartan.md) | karta-oversikt | |
| [Planhandlingen](planhandlingen.md) | bokmarken-steg-2, bokmarken-steg-3 | planhandlingen |
| [Ändring av planen](andring.md) | andring-dialog | andring |
| [Leverera planen](leverera.md) | leverans-och-export | leverera-ngp |
| [Arkivpaket](arkivpaket.md) | arkivpaket-dialog | arkivpaket |
| [Lagring](lagring.md) | | checka-ut-in |

## Skrivregler

- Skriv **du** till läsaren och använd aktiv form: "Klicka på …", inte "Det klickas på …".
- Använd **numrerade steg** för det man gör i ordning och **punktlistor** för det som inte har en ordning.
- Skriv knappar, menyer och fält i **fetstil** och med samma namn som i pluginet: **Planens uppgifter**,
  **Insticksprogram → Rita Översiktsplan → Ny översiktsplan…**.
- Använd citatblock (`>`) för viktiga varningar och tips.
- Varje sida slutar med en länk till nästa steg.
- Nya sidor läggs i `docs/handbok/` och i innehållsförteckningen i `docs/anvandning.md`. Webbplatsen bygger sin meny
  från den listan.
