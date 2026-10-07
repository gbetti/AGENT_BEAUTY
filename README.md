# AGENT_BEAUTY

A ogni avvio cerca online le notizie beauty degli ultimi sette giorni, sceglie un prodotto dal database e costruisce un concept coerente con i trend. Crea **tre grafiche della stessa campagna e un PowerPoint con tutti i mockup**, usando packshot originale e logo IOMA. Ambientazione, headline e obiettivo del post cambiano tra esecuzioni; la stessa campagna mantiene visual, headline e CTA coerenti nei tre formati.

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
| `presentazione.pptx` | PowerPoint 16:9, 6 slide | Prodotto e concept; trend con fonti; feed nella cornice Instagram; feed nella cornice Facebook; Story/Reel nei due telefoni; banner dentro una pagina web. Caption e hashtag modificabili. |

I tre formati condividono colori, visual, headline e CTA. Tutti gli elementi importanti rispettano almeno il 5% di margine per lato; il testo usa al massimo due pesi della stessa famiglia tipografica. Le verifiche di safe zone, superficie del testo e leggibilità vengono eseguite prima dell'esportazione. Se un formato o il PowerPoint falliscono, la campagna incompleta viene rimossa e le campagne precedenti restano intatte.

## Presentazione PowerPoint

La prima slide presenta il titolo completo del prodotto, la creatività scelta, la headline e l'obiettivo del post. La seconda mostra fino a tre segnali beauty osservati nelle notizie degli ultimi sette giorni: tema, titolo dell'articolo, data e fonte cliccabile. La fonte che ha ispirato il concept ha priorità. I riferimenti completi sono anche nelle note della slide. Se le fonti sono meno di tre, non vengono aggiunti trend inventati.

Le slide 3 e 4 mostrano il feed 4:5 nelle cornici Instagram e Facebook, con caption e hashtag. La slide 5 incorpora la Story/Reel 9:16 in due telefoni, con controlli delle app confinati alle safe zone. La slide 6 inserisce il banner 300×250 nella colonna pubblicitaria di una pagina web simulata, a dimensione naturale per mantenerlo leggibile. Tutti i PNG sono incorporati per intero, senza tagli o deformazioni; la presentazione conserva i file originali, e titoli, caption e hashtag restano modificabili. Entrambi i social sono sempre presenti; `--platform` sceglie soltanto quale mostrare per primo:

```sh
python3 agent.py --product 'CC Gel' --platform facebook
```

La presentazione contiene immagini incorporate e si apre anche senza una connessione Internet. Il post è un'anteprima; l'agente non pubblica sui social.

