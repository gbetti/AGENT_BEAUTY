# Consegna delle campagne via email

Mittente e destinatario: **gb77ita@gmail.com**, l’account Gmail collegato.
Il 22 ottobre 2026 l’utente ha autorizzato l’invio delle campagne revisionate e
ha sostituito il precedente destinatario con questo stesso account. Inviare
due messaggi per campagna: francese e italiano. La conferma SÌ/NO resta
necessaria per ciascun post Instagram, non per questa consegna email.

Ogni messaggio contiene la newsletter nel corpo, feed e logo originali incorporati,
e cinque allegati: story, banner, PowerPoint, template HTML e bozza EML originale.
Tutti i sette file della lingua sono presenti con gli stessi byte; nessuno ZIP
e nessuna rigenerazione. L’EML allegato conserva il mittente di esempio;
il messaggio effettivo parte dall’account Gmail verificato.

## Gmail collegato: flusso operativo

`assets/email/delivery.json` seleziona `gmail_connector`, mittente e destinatario.
La connessione è disponibile all’agente tramite il plugin Gmail; non richiede
di copiare password o token nel progetto. Il programma Python prepara le
richieste MIME, mentre l’agente nella chat esegue l’invio con il connettore.
Il solo comando Python non equivale all’invio remoto.

1. Verificare il profilo con Gmail `get_profile`: deve essere `gb77ita@gmail.com`.
2. Dopo il controllo visivo, registrare tutti i 14 hash nel report della campagna.
3. Preparare la consegna:

```sh
python -m agents.mailer deliver \
  --generation ID_GENERAZIONE \
  --output output/email-delivery/ID_GENERAZIONE
```

Il comando produce `delivery.json`, `gmail-requests.json`, `fr-gmail-request.json`
e `it-gmail-request.json`. Controlla destinatario, mittente e integrità di tutti
gli originali; conserva l’HTML con immagini CID e include gli allegati come
base64url senza conversioni. Il limite conservativo è 25 MB di richiesta
codificata per messaggio; non si applica il limite Outlook di 3 MB per file.

4. Prima di ciascun invio, riservare il tentativo nel registro persistente:

```sh
python -m agents.mailer gmail-reserve \
  --requests output/email-delivery/ID_GENERAZIONE/gmail-requests.json \
  --language fr
```

5. Leggere `fr-gmail-request.json` e passare l’oggetto JSON esatto al tool Gmail
   `send_email`. L’utente ha già autorizzato l’invio: non creare un’altra domanda.
   Trasferire i dati programmaticamente, senza stampare allegati base64 nella
   chat. Se il lettore tronca l’output, leggere blocchi completi e ricomporli
   prima di interpretare il JSON.
6. Salvare la risposta strutturata reale del tool e registrarla:

```sh
python -m agents.mailer gmail-record \
  --packet ID_RESTITUITO_DA_GMAIL_RESERVE \
  --response output/email-delivery/ID_GENERAZIONE/fr-gmail-response.json
```

La risposta deve contenere l’ID del messaggio e l’etichetta `SENT`.
Ripetere i passaggi 4–6 per `it`. Leggere infine i messaggi Gmail inviati e
verificare mittente, destinatario, oggetto e parti MIME. Il registro locale
si consulta con `python -m agents.mailer status`.

## Invio reale già completato

La campagna contorno occhi del 17 ottobre 2026 è stata inviata il **22 ottobre
2026, 01:16 Europe/Paris**, da e a **gb77ita@gmail.com**:

- FR: «Et si tout commençait par le regard ?»;
- IT: «E se tutto iniziasse dallo sguardo?».

Gmail ha confermato `SENT` e `INBOX` per entrambi. Una lettura successiva ha
verificato intestazioni e tutti i sette file originali per lingua. Le copie
di feed/logo contenute nell’EML allegato possono comparire anche tra le parti
MIME annidate: non sono invii aggiuntivi. Il materiale conserva data e fonti
della campagna archiviata; non è presentato come nuova ricerca settimanale.

Manifest e risposte sono in `output/email-delivery/2026-10-17-contour-yeux-gmail/`,
gli ID di invio nel registro locale. **Non reinviare questa campagna.** Nessuna
email della consegna è partita verso il precedente destinatario.
La [ricevuta verificata](email-deliveries/2026-10-22-contour-yeux-gmail.json)
conserva ID Gmail, destinatario, nomi/dimensioni e hash degli originali inviati.

## Errori e ripresa

Conservare `data/email-delivery.sqlite`. Lo stesso registro copre Gmail e
Outlook; un tentativo registrato impedisce un secondo invio anche dopo un
cambio di trasporto. `connector_sending` indica un tentativo in corso o da
riconciliare, mai un successo automatico.

Se il tool Gmail ha un timeout, non ripeterlo. Cercare negli inviati a partire
dall’ora del tentativo, leggere i candidati e confrontare mittente, destinatario,
oggetto, corpo e originali allegati prima di registrare la risposta riconciliata.
Se l’esito resta incerto, lasciarlo tale; non cancellare il registro per aggirare
il blocco. `SENT` conferma l’invio. Per questo invio a sé stessi è stata verificata
anche `INBOX`; nessuna lettura del messaggio da parte dell’utente è presunta.

## Trasporto Python Outlook alternativo

Resta disponibile per un’altra configurazione esplicita, selezionando
`transport: outlook` e un mittente verificato. Collegare Gmail non configura
Outlook e non espone le credenziali Gmail al programma Python.

Per Microsoft Graph servono `OUTLOOK_ACCESS_TOKEN` nei segreti dell’ambiente,
autorizzato a `graph.microsoft.com`, e `BEAUTY_EMAIL_SENDER`. Permessi delegati:
`User.Read`, `Mail.ReadWrite`, `Mail.Send`. `check` verifica il profilo; `send`
e `deliver` eseguono le API soltanto quando è selezionato questo trasporto.
Il token deve essere valido; rinnovo OAuth e caricamenti Outlook di singoli
allegati da 3 MB in su non sono implementati. Il limite viene controllato prima
di qualsiasi scrittura remota. Il registro conserva gli ID immutabili e non
ritenta automaticamente scritture incerte.

Documentazione Microsoft:
[bozze](https://learn.microsoft.com/en-us/graph/api/user-post-messages),
[allegati](https://learn.microsoft.com/en-us/graph/api/message-post-attachments),
[invio](https://learn.microsoft.com/en-us/graph/api/message-send),
[ID immutabili](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).

## Destinatari privati e collegamento Instagram

La configurazione locale `data/email-settings.json`, ignorata da Git, può definire
`recipients` come lista esatta di indirizzi autorizzati. Il pacchetto MIME, la
prenotazione e la ricevuta sono vincolati alla stessa lista. Non sono aggiunti CC
né BCC. Verificare i destinatari nella configurazione privata quando si trasferisce
l’agente su un altro ambiente; non pubblicare gli indirizzi dei collaboratori nel PR.

Le nuove campagne aspettano la pubblicazione Instagram per includere il permalink
reale in HTML e testo semplice. L’intestazione conserva il solo logo originale,
senza sottotitolo; il visual non contiene loghi aggiunti. Le campagne animate
allegano anche il file MP4 originale, oltre ai sette file previsti per lingua.
