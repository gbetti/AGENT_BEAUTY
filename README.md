# AGENT_BEAUTY

A ogni avvio crea **tre grafiche della stessa campagna e una presentazione PowerPoint**, usando packshot originale e logo IOMA salvati nel progetto, una sola headline italiana e la stessa CTA. Cerca prima online le notizie beauty degli ultimi sette giorni e sceglie il prodotto dal database locale.

## Avvio

Python 3.10+:

```sh
python3 -m pip install -r requirements.txt
python3 agent.py
```

Ogni esecuzione riuscita crea una cartella distinta `output/ioma-<data>-<id>/` contenente **soltanto**:

| File | Formato finale | Composizione |
| --- | --- | --- |
| `feed.png` | 1080×1350, 4:5 | Master 1024×1536, ritaglio centrale 1024×1280; nessun contenuto importante nel 6% alto/basso del master. Visual protagonista, headline in alto, CTA in basso, logo piccolo in un angolo. Testo entro il 20% della superficie. |
| `story.png` | 1080×1920, 9:16 | Stesso master verticale 1024×1536 adattato estendendo i bordi fotografici; testo e visual conservano le proporzioni. Safe zone: 13% superiore e 18% inferiore liberi; headline nel terzo superiore utile, visual centrale, CTA nella parte bassa utile. |
| `banner.png` | 300×250, 6:5 | Master 1536×1024, ritaglio centrale quasi quadrato. Solo logo, headline breve, visual prodotto e CTA come pulsante. Nessun sottotitolo. Bordo da 1 px su sfondo bianco. |
| `presentazione.pptx` | PowerPoint 16:9, 3 slide | Titolo del prodotto e packshot; trend settimanali con fonti cliccabili; anteprima Instagram o Facebook con il feed completo, caption e hashtag modificabili. |

I tre formati condividono colori, visual, headline e CTA. Tutti gli elementi importanti rispettano almeno il 5% di margine per lato; il testo usa al massimo due pesi della stessa famiglia tipografica. Le verifiche di safe zone, superficie del testo e leggibilità vengono eseguite prima dell'esportazione. Se un formato o il PowerPoint falliscono, la campagna incompleta viene rimossa e le campagne precedenti restano intatte.

## Presentazione PowerPoint

La prima slide presenta il titolo completo del prodotto, il packshot originale e la headline della campagna. La seconda mostra fino a tre segnali beauty osservati nelle notizie degli ultimi sette giorni: tema, titolo dell'articolo, data e fonte cliccabile. I riferimenti completi sono anche nelle note della slide. Se le fonti sono meno di tre, non vengono aggiunti trend inventati.

La terza slide simula un post Instagram: il PNG feed è incorporato per intero, senza tagli o deformazioni, accanto alla caption e agli hashtag. Titoli, caption e hashtag sono testi modificabili in PowerPoint. La caption usa il beneficio già registrato nel database; gli hashtag dipendono dal prodotto. Per una cornice Facebook:

```sh
python3 agent.py --product 'CC Gel' --platform facebook
```

La presentazione contiene immagini incorporate e si apre anche senza una connessione Internet. Il post è un'anteprima; l'agente non pubblica sui social.

Esempio verificato con CC Gel: [scarica il PowerPoint](https://github.com/gbetti/AGENT_BEAUTY/raw/refs/heads/main/posts/2026-10-07-campagna-powerpoint/presentazione.pptx). Anteprime delle slide: [prodotto](posts/2026-10-07-campagna-powerpoint/slide-1.png), [trend](posts/2026-10-07-campagna-powerpoint/slide-2.png), [post Instagram](posts/2026-10-07-campagna-powerpoint/slide-3.png).

## Testi esatti

Per rispettare la stessa headline anche nel banner, la headline ha **massimo quattro parole in tutti i formati**. È possibile fornire i testi esatti:

```sh
python3 agent.py --product 'CC Gel' \
  --headline 'Un incarnato luminoso' \
  --cta 'Scopri il prodotto'
```

I testi vengono stampati preservando lettere, accenti, punteggiatura e maiuscole: soltanto gli a capo possono cambiare con il layout. Non vengono abbreviati, tradotti o corretti automaticamente. Un testo troppo lungo o illeggibile nel banner produce un errore esplicito, senza una campagna parziale.

In assenza di override, `assets/campaign-copy.json` contiene headline italiane brevi derivate dalle descrizioni già fornite: «Un incarnato luminoso», «Nutre in profondità» e «Leviga le rughe», con CTA «Scopri il prodotto». Eventuali `editorial.headline_it` e `editorial.cta_it` nel database hanno precedenza su questi default.

```sh
python3 agent.py --database data/catalog.sqlite --output output
python3 agent.py --font /percorso/font.ttf
python3 -m unittest discover -s tests -v
```

Di default sono usati DejaVu Sans Bold e DejaVu Sans Regular. `--font` usa un solo font personalizzato per tutti i testi.

## Asset e database

I packshot originali sono in `assets/products/`, collegati al catalogo tramite `images` e `product_images`. La composizione preferisce i packshot ufficiali a 2000×2000 pixel; le precedenti versioni a 1000 pixel restano archiviate. Gli originali restano invariati: nella composizione viene rimosso soltanto il bianco esterno e corretta la frangia chiara del bordo. Il packshot resta separato dal master e viene ridimensionato una sola volta, direttamente alla dimensione di esportazione di ciascun formato. La confezione e le scritte non sono rigenerate con IA.

Il logo ufficiale è in `assets/brand/ioma-logo.png`. Il fondo fotografico di seta e pietra, creato con il generatore di immagini, è in `assets/backgrounds/ioma-campaign.png`. I master di lavoro vengono composti in memoria alle dimensioni indicate: non si rigenera uno sfondo remoto a ogni avvio e non servono API di generazione a pagamento. Il prodotto è ricomposto per il banner, senza ritagliare un post verticale con testi diventati minuscoli.

Il catalogo è `data/catalog.sqlite`; se manca viene inizializzato da `catalog_seed.sql` con CC Gel, Crème Sublime Revitalisante e Crème Généreuse Contour des Yeux. All'avvio l'agente non cerca prodotti né scarica foto dal sito IOMA. Prezzi, descrizioni e claim provengono dal database. Se una foto, il logo o lo sfondo mancano, termina con un errore esplicito.

La ricerca usa Google News RSS, verifica le date degli ultimi sette giorni e richiede un riferimento beauty nel titolo per escludere notizie estranee. Sono segnali dai titoli delle notizie, non misure di viralità Instagram/TikTok. Le fonti, i testi esatti, i percorsi e le verifiche geometriche restano nella tabella interna `generations` del database, insieme alla caption, agli hashtag e ai riferimenti del PowerPoint. Non esporta file caption o ZIP separati e non pubblica su Instagram o Facebook.

Servono HTTPS verso `news.google.com` e, per installare Pillow, `pypi.org` e `files.pythonhosted.org`.