Due esecuzioni verificate con CC Gel: [PowerPoint della variante 1](https://github.com/gbetti/AGENT_BEAUTY/raw/refs/heads/main/posts/2026-10-07-campagne-trend/variante-1/presentazione.pptx), [variante 2](https://github.com/gbetti/AGENT_BEAUTY/raw/refs/heads/main/posts/2026-10-07-campagne-trend/variante-2/presentazione.pptx) e [confronto delle grafiche](posts/2026-10-07-campagne-trend/confronto.png).

## Trend, messaggio e ambientazione

`creative.py` collega le notizie a un angolo editoriale compatibile con il prodotto: incarnato e glow, rituali ispirati alla K-beauty, idratazione o cura anti-age. Il trend ispira il setting e la caption; benefici e claim restano quelli già documentati nel catalogo. Un riferimento alla K-beauty è un'ispirazione per il rituale, non un'affermazione sull'origine o sugli ingredienti IOMA.

La libreria in `assets/backgrounds/scenes.json` contiene sette ambientazioni fotografiche: vanity nella luce del mattino, vetro perlato, spa con acqua, studio verde giada, seta viola serale, giardino di pietra e seta color moka. Sono state create con il generatore di immagini e salvate nel progetto. L'agente seleziona una scena compatibile con il messaggio ed esclude quella dell'ultima campagna registrata in SQLite. Nello stesso catalogo, due avvii consecutivi cambiano setting; la libreria può essere riutilizzata nelle esecuzioni successive. Non serve una chiave API per l'esecuzione ordinaria.

L'obiettivo alterna commenti, salvataggi e clic. Le headline usano domande o inviti brevi, come «Team incarnato naturale?», «Rughe? Parti dal rituale» e «Pelle soda? Inizia qui». La caption collega il trend al beneficio documentato e propone una sola azione principale. L'obiettivo è un'ipotesi editoriale: l'agente non inventa risultati, numeri di engagement, scarsità o promesse di efficacia.

Ogni scena include il punto d'appoggio del prodotto. Il ritaglio del banner e la posizione del packshot seguono quel riferimento. Il colore del testo si adatta alla luce del setting; quando serve, una velatura locale rende leggibili headline e logo senza oscurare l'intera fotografia.

## Testi esatti

Per rispettare la stessa headline anche nel banner, la headline ha **massimo quattro parole in tutti i formati**. È possibile fornire i testi esatti:

```sh
python3 agent.py --product 'CC Gel' \
  --headline 'Un incarnato luminoso' \
  --cta 'Scopri il prodotto'
```

I testi vengono stampati preservando lettere, accenti, punteggiatura e maiuscole: soltanto gli a capo possono cambiare con il layout. Non vengono abbreviati, tradotti o corretti automaticamente. Un testo troppo lungo o illeggibile nel banner produce un errore esplicito, senza una campagna parziale.

In assenza di override, l'agente varia la headline tra gli hook coerenti con il prodotto, evitando quello dell'ultima campagna dello stesso prodotto. Eventuali `editorial.headline_it` e `editorial.cta_it` nel database hanno precedenza; gli override della riga di comando hanno priorità. `assets/campaign-copy.json` conserva i testi di base per la composizione manuale.

```sh
python3 agent.py --database data/catalog.sqlite --output output
python3 agent.py --font /percorso/font.ttf
python3 -m unittest discover -s tests -v
```

Di default sono usati DejaVu Sans Bold e DejaVu Sans Regular. `--font` usa un solo font personalizzato per tutti i testi.

## Asset e database

I packshot originali sono in `assets/products/`, collegati al catalogo tramite `images` e `product_images`. La composizione preferisce i packshot ufficiali a 2000×2000 pixel; le precedenti versioni a 1000 pixel restano archiviate. Gli originali restano invariati: nella composizione viene rimosso soltanto il bianco esterno e corretta la frangia chiara del bordo. Il packshot resta separato dal master e viene ridimensionato una sola volta, direttamente alla dimensione di esportazione di ciascun formato. La confezione e le scritte non sono rigenerate con IA.

Il logo ufficiale è in `assets/brand/ioma-logo.png`. Le fotografie dei setting sono in `assets/backgrounds/` e il manifest ne registra dimensioni e SHA-256. I master sono composti in memoria alle dimensioni indicate; il prodotto è ricomposto per il banner, senza ritagliare un post verticale con testi diventati minuscoli.

Il catalogo è `data/catalog.sqlite`; se manca viene inizializzato da `catalog_seed.sql` con CC Gel, Crème Sublime Revitalisante e Crème Généreuse Contour des Yeux. All'avvio l'agente non cerca prodotti né scarica foto dal sito IOMA. Prezzi, descrizioni e claim provengono dal database. Se una foto, il logo o lo sfondo mancano, termina con un errore esplicito.

La ricerca usa Google News RSS, verifica le date degli ultimi sette giorni e richiede un riferimento beauty nel titolo per escludere notizie estranee. Sono segnali dai titoli delle notizie, non misure di viralità Instagram/TikTok. Le fonti, il concept, il setting, l'obiettivo, i testi esatti, i percorsi e le verifiche geometriche restano nella tabella interna `generations` del database, insieme alla caption, agli hashtag e ai mockup del PowerPoint. Non esporta file caption o ZIP separati e non pubblica su Instagram o Facebook.

Servono HTTPS verso `news.google.com` e, per installare le dipendenze, `pypi.org` e `files.pythonhosted.org`.
