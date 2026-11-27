# Getting API keys

The agent needs two keys in `.env`:

| Variable | Used for | Needed from |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLM jobs (dish ideas, safety check, feedback) | P3 evals onward |
| `GOOGLE_API_KEY` | Places API (New): location lookup + nearby places | P4 onward |

> **Keep keys secret.** Only put them in `.env` (already git-ignored). Never commit them, paste them in chat, or put them in code. In production they go into Google Secret Manager (P10).
>
> Dashboard menus change from time to time; if a label below doesn't match exactly, look for the closest equivalent.

---

## 1. Anthropic API key

1. Go to **https://platform.claude.com** and sign up / log in.
2. **Add credits:** Settings → **Billing** → add a payment method and buy a small amount of credit (a few dollars is plenty for development — Claude Haiku 5.5 costs $0.10 per million input tokens and $0.50 per million output tokens).
3. *(Recommended)* **Set a spend limit:** Settings → **Limits** → set a monthly limit so a bug can't run up a bill.
4. **Create the key:** Settings → **API Keys** → **Create Key** → name it e.g. `ai-makan-agent-dev`.
5. Copy the key (starts with `sk-ant-`). It is shown **only once**.
6. Paste it into `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### Check it works

```bash
set -a; source .env; set +a
curl -s https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" | head -c 300; echo
```

A JSON list of models means the key works. `authentication_error` means the key is wrong.

Then run the real-model evals:

```bash
make eval
```

---

## 2. Google Places API key

### 2.1 Create a project and enable billing

1. Go to **https://console.cloud.google.com** and log in.
2. Top bar project picker → **New Project** → name it e.g. `ai-makan-agent` → **Create**. Make sure it is selected.
3. **Billing:** ☰ menu → **Billing** → link a billing account to the project. Google Maps Platform requires billing even when your usage stays within the free monthly allowance.

### 2.2 Enable Places API (New)

1. ☰ → **APIs & Services** → **Library**.
2. Search **"Places API (New)"** → open it → **Enable**.
   - Pick **Places API (New)**, *not* the older "Places API". The code calls `places.googleapis.com/v1/...`, which only the new one serves.

### 2.3 Create and restrict the key

1. ☰ → **APIs & Services** → **Credentials** → **+ Create credentials** → **API key**.
2. Click the new key to **edit** it:
   - **Name:** `ai-makan-agent-server`
   - **API restrictions:** select **Restrict key** → tick only **Places API (New)** → Save.
   - **Application restrictions:** leave as **None**. The key is used server-side, and Cloud Run has no fixed outgoing IP, so an IP restriction would break it. The API restriction above plus keeping the key secret is the protection.
3. Copy the key (starts with `AIza`) into `.env`:
   ```
   GOOGLE_API_KEY=AIza...
   ```

### 2.4 Protect against surprise bills (recommended)

- **Budget alert:** ☰ → **Billing** → **Budgets & alerts** → **Create budget** → e.g. a small monthly amount with email alerts at 50% / 90% / 100%.
- **Quota cap:** ☰ → **APIs & Services** → **Places API (New)** → **Quotas & System Limits** → lower *requests per day* (e.g. 500 for development). Calls beyond the cap fail instead of costing money.

The app also keeps costs down itself: it asks Google only for basic fields (field mask) and caches results for 7 days, shared across users (see `docs/specs/08-cost-safety-privacy.md`).

### Check it works

```bash
set -a; source .env; set +a
curl -s -X POST https://places.googleapis.com/v1/places:searchText \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $GOOGLE_API_KEY" \
  -H "X-Goog-FieldMask: places.displayName,places.formattedAddress" \
  -d '{"textQuery": "nasi lemak in Bangsar"}' | head -c 400; echo
```

A JSON list of places means the key works. Common errors:

| Error | Fix |
|---|---|
| `API_KEY_INVALID` | Key copied wrong, or deleted. |
| `PERMISSION_DENIED` … *Places API (New) has not been used / is disabled* | Enable **Places API (New)** (step 2.2) and wait a minute. |
| `PERMISSION_DENIED` … *requests to this API are blocked* | The key's API restriction doesn't include Places API (New) (step 2.3). |
| `BILLING_DISABLED` | Link a billing account to the project (step 2.1). |

---

## After adding both keys

```bash
make dev    # restart so the app picks up the new .env
make eval   # real-model LLM evals
```

Tell Claude the keys are in place: it will check that they are **set** without printing them.
