---
name: docuseal
description: Create, send, track and download e-signature contracts through the DocuSeal cloud API (Pro plan). Use when the user wants to draft a contract or agreement for signature, turn a PDF/DOCX into a signable template, send a document to someone to sign, check which contracts are pending/signed/declined, resend or archive a request, or download signed copies.
---

# DocuSeal contracts

Drive DocuSeal (hosted, Pro plan) via its REST API using `scripts/ds.sh`, which
adds the auth header and base URL. Always call it by its path relative to this
skill, e.g. `bash .claude/skills/docuseal/scripts/ds.sh GET /templates`
(or `~/.claude/skills/docuseal/scripts/ds.sh` if installed globally).

## Setup (one time, by the user)
- Local: `DOCUSEAL_API_KEY` exported in the user's shell (DocuSeal console → API).
- Claude Code cloud: the key is saved as a network secret for `api.docuseal.com`
  (header `X-Auth-Token`); the proxy injects it, so no variable is needed.
- `DOCUSEAL_API_URL` only if the account is on the EU server: `https://api.docuseal.eu`.
- Never print, echo, log or write the key into any file. If it is missing,
  tell the user to set it; do not ask them to paste it into chat.

## Ground rules
- **Sending is irreversible and costs money** ($0.20 per document signed via API).
  Before any `POST /submissions*` that emails people, show the user a summary
  (document, each signer's role/name/email, signing order, pre-filled values,
  email subject) and get an explicit "yes". For dry runs use `"send_email": false`.
- **Notifications are always on.** Every send uses `"send_email": true` (top
  level and never overridden per submitter), so each signer is emailed when it
  is their turn and all parties get the signed copy on completion. Only turn
  emails off if the user explicitly asks, or for a dry run they approved.
- Signing order: default `"order": "preserved"`, with `submitters` listed in
  the order the user wants them to sign (first signer first).
- Write request bodies to a temp JSON file (or pipe via `-`), never inline huge base64.
- IDs: templates and submissions have integer `id`s. Look them up; don't guess.

## Workflows

### 1. Find templates / inspect fields and roles
```bash
ds.sh GET "/templates?q=NDA&limit=10"         # search by name
ds.sh GET /templates/123                      # fields[], submitters[] (roles), documents
```
Use the template's `submitters[].name` values as `role` when sending, and its
`fields[].name` values as keys in `values`.

### 2. Create a template from a DOCX or PDF
Fields come from text tags written into the document itself:
`{{Field Name;role=Client;type=signature}}`. Common types: `text` (default),
`signature`, `initials`, `date`, `number`, `checkbox`, `select`, `phone`,
`image`, `stamp`. DOCX also supports `[[variable]]` placeholders filled per send
via `variables`. Tags are removed from the rendered document.

Tag pitfalls (learned the hard way):
- **Role names must have no spaces** (`role=RhodeLabs`, not `role=Rhode Labs`).
  DocuSeal drops spaces wherever a tag wraps onto a new line, silently creating
  an extra signer role. Keep tags short so they fit on one line.
- **Existing contracts with blank lines** (`By: ______`): copy the DOCX and
  replace each underscore run with a tag by editing `word/document.xml`
  directly (python-docx misses text inside content controls). Never modify the
  user's original file.
- Blanks that the *sender* decides (fees, prices, dates) must not be left for the
  signer: assign them to the sender's own role and pre-fill them on that submitter with
  `fields: [{"name": ..., "default_value": ..., "readonly": true}]`. Ask the user
  for any such value; never guess a commercial term.
