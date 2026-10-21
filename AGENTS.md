# IOMA Beauty Radar — production créative

Current scope: exactly French and Italian; three PNG formats per language:
feed 1080×1350, story 1080×1920, banner 300×250, plus one four-slide
PowerPoint and coordinated email per language. The email outputs are
`email.html`, `email.eml` and its original `email-logo.png`; it uses the same
`feed.png` unchanged. No English, Chinese, ZIP or unrelated delivery files.

## Three-agent architecture
- `agent.py` is the existing CLI; `coordinator.py` executes Trend Beauty,
  Keyword & Domanda and Creative Studio in order. Their implementations live
  in `agents/trends.py`, `agents/keywords.py` and `agents/assets.py`.
- Use the handoff contracts in `agents/contracts.py`; do not mutate upstream
  evidence or attach keyword data to another product/run. `catalog.py` owns
  local product loading and links to original photographs.
- Keep pipeline metadata and the shared campaign brief in the same SQLite
  generation transaction as all exports. A failed agent must prevent
  downstream work; retain the original cause and identify the failing agent.
- These are specialized Python components, not independent LLM services.
  The split does not remove fresh reviewed research or visual review requirements.
- `python -m agents.keywords --research <current-brief>` runs keyword research
  independently from RSS discovery and creative exports. It verifies the same
  reviewed evidence, reads the local catalog and archives a separate JSON report
  under `output/keywords/`; it must not insert a creative generation or overwrite
  earlier reports. This research-only output is separate from campaign delivery.

## Before making a campaign
- Read `editorial.py`, the selected official product page, and the product asset manifest.
- Keep official product photography, label, shape and logo unchanged. Generated
  backgrounds must not introduce ingredients or efficacy claims.
- Use product-specific copy grounded in documented benefits. Do not turn a
  loosely related news headline into a product claim or a claim of virality.
- Never overlay an IOMA logo on social graphics or the email hero. Preserve the original packaging label and its printed brand unchanged.
- Use deliberate editorial typography and native layouts per format.
- No large button in feed/story; their call to action belongs in the caption.
- New campaigns rotate `product` → `model` → `pack` with `--creative-mode auto`.
  `art_direction.py` varies palette, architectural motif and lighting field;
  compare the actual background hash against the full campaign history and do
  not reuse it. Save seed, palette, motif, assets and mode in the creative brief.
  Maintain smooth copy space and a continuous support plane. Original archived
  studio plates remain reproducible; they are not the only new background choices.
- `model` uses the checked fictional adult portrait in `assets/models/manifest.json`;
  it is an editorial image, never a customer, testimonial or treatment result.
  `pack` uses two or three different original products in the same skin/hair
  family. Do not invent a bundle price, combined efficacy or a special offer.
  Show the exact composition in the caption. Add new portraits only with provenance
  and visual review; never generate or alter product labels.
- Cast shadows use the product's alpha silhouette and the background's documented
  light direction. Contact occlusion follows its base footprint, without a gap;
  the cast shadow softens and fades away from contact. Keep label pixels intact.

## Weekly evidence and PowerPoint
- Refresh a dated research brief in `research/` for each requested campaign.
  The CLI rechecks URLs and rejects briefs reviewed more than 36 hours ago.
  Never refresh only the timestamp: read and update the actual evidence.
- First slide: this week's skincare signals, ingredients, and documented
  advertising/promotion activity. Second slide: IOMA product, why its formula
  connects to those signals, proposed social activation and a measurable test.
- Third slide: Google Trends query data, France in French and Italy in Italian.
  Use seven completed UTC days, Face & Body Care (143) for skincare or Hair Care
  (146) for hair products, Web search,
  no seed query. Show top relative scores separately from rising percentages.
  Never call index scores search volumes or compare FR/IT scores directly.
  Keep source spelling, values and order; disclose the editorial relevance filter.
  Archive raw responses; reject stale/mismatched scopes or insufficient relevant
  queries. Use present queries from the reviewed pool, preserving source order.
- Fourth slide: visible article titles, publisher, publication date, and explicit
  clickable reading links. Separate editorial/trade articles from brand releases.
- Keep an editorial layout: ivory background, dark text, restrained rules,
  generous margins, top-centered IOMA logo. Include source dates and hyperlinks.
- Separate editorial coverage, brand promotions and advertising campaigns.
  Older campaigns may appear only with a documented active date range and
  their original article date. Mark ended promotions; never invent ad spend.
- Claim-based product-only visuals show exactly two labeled arrows toward the product. Inspiration and review layouts omit arrows and efficacy promises.
  Portrait and pack layouts keep the image clear; verified ingredient information
  stays in the research brief and PowerPoint rather than forcing arrows over faces
  or assigning the main product's formula to all items in a pack.
  Select ingredients present in the official INCI and relevant to recent
  sources. Use `assets/ingredients.json`; do not borrow competitor ingredients.
  Editorial priority is not a claim about ingredient concentration.
