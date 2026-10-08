# IOMA Beauty Radar — production créative

Current scope: exactly French and Italian; three PNG formats per language:
feed 1080×1350, story 1080×1920, banner 300×250. No PowerPoint, English,
Chinese, ZIP or extra files in the delivery directory unless requested.

## Before making a campaign
- Read `editorial.py`, the selected official product page, and the product asset manifest.
- Keep official product photography, label, shape and logo unchanged. Generated
  backgrounds must not introduce ingredients or efficacy claims.
- Use product-specific copy grounded in documented benefits. Do not turn a
  loosely related news headline into a product claim or a claim of virality.
- Keep the IOMA logo at the top center, inside each format's safe area.
- Use deliberate editorial typography and native layouts per format.
- No large button in feed/story; their call to action belongs in the caption.

## Visual completion is mandatory
Running tests is not visual approval. Open all six final exports. Inspect:
- product size, contact shadow, light and believable placement;
- unchanged, readable label, clean cutout and no white fringe;
- deliberate visual hierarchy, spacing, accents and spelling;
- feed at about 360 pixels wide, story at about 360 pixels wide,
  banner at its actual 300×250 size;
- no text collisions, clipping, stretched objects or simulated app controls.
If a defect is visible, revise the source and regenerate. Reinspect changed files.
Record the reviewed file SHA-256s and actual observations in the generation's
`quality` object in SQLite. Never infer aesthetic approval from geometry tests.
No user confirmation is required to do this review and correction work.

## Delivery
Use verified accessible GitHub links in this established repository workflow;
cloud `/workspace` paths did not work for this user. Verify remote files before
claiming delivery. Store the six files under a new dated directory in `posts/`;
do not overwrite prior campaigns. Publishing assets to the repository is not
publishing them on social media. Do not claim a social post was published.