- **Inline fields (a number mid-sentence, like a fee %):** a box's width and the
  gap it leaves in the text both come from the tag's length, so a normal-size tag
  leaves a huge hole. Put the tag in its own run at tiny type
  (`<w:sz w:val="1"/>`), raised with `<w:position w:val="12"/>`, no spacer, and
  size the box explicitly:
  `{{Referral Fee;role=RhodeLabs;width=16;height=12;font_size=10}}`.
  Then measure the template PDF (box vs. the next word's x/y, using pymupdf)
  and screenshot a dry-run before calling it done.
- Date fields default to DD/MM/YYYY. For US contracts, add
  `preferences.format: "MM/DD/YYYY"` to each date field in the send body.
- After uploading, verify the response: role list = intended signers only, and
  every field has the right name, type and role. If wrong, fix, re-upload, and
  archive the bad template (`DELETE /templates/{id}`).

When drafting a contract for the user, generate a DOCX (python-docx or the docx
skill) containing these tags — e.g. a signature block per party:
```
Client: {{Client Name;role=Client}}   Signature: {{Client Sig;role=Client;type=signature}}   Date: {{Client Date;role=Client;type=date}}
Company: {{Company Signer;role=Company}} Signature: {{Company Sig;role=Company;type=signature}}
```

Upload (file may be base64 or a public download URL):
```bash
python3 - "Consulting Agreement" path/to/contract.docx > /tmp/ds_tpl.json <<'EOF'
import sys, json, base64, os
name, f = sys.argv[1], sys.argv[2]
print(json.dumps({"name": name, "documents": [{
  "name": os.path.basename(f),
  "file": base64.b64encode(open(f, "rb").read()).decode()}]}))
EOF
ds.sh POST /templates/docx /tmp/ds_tpl.json   # or /templates/pdf for a PDF
```
Optional body keys: `folder_name`, `external_id`, `documents[].dynamic`.
Without tags you can pass `documents[].fields[]` with `areas` (`x,y,w,h,page`),
but tags are far easier. Confirm the response has non-empty `fields`.

### 2b. House workflow: master template → per-counterparty copy → send
- **Masters** are named `[Template] <Agreement name>` (e.g. `[Template] Rhode
  Labs Referral Agreement`). Never send from a master and never edit one for a
  single deal.
- For each counterparty, clone the master:
  `POST /templates/{master_id}/clone` with
  `{"name": "<Agreement name> – <Counterparty>", "folder_name": "<e.g. Referral Partners>"}`.
  Signers see this name at the top of the signing page and in emails.
- Make the deal-specific changes on that copy, normally at send time: the
  sender-owned pre-fills (fee etc., `readonly`) and the signer names/emails.
  If a deal needs different contract wording, edit a copy of the master's DOCX
  and upload it as that counterparty's template instead of cloning.
- Preview (3b) and send (3) from the copy, never the master.
- Find a master with `GET /templates?q=[Template]`. Find a partner's copy with
  `GET /templates?q=<Counterparty>` or `?folder=Referral Partners`.

### 3. Send a template for signature
```json
{
  "template_id": 123,
  "order": "preserved",
  "send_email": true,
  "message": {"subject": "Please sign: Consulting Agreement",
              "body": "Hi, please review and sign: {{submitter.link}}"},
  "submitters": [
    {"role": "Client", "name": "Jane Doe", "email": "jane@acme.com",
     "values": {"Client Name": "Jane Doe"}},
    {"role": "Company", "email": "me@mycompany.com"}
  ]
}
```
```bash
ds.sh POST /submissions /tmp/ds_send.json
```
- `order: "preserved"` = sign in array order; `"random"` = all at once.
- Other useful keys: `expire_at` (ISO date), `bcc_completed`, `reply_to`,
  `variables` (for `[[...]]`), per-submitter `fields[]` with `readonly: true`
  to lock pre-filled values, `completed: true` to auto-sign the user's own side.
- Response is an array of submitters: report `submission_id`, each `email`,
  `status`, and `embed_src` (the signing link).

### 3b. Preview before sending (offer this every time)
1. Re-fetch the template (`GET /templates/{id}`) right before previewing or
   sending. The user may have edited it in the DocuSeal web app (renamed it,
   moved a field to another role), and old assumptions will break the send.
2. Create a **dry-run** submission from the exact send body, changed only to
   `"send_email": false` and placeholder emails (`preview-<role>@example.com`).
   Never use the real signers' emails for a preview.
3. Give the user each role's `embed_src` link so they can see exactly what each
   signer sees. Tell them **not to sign** in the preview: a completed one counts
   as a signed document.
4. Optionally screenshot the first signer's page with Playwright and check that
   pre-filled values actually render.
5. Archive the preview (`DELETE /submissions/{id}`) before the real send.

Pre-fill gotchas:
- `"Unknown field: X"` in a submitter's `fields[]` means X belongs to a
  **different role**. Put the pre-fill on the submitter that owns the field.
- A field whose value the sender decides (fee, price) should belong to the
  sender's role, pre-filled with `default_value` + `readonly: true`. Earlier
  signers still see it on the document.
- `GET /submissions/{id}` doesn't show pre-filled values before signing, so
  check the rendered page instead.

### 4. One-off contract without saving a template
`POST /submissions/docx` (or `/submissions/pdf`, `/submissions/html`) with
`name`, `documents[{name,file}]`, `submitters[]`, plus the same optional keys
as above. Use this when the user won't reuse the document.

### 5. Track status
```bash
ds.sh GET "/submissions?status=pending&limit=20"   # pending|completed|declined|expired
ds.sh GET "/submissions?q=jane@acme.com"
ds.sh GET "/submissions?template_id=123"
ds.sh GET /submissions/456                         # per-submitter status, opened/completed timestamps
```
Paginate with `after=<last id>`. Summarize as a table: contract, signer,
status, sent/opened/completed dates.

### 6. Download signed documents
```bash
ds.sh GET "/submissions/456/documents?merge=true"
```
Returns `documents[].url`; download with `curl -sSL -o <name>.pdf "<url>"`
into the location the user asks for.

### 7. Change / cancel
- Update a signer (fix email, resend): `PUT /submitters/{id}` with e.g.
  `{"email": "new@x.com", "send_email": true}`.
- Archive (cancel) a submission: `DELETE /submissions/{id}`. Archive a
  template: `DELETE /templates/{id}`. Confirm with the user first.
- Clone a template: `POST /templates/{id}/clone` with `{"name": "..."}`.

## Errors
`ds.sh` prints the JSON body and exits non-zero with `HTTP <code>` on stderr.
401 → bad/missing key or wrong region URL. 422 → read the `error` message
(usually an unknown role, missing field name, or template without fields).
Full spec: https://console.docuseal.com/openapi.yml
