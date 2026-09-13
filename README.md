# LLM Overlay

En genomskinlig ram som du placerar över valfri del av skärmen, fångar som en
skärmdump och ställer frågor om till Google Gemini — utan att lämna appen du
jobbar i.

![Windows](https://img.shields.io/badge/plattform-Windows-blue)

## Kom igång

1. **Ladda ner projektet**

   ```powershell
   git clone https://github.com/AxelFredriksson/AI-overlay.git
   cd AI-overlay
   ```

   (Eller ladda ner som ZIP via *Code → Download ZIP* och packa upp.)

2. **Dubbelklicka på `run.bat`**

   Första gången skapas en virtuell miljö och beroendena installeras — räkna med
   några minuter. Därefter startar programmet direkt varje gång.

   Saknas Python erbjuder `run.bat` att installera det åt dig via winget, eller
   hänvisar till [python.org](https://www.python.org/downloads/). Kräver
   Python 3.10 eller senare.

3. **Klistra in din API-nyckel**

   Första gången öppnas inställningarna. Hämta en gratis nyckel på
   [aistudio.google.com/apikey](https://aistudio.google.com/apikey) och klistra
   in den under *Modell & nyckel*. Nyckeln sparas i en lokal `.env`-fil som
   aldrig hamnar i git.

## Användning

**Ctrl+Shift+O** visar och döljer ramen var du än befinner dig. Programmet
ligger kvar i systemfältet när ramen är dold.

- **Dra i kanten** för att flytta ramen, **dra i ett hörn** för att ändra
  storlek. Måtten visas medan du drar.
- Ramens mitt är klickgenomskinlig — du kan jobba som vanligt i fönstret bakom.
- **Fråga** fångar det som ligger innanför ramen och öppnar panelen med
  skärmdumpen bifogad.
- **Chatt** öppnar panelen utan skärmdump, för en vanlig textfråga.
- **Inställningar** öppnar inställningsfönstret, **Dölj** gömmer overlayn.

I panelen:

- Skriv en fråga och tryck Enter. Svaret strömmas in medan det genereras, och du
  kan **Stoppa** mitt i eller be om **Svara igen**.
- **Kopiera** kopierar svaret; kodblock har en egen kopieringsknapp.
- Klicka på sessionsnamnet uppe till vänster för att bläddra i **historiken**,
  med sökfält och miniatyrer.
- **+** startar en ny session och sol-/månikonen växlar tema direkt.
- Kryss-ikonen på skärmdumpen tar bort den som kontext, om frågan inte handlar
  om skärmen.

## Inställningar

| Sida | Innehåller |
| --- | --- |
| Beteende | Auto-skicka och standardfråga, detaljnivå, resoneringsnivå, tema, spara historik |
| Modell & nyckel | API-nyckel och modellval (egna modellnamn går bra) |
| Genvägar | Den globala hotkeyn |
| Overlay | Ramens standardstorlek, linjetjocklek, grip- och hörnzon samt färg |
| Historik | Var historiken sparas, och en genväg till mappen |

Temat följer Windows som standard, men kan låsas till ljust eller mörkt.

## Filer som skapas lokalt

Inget av det här hamnar i git:

- `.env` — din `GEMINI_API_KEY`.
- `settings.json` — alla inställningar ovan.
- `history/` — skärmdumpar (`images/`) och en logg (`history.jsonl`) med
  fråga och svar per session, om historik är påslaget.
- `.venv/` — den virtuella miljön som `run.bat` skapar.

## Felsökning

- **Inget händer när jag kör run.bat** — starta från en terminal med
  `.venv\Scripts\python main.py` så visas eventuella felmeddelanden.
- **"Modellen är inte tillgänglig längre"** — Google har fasat ut modellen. Välj
  en annan under *Modell & nyckel*.
- **Hotkeyn fungerar inte** — kombinationen kan vara upptagen av ett annat
  program. Byt under *Genvägar*.

## För utvecklare

Gränssnittet är delat i två lager. Ramen, verktygsfältet, den globala hotkeyn
och skärmdumpen är native Qt (PySide6), medan panelen och inställningarna är
HTML/CSS/JS i en `QWebEngineView` som pratar med Python över `QWebChannel`.
Designens färger definieras en gång i `theme.py` och skickas in i webbsidorna
som CSS-variabler.

```
main.py                     startar programmet
llm_overlay/
    app.py                  kopplar ihop overlay, verktygsfält, panel och systemfält
    config.py               inställningar och API-nyckel
    theme.py                färgpalett, tema och systemläge
    capture.py              skärmdump av ramens område
    hotkey.py               global hotkey
    history.py              sparade sessioner
    markdown_lite.py        markdown till HTML för svaren
    worker.py               strömmande anrop i bakgrundstråd
    llm/                    Gemini-klienten bakom ett litet gränssnitt
    ui/
        overlay_window.py   ramen (flytta, ändra storlek, klickgenomskinlighet)
        overlay_toolbar.py  verktygsfältet ovanför ramen
        panel_window.py     chattpanelen: fönster + brygga mot webbsidan
        settings_dialog.py  inställningsfönstret: dialog + brygga
        webview.py          uppsättning av webbvy och kanal
        web/                panelens och inställningarnas gränssnitt
```

`settings.json`, `.env` och `history/` skapas i projektroten, inte i paketet.

Kör direkt från källkoden med `.venv\Scripts\python main.py`.
