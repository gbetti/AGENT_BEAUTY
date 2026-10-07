# AGENT_BEAUTY

Genera **una sola immagine Instagram finale** con packshot originale, claim sovrapposto e logo IOMA, su uno sfondo fotografico. Usa i prodotti e le foto del database locale. A ogni avvio ricerca online notizie beauty degli ultimi sette giorni per scegliere il tema e il prodotto.

## Avvio

Python 3.10+:

```sh
python3 -m pip install -r requirements.txt
python3 agent.py
```

Il risultato è un solo file `output/ioma-<data>-<id>.png`, di 1080×1350 pixel. Il programma stampa soltanto il percorso dell'immagine. Non esporta caption, ZIP o file di fonti. Ogni avvio conserva i post precedenti e genera un nuovo file.

```sh
python3 agent.py --product 'CC Gel'
python3 agent.py --database data/catalog.sqlite --output output
python3 agent.py --font /percorso/font.ttf
python3 -m unittest discover -s tests -v
```

## Composizione dell'immagine

I packshot reali sono in `assets/products/`, collegati al catalogo tramite le tabelle `images` e `product_images`. Sono le foto ufficiali delle confezioni mostrate dall'utente, recuperate una volta dal sito IOMA. Gli originali rimangono conservati senza modifiche. Nell'impaginazione viene rimosso soltanto il bianco esterno collegato ai bordi e la confezione viene ridimensionata, preservando i suoi pixel e le scritte. La confezione non viene rigenerata con IA.

Il logo ufficiale è salvato in `assets/brand/ioma-logo.png`: la composizione usa la sagoma originale nella variante bianca. Lo sfondo fotografico di seta e pietra è stato creato con il generatore di immagini ed è conservato in `assets/backgrounds/ioma-campaign.png`. A ogni avvio l'agente compone questi asset locali con il claim presente nella scheda prodotto. Non richiede API di generazione a pagamento durante l'avvio.

Il logo e il claim sono sovrapposti alla stessa immagine fotografica: nessuna scheda bianca separata attorno al packshot. Se manca una foto, il logo o lo sfondo, l'agente termina con un errore esplicito.

## Database e ricerca

Il catalogo è `data/catalog.sqlite`. Se manca viene inizializzato da `catalog_seed.sql` con CC Gel, Crème Sublime Revitalisante e Crème Généreuse Contour des Yeux. Le foto e i loro collegamenti sono disponibili anche nei nuovi cloni; un catalogo esistente viene conservato.

L'agente non cerca né scarica prodotti dal sito IOMA all'avvio. Prezzi, descrizioni e claim provengono dal database. Per aggiungere un prodotto servono una foto locale collegata e i campi `editorial.theme` (`glow` o `renew`) e `editorial.claim_it` nel JSON della scheda.

La ricerca usa Google News RSS con filtro e verifica delle date degli ultimi sette giorni. Si tratta di segnali dai titoli delle notizie, non di misure di viralità Instagram/TikTok. Se la ricerca fallisce non vengono inventati trend e non viene esportato un post. Le fonti e la scelta del prodotto restano nella tabella interna `generations` del database, senza file aggiuntivi per l'utente.

Servono HTTPS verso `news.google.com` e, per installare Pillow, `pypi.org` e `files.pythonhosted.org`. Serve inoltre un font TrueType: di default `DejaVuSerif.ttf`; usare `--font` se assente. Il programma crea l'immagine, senza pubblicare automaticamente su Instagram.
