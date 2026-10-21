# Pubblicare il feed su Instagram

L’agente pubblica una singola immagine con la sua caption attraverso **Instagram
API with Instagram Login**. Il post preparato è quello francese della Crème
Généreuse Contour des Yeux, destinato a **@gb77ita**. L’autorizzazione del profilo
è configurata: il 21 ottobre 2026 l’API ha riconosciuto @gb77ita come
`MEDIA_CREATOR` e ha restituito la quota di pubblicazione. Sono stati verificati
anche URL pubblico e hash del JPEG. Il **22 ottobre 2026 (Europe/Paris)**,
dopo il SÌ dell’utente, il feed francese è stato
[pubblicato su Instagram](https://www.instagram.com/p/DexcJYEgdJL/).
Una successiva lettura API ha confermato ID `17914666347467428`, caption e permalink.
La [ricevuta](publishing/2026-10-17-contour-yeux-fr/publication.json) documenta
questo invio; ogni nuovo contenuto richiede una nuova risposta SÌ.

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

`connect` legge il profilo autenticato, controlla nome, ID, tipo di account e
accessibilità della quota di pubblicazione.
Non pubblica nulla e non stampa il token. Un nome profilo diverso da @gb77ita
blocca il processo. Il token scade e può essere revocato: rinnova l’autorizzazione
quando necessario. La gestione OAuth di più clienti e il rinnovo automatico
non sono inclusi in questa integrazione per un singolo account.

Riferimenti ufficiali: [avvio e generazione del token](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started),
[permessi Instagram Login](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login),
[pubblicazione](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/).

## Il post francese pubblicato

Il manifest è [`publishing/2026-10-17-contour-yeux-fr/post.json`](publishing/2026-10-17-contour-yeux-fr/post.json).
Contiene profilo, lingua, caption, riferimento al PNG revisionato e hash dei file.
La copia [`feed.jpg`](publishing/2026-10-17-contour-yeux-fr/feed.jpg) mantiene
dimensioni e composizione 1080×1350; cambia soltanto la codifica, perché l’API
accetta JPEG. Il PNG della campagna e le email rimangono identici.

Dalla cartella del progetto, dopo il collegamento:

```bash
python -m agents.publisher check \
  --post publishing/2026-10-17-contour-yeux-fr/post.json \
  --image-url 'https://raw.githubusercontent.com/gbetti/AGENT_BEAUTY/3c85f1886ec5939d26343b58ef613fcc7bb02e5e/publishing/2026-10-17-contour-yeux-fr/feed.jpg'
```

Questo comando controlla il profilo e scarica il JPEG pubblico **senza token**:
il contenuto deve coincidere con il file preparato. Mostra lingua e caption,
senza creare contenitori o post. Il link deve restare accessibile senza login
anche ai server Meta. Sono accettati URL HTTPS diretti, senza redirect.

## Domanda e risposta per ogni contenuto

Il flusso nella chat è: generazione → revisione visiva → JPEG pubblico verificato
→ anteprima con caption e domanda → risposta dell’utente. La normale generazione
registra e mostra una domanda per ciascuna lingua. L’agente completa i controlli
e prepara l’offerta prima di chiedere il consenso, senza chiedere all’utente di
eseguire i comandi o di certificare la revisione visiva.

Per mostrare un post preparato e salvare la domanda senza inviare nulla
(l’esempio seguente si riferisce al post storico già pubblicato):

```bash
python -m agents.publisher offer \
  --post publishing/2026-10-17-contour-yeux-fr/post.json \
  --image-url 'https://raw.githubusercontent.com/gbetti/AGENT_BEAUTY/3c85f1886ec5939d26343b58ef613fcc7bb02e5e/publishing/2026-10-17-contour-yeux-fr/feed.jpg'
```

Il risultato contiene `request_id`, immagine, caption, lingua, profilo e domanda.
L’agente mostra questi contenuti nella chat e conserva l’ID. Solo dopo il SÌ
dell’utente esegue immediatamente:

```bash
python -m agents.publisher respond --request ID_RESTITUITO --answer SI
```

Con `--answer NO` registra il rifiuto senza collegarsi a Instagram. SÌ, SI e sì
sono equivalenti; risposte vuote o ambigue non pubblicano. Non esiste un consenso
globale per le prossime campagne. Una caption, immagine, lingua o destinazione
modificata richiede una nuova offerta e un nuovo SÌ. Non usare `--answer SI`
senza una risposta effettiva dell’utente a quel post.

La domanda resta nel medesimo registro SQLite del publisher tra due comandi o
messaggi della chat. Un errore dopo il SÌ conserva l’approvazione: riprendere la
stessa richiesta permette al publisher di verificare l’esito senza inviare due
volte. Non serve una seconda conferma per riprendere il contenuto già approvato.

Da un terminale interattivo è disponibile anche:

```bash
python -m agents.publisher publish \
  --post publishing/2026-10-17-contour-yeux-fr/post.json \
  --image-url 'https://raw.githubusercontent.com/gbetti/AGENT_BEAUTY/3c85f1886ec5939d26343b58ef613fcc7bb02e5e/publishing/2026-10-17-contour-yeux-fr/feed.jpg'
```

Il comando mostra immagine, caption e domanda e attende SÌ/NO. Solo con SÌ invia
il JPEG e la caption, attende il contenitore e pubblica. Senza un terminale
interattivo salva la richiesta e termina senza inviare: si usa poi `respond`.
Salva l’ID restituito da Instagram e, quando disponibile, il permalink. Non invia
email e non estende la conferma all’altra lingua, alle story o ai banner.

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
generazione e lingua. `instagram_approvals` conserva domanda e risposta;
`instagram_publications` conserva lo stato dell’invio. I campi della generazione
`quality.publication_status` e `localizations.<lingua>.instagram` fotografano lo
stato alla creazione e non sono lo stato live del post.

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
o sul tuo hosting, poi usa `offer` con il nuovo manifest e URL, mostra il contenuto
e chiedi SÌ/NO. `agent.py --instagram-username NOME` cambia il profilo proposto;
passa lo stesso nome a `prepare`.
Per conservare un URL immutabile puoi usare il commit Git che contiene il JPEG
al posto del nome del ramo. I token non vanno inclusi negli URL degli asset.

Non occorre rigenerare una campagna già revisionata per pubblicarla. Una nuova
campagna continua invece a richiedere ricerca aggiornata e revisione completa.

## Verifica dell’integrazione

I test del publisher e delle conferme usano risposte Meta simulate: coprono
SÌ/NO, assenza di risposta, cambio del contenuto o account, ripresa dopo timeout,
invii duplicati e comandi interattivi/non interattivi. Il collegamento reale,
la quota API e il JPEG pubblico sono stati verificati separatamente il
21 ottobre 2026. Dopo la conferma esplicita, il 22 ottobre (Europe/Paris) è riuscita
anche la pubblicazione reale del feed francese. Sono passati i 78 test della
suite completa e, dopo gli ultimi tre casi aggiunti, tutti i 38 test Instagram
(81 casi distinti verificati). La lettura API del post pubblicato ha confermato
la caption approvata. I token possono comunque scadere o essere revocati.

## Rotazione editoriale e Reel

`agent.py --editorial-mode auto` alterna claim documentato, ispirazione e recensione
attribuita. Le immagini social non aggiungono il logo. L’ispirazione genera anche
`reel.mp4`: sei secondi, H264, 1080×1920, pattern animato dietro il prodotto originale.
La modalità ingredienti usa soltanto ingredienti verificati nella formula. I claim
mantengono la propria rotazione prodotto/modella/pack; gli altri post non la consumano.

Dopo la revisione dei PNG e del video, preparare con `agents.publisher prepare
--kind reel`; `check`, `offer` e `respond` supportano lo stesso manifest e verificano
il video pubblico. Il Reel viene condiviso anche nel feed. Il normale consenso per
singolo post resta attivo. Un’autorizzazione esplicita dell’utente per un lotto limitato
può invece usare `python authorized_batch.py --grant <file privato> --slot <1–5>
--post <manifest> --media-url <URL pubblico>`. Non creare una concessione senza una
richiesta esplicita: limite, profilo, lingua, scadenza e ogni contenuto sono vincolati
nel registro persistente. Un errore o timeout non libera una posizione già usata.

Dopo la pubblicazione, `campaign_delivery.finalize_published_emails` legge la ricevuta
persistente della stessa generazione e inserisce il permalink nelle due email.
Rivedere le email modificate e aggiornare i loro hash prima di inviarle. Non usare
un URL di anteprima o di un altro post. I nuovi invii richiedono questo collegamento.
