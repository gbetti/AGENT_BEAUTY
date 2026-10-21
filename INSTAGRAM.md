# Pubblicare il feed su Instagram

L’agente pubblica una singola immagine con la sua caption attraverso **Instagram
API with Instagram Login**. Il post preparato è quello francese della Crème
Généreuse Contour des Yeux, destinato a **@gb77ita**. L’autorizzazione del profilo
non è ancora configurata e il post non è stato inviato a Instagram.

## Collegare @gb77ita una volta

1. Il profilo deve essere **Business o Creator**. Se è personale, passa a un
   account professionale nelle impostazioni Instagram. Questo tipo di API non
   richiede di collegare una Pagina Facebook.
2. In [Meta for Developers](https://developers.facebook.com/apps/), crea o apri
   un’app con **Instagram API with Instagram Login**. Nella configurazione API
   aggiungi @gb77ita e autorizza l’account nella sezione di generazione dei token.
   Per un account che gestisci, segui il percorso di test/ruoli dell’app indicato
   dalla dashboard. Per collegare account di altri utenti possono servire App
   Review e accesso avanzato. Richiedi soltanto `instagram_business_basic` e
   `instagram_business_content_publish` per questa funzione.
3. Salva il token utente Instagram nel segreto **`INSTAGRAM_ACCESS_TOKEN`**
   dell’ambiente che esegue il progetto. Non usare la password Instagram e non
   incollare il token in chat, nei file pubblici o nella riga di comando.
   La versione API predefinita è `v26.0`; `INSTAGRAM_API_VERSION` consente di
   aggiornarla. Un token Facebook Login non è intercambiabile con questo token.

Su un terminale Bash locale puoi inserire il token senza mostrarlo né scriverlo
nella cronologia (vale solo per questa sessione):

```bash
read -r -s -p 'Token Instagram: ' INSTAGRAM_ACCESS_TOKEN
export INSTAGRAM_ACCESS_TOKEN
python -m agents.publisher connect --username gb77ita
```

`connect` legge il profilo autenticato, controlla nome, ID e tipo di account.
Non pubblica nulla e non stampa il token. Un nome profilo diverso da @gb77ita
blocca il processo. Il token scade e può essere revocato: rinnova l’autorizzazione
quando necessario. La gestione OAuth di più clienti e il rinnovo automatico
non sono inclusi in questa integrazione per un singolo account.

Riferimenti ufficiali: [avvio e generazione del token](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started),
[permessi Instagram Login](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login),
[pubblicazione](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/).

## Il post francese già pronto

Il manifest è [`publishing/2026-10-17-contour-yeux-fr/post.json`](publishing/2026-10-17-contour-yeux-fr/post.json).
Contiene profilo, lingua, caption, riferimento al PNG revisionato e hash dei file.
La copia [`feed.jpg`](publishing/2026-10-17-contour-yeux-fr/feed.jpg) mantiene
dimensioni e composizione 1080×1350; cambia soltanto la codifica, perché l’API
accetta JPEG. Il PNG della campagna e le email rimangono identici.

Dalla cartella del progetto, dopo il collegamento:

```bash
python -m agents.publisher check \
  --post publishing/2026-10-17-contour-yeux-fr/post.json \
  --image-url 'https://raw.githubusercontent.com/gbetti/AGENT_BEAUTY/codex/instagram-publishing-2026-10-21/publishing/2026-10-17-contour-yeux-fr/feed.jpg'
```

Questo comando controlla il profilo e scarica il JPEG pubblico **senza token**:
il contenuto deve coincidere con il file preparato. Mostra lingua e caption,
senza creare contenitori o post. Il link deve restare accessibile senza login
anche ai server Meta. Sono accettati URL HTTPS diretti, senza redirect.

Per pubblicare realmente il post, esegui:

```bash
python -m agents.publisher publish \
  --post publishing/2026-10-17-contour-yeux-fr/post.json \
  --image-url 'https://raw.githubusercontent.com/gbetti/AGENT_BEAUTY/codex/instagram-publishing-2026-10-21/publishing/2026-10-17-contour-yeux-fr/feed.jpg'
```

Il comando invia il JPEG e la caption francese, attende che il contenitore sia
pronto e lo pubblica. Salva l’ID restituito da Instagram e, quando disponibile,
il permalink. Non invia email e non pubblica automaticamente l’altra lingua,
le story o i banner. Eseguire la normale generazione con `agent.py` continua a
creare gli asset; la pubblicazione richiede questo comando dedicato.

## Registro, ripresa e problemi

Il registro persistente è `data/instagram.sqlite`. **Conservalo e riusalo** per
tutti gli invii del profilo, anche se sposti il progetto su un’altra macchina.
Il manifest da solo non contiene lo storico di pubblicazione. Non avviare il
comando in esecutori temporanei o concorrenti con copie diverse del registro:
non condividerebbero la protezione dai duplicati. `--state` seleziona un percorso
persistente alternativo. L’esecuzione è supportata su Linux e macOS.

- Ripetere un invio già riuscito restituisce il risultato registrato.
- Se il contenitore è ancora in lavorazione, il comando lo ricontrolla fino a
  cinque volte, a intervalli di un minuto. Ripetere il comando riprende lo stesso
  contenitore.
- Prima dell’invio finale il registro viene salvato. Un crash, timeout o errore
  durante quel passaggio lascia un esito da verificare. Al nuovo avvio viene
  letto lo stato remoto: `PUBLISHED` conferma la pubblicazione, senza reinviarla.
  In questo caso l’ID del post o il permalink possono non essere recuperabili;
  l’ID del contenitore non viene presentato come ID del post.
- Se l’esito rimane incerto, il processo si ferma. Verifica il feed Instagram e
  lo stato del contenitore; non cancellare il registro per forzare un retry.
  Anche un errore definitivo dell’invio finale richiede verifica prima di
  correggere lo stato. Non esiste un comando `force` che aggiri questa protezione.
- Un contenitore fallito o scaduto viene bloccato. Dopo avere verificato su Meta
  che non è stato pubblicato, un operatore può ripristinare quella riga allo
  stato `prepared`, azzerando `container_id`, `media_id` e `permalink` per
  ricrearlo. Conserva una copia del registro prima di una correzione manuale.
- Il controllo del profilo non certifica tutti i permessi di pubblicazione:
  Meta può rifiutare l’invio per permessi, limiti o requisiti dell’account.
  Gli errori mostrano i codici diagnostici senza esporre le credenziali.

Il registro Instagram è separato dalla ricerca e conserva l’esito per account,
generazione e lingua. Il vecchio campo `quality.publication_status` fotografa
lo stato alla generazione e non è lo stato live del post.

## Preparare le prossime campagne

Dopo la generazione e la revisione visiva prevista da `AGENTS.md`, usa l’ID
presente nella tabella `generations` del database:

```bash
python -m agents.publisher prepare \
  --generation ID_DELLA_GENERAZIONE \
  --language fr --username gb77ita \
  --output publishing/NUOVA_CAMPAGNA-fr
```

La cartella deve essere nuova. La preparazione rifiuta una revisione mancante,
un PNG modificato dopo la revisione, un formato diverso dal feed o una caption
non valida. Carica il JPEG su un URL HTTPS pubblico nel workflow del repository
o sul tuo hosting, poi usa `check` e `publish` con il nuovo manifest e URL.
Per conservare un URL immutabile puoi usare il commit Git che contiene il JPEG
al posto del nome del ramo. I token non vanno inclusi negli URL degli asset.

Non occorre rigenerare una campagna già revisionata per pubblicarla. Una nuova
campagna continua invece a richiedere ricerca aggiornata e revisione completa.