- The verified ingredient registry supports Crème Sublime and Crème Généreuse
  Contour des Yeux (peptides and vitamin E). Each still needs a current,
  product-specific brief. The eye formula has no terminal PARFUM: stop its
  official INCI at the list boundary, never at reviews or related products.
- The shampoo and repairing conditioner also have reviewed bilingual copy,
  email content and ingredient registries. Their INCI is scoped to the official
  composition accordion: PARFUM may appear mid-list and is not an end marker.

## Public catalog and customer reviews
- `python catalog_sync.py` refreshes all public products, FR/IT descriptions,
  composition/details, variants/prices, original photos and paginated Judge.me
  reviews. `assets/catalog/ioma.json` seeds both new and existing SQLite catalogs.
  Preserve existing generations, reviewed claims and Instagram publishing state.
- Store review scores, text, dates, public display names, source and completeness
  separately in `product_reviews`. Opinions are not verified efficacy claims.
  Missing or partial review access is not zero reviews and never counts as complete.
- The current snapshot covers 63 sitemap products and 2,461 public reviews.
  Only products with reviewed creative briefs can enter campaign production;
  importing a product does not invent its Italian advertising copy or research.
- The user's shampoo price (25 EUR / 200 ml) is a supplied reference. The live
  storefront price collected on 2026-10-22 is 24.90 EUR; preserve both sources.
- `preview_creatives.py` produces clearly marked design previews to inspect
  layouts without inventing fresh weekly research. These are not publication
  offers and must not bypass normal campaign review and SI/NO confirmation.

## Visual completion is mandatory
Running tests is not visual approval. Open all six final exports. Inspect:
- product size, contact shadow, light and believable placement;
- unchanged, readable label, clean cutout and no white fringe;
- deliberate visual hierarchy, spacing, accents and spelling;
- feed at about 360 pixels wide, story at about 360 pixels wide,
  banner at its actual 300×250 size;
- no text collisions, clipping, stretched objects or simulated app controls.
If a defect is visible, revise the source and regenerate. Reinspect changed files.
Render and open both PowerPoints; inspect every slide for legibility,
clipping, source attribution and consistent typography.
Record the reviewed file SHA-256s and actual observations in the generation's
`quality` object in SQLite. Never infer aesthetic approval from geometry tests.
No user confirmation is required to do this review and correction work.

## Coordinated email
- Generate the email after the campaign exports in each of the same two languages.
- Use the campaign feed PNG without regeneration, cropping or recompression.
- Follow the supplied IOMA email style: centered original logo, large hero,
  concise product-specific copy and one CTA. Subject max 55 characters,
  preheader max 100, commercial body max 70 words. Structure the commercial
  copy as five short statements: curiosity hook, three benefit statements,
  and a conditional explanation of whom the product suits. Allow natural
  wrapping on phones; do not force five physical lines on every screen.
  Curiosity hooks must not
  invent reviews, discounts, scarcity, ingredient claims or clinical results.
- Use documented catalog benefits. Email examples inform style, not claims.
- Review the HTML at desktop and phone width, and verify the MIME draft
  contains the exact source PNG bytes.
- The user explicitly authorized sending every completed, reviewed campaign's
  emails, PowerPoints and original assets on 2026-10-22. The final recipient
  allowlist is stored privately in `data/email-settings.json`; the latest explicit user instruction specifies exactly two recipients. Do not add CC, BCC or any other recipients. This replaces prior single-recipient delivery.
  After recording all 14 reviewed hashes, run `python -m agents.mailer deliver`
  with the generation ID and a new delivery directory. Do not ask for another
  email approval. Instagram normally requires per-post consent; explicit bounded batch permission is described below.
- Gmail is connected and is the default transport. `deliver`/`send` exports
  structured MIME requests for the connector; it does not itself send them.
  Complete the delivery in chat: verify the Gmail profile, reserve each request
  with `gmail-reserve`, call the Gmail `send_email` tool with that exact request,
  then save the real response using `gmail-record`. Use the verified sender,
  never a guessed From address. Follow `EMAIL_DELIVERY.md` for reconciliation.
- The archived contour-eye FR/IT emails were actually sent to gb77ita@gmail.com
  on 2026-10-22 (Europe/Paris), with all original assets; both have SENT and INBOX
  labels. Do not send them again. Preserve `data/email-delivery.sqlite`.
- `assets/email/delivery.json` stores public defaults; `data/email-settings.json` stores the private exact recipient allowlist. Send one message per language,
  with the newsletter as its body and all seven original files, including inline
  feed/logo. Use the authenticated sender, never the draft's IOMA From header.
  Follow `EMAIL_DELIVERY.md`; preserve `data/email-delivery.sqlite` to avoid
  duplicate sends. A missing sender is a configuration blocker, not a delivery.
- HTML is a Klaviyo template: publish its assets at the configured HTTPS base
  before import. Leave per-recipient unsubscribe resolution to the ESP.
  The standalone MIME draft uses embedded images and defaults to a mailto
  unsubscribe request to the IOMA contact address. The delivery step uses a copy
  of the original campaign email; keep all archived files unchanged.

## Delivery
Use verified accessible GitHub links in this established repository workflow;
cloud `/workspace` paths did not work for this user. Verify remote files before
claiming delivery. Store the eight campaign files and six email files together
under a new dated directory in `posts/`; do not overwrite prior campaigns.
Publishing assets to the repository is not
publishing them on social media. Claim publication only after a confirmed
Instagram API response or a reconciled PUBLISHED container state.

## Instagram publishing
- Unless an explicit bounded user authorization covers the batch, every completed campaign must end with a publication question for each
  proposed Instagram feed. The user explicitly requested this flow: create,
  show the exact content, ask whether to publish, and publish if the reply is
  SI/SÌ. A NO leaves it unpublished. Silence is never consent. Follow `INSTAGRAM.md`.
- Complete the visual review, prepare the JPEG, host it at a verified immutable
  public URL and run `python -m agents.publisher offer` BEFORE asking. Show the
  image, caption, language and target profile with the returned question. Keep
  the returned request ID associated with that question in the chat.
- On the user's SI/SÌ, immediately run `python -m agents.publisher respond
  --request <id> --answer SI` using the same persistent state. Do not ask again
  or stop at instructions. On NO, use `--answer NO`. If several posts are shown,
  associate the answer unambiguously with the selected post; approval of one
  language never authorizes the other or future content.
- These commands integrate the creative delivery with publishing; the Python
  renderer alone cannot certify visual quality. Its output records the pending
  question per language. Finish the existing review and offer workflow in chat.
- Use Instagram Login with a Business/Creator account. Read the access token
  only from the execution environment; never put credentials in chat, public
  manifests, Git, asset URLs or diagnostic output.
- Select one language and an explicit target username. Check the authenticated
  username against that target before every publication.
- Prepare only visually reviewed generations with matching source SHA-256s.
  A separate 1080×1350 JPEG is an Instagram transport derivative: preserve the
  original campaign PNGs and email bytes. Store the derivative and portable
  manifest under `publishing/`, without overwriting older preparations.
- Verify the public JPEG URL returns the prepared bytes without authentication.
  Do not claim that a local preview establishes Meta's ability to fetch it.
- Keep one durable `data/instagram.sqlite` register across invocations. Commit
  the publishing state before calling media_publish. Never automatically resend
  an uncertain write or erase the register to bypass duplicate protection.
- `connect`, `check` and `offer` only read remote APIs. `offer` persists a local
  request bound to the reviewed post, public URL and verified account. `respond`
  performs the real social action only on SI/SÌ. `publish` asks in a terminal;
  without an interactive terminal it saves the question without sending.
- @gb77ita is the current default profile. The French eye cream feed was
  published after an explicit SI on 2026-10-22 (Europe/Paris):
  https://www.instagram.com/p/DexcJYEgdJL/ . Its receipt is in
  `publishing/2026-10-17-contour-yeux-fr/publication.json`; do not publish it again
  from a fresh register. Never invent an affirmative answer. Outside a user-authorized batch, changed content requires a new preview and question.
- Unit tests mock Meta. Report real account connection and publication separately
  from test results. An unavailable permalink does not negate a confirmed post.

## Editorial rotation and the current five-post batch
- New campaigns alternate claim, inspiration and sourced review using `--editorial-mode`.
  This is separate from product/model/pack art direction. Backgrounds still vary.
- Inspiration uses ingredient or skin-type themes without efficacy promises. Export
  an actual six-second animated pattern MP4, preserve product pixels, and review
  multiple frames and the loop. Publish it as a Reel shared to the feed.
- Reviews must belong to the depicted product; quote the retrieved text faithfully,
  include its rating/date/source and label translations. Do not invent or improve
  a customer quote, remove qualifications, or call it efficacy evidence.
- Email header: original logo alone, no expertise subtitle. Hero: no added logo.
  After confirmed publication, finalize both language emails with the actual
  Instagram permalink, review the HTML again and refresh only changed file hashes.
- The user explicitly authorized exactly five new French posts on @gb77ita on
  2026-10-22 (Paris), without further publication questions, and delivery after each.
  `authorized_batch.py` binds each of five slots to reviewed content in the durable
  Instagram register. Keep the grant and email allowlist private under `data/`.
  This exception does not authorize a sixth post, another account or future batches.
- Resume uncertain publication/send states read-only. Preserve all durable registers.
