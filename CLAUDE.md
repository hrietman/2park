# 2Park Home Assistant Integration

## Project Overview

Custom Home Assistant integration for **2Park** (mijn.2park.nl), Breda's municipal parking permit management system. Designed for HACS distribution.

## What 2Park Does

- **Visitor parking registration** — register guest vehicles with license plate, start/end time
- **Balance management** — track remaining credit (EUR) for visitor parking
- **License plate management** — manage plates on resident permits
- **Favorites** — store frequent visitor plates with nicknames
- **Action history** — view past parking sessions and balance mutations

## Project Structure

```
custom_components/2park/    # HA integration code
  __init__.py               # Integration entry point
  const.py                  # Constants
  manifest.json             # HA manifest
config/                     # HA dev instance config
.devcontainer/              # VS Code devcontainer
hacs.json                   # HACS metadata
```

## Development

- **IDE**: VS Code with devcontainer
- **Run HA**: `hass -c /workspaces/2park/config` (inside devcontainer)
- **HA UI**: http://localhost:8123
- **Python**: 3.12+

---

# 2Park REST API Reference (Reverse Engineered)

## Base URL & Conventions

- **Base URL**: `https://mijn.2park.nl`
- **API prefix**: `/gsmpark-app-www/json/`
- **Content-Type**: `application/x-www-form-urlencoded` (all POST requests)
- **Response Content-Type**: `application/json;charset=UTF-8`
- **Session management**: `JSESSIONID` cookie. Login (`check_credentials.json`) returns `Set-Cookie: JSESSIONID=...` (HttpOnly). Every subsequent request must send `Cookie: JSESSIONID=...`. A new JSESSIONID is issued per login session. Use `aiohttp.ClientSession` which handles this automatically via its built-in cookie jar.
- **Locale parameter**: `nl_NL` sent with virtually every request.
- **Datetime format**: `dd-MM-yyyy HH:mm:ss` (e.g., `20-02-2026 18:15:00`)

### Standard Response Envelope

```json
{
  "status": {
    "code": {
      "major": "OK",       // or "ERROR"
      "minor": "SUCCESS"   // or "AUTHENTICATED", "PRK-00000", etc.
    },
    "message": "Gelukt"    // human-readable Dutch
  },
  "data": { ... }
}
```

### Product ID Format

`{TYPE}_{LOCATION_ID}${ACCOUNT_ID}`

- `BDABZRG_1317$1055649` = Bezoekersregeling (visitor scheme)
- `BDATKTKBH_1317$1053327` = Bewoner Basisvergunning (resident permit)
- `BDA` prefix = Breda

### Member Types

- `LPN` = License Plate Number (changeable, visitors)
- `FLPN` = Fixed License Plate Number (permanent, resident's own car)

### Parameter Data Types

- `LPN` = License plate
- `DATETIME` = `dd-MM-yyyy HH:mm:ss`
- `MONEY` = Decimal string (e.g., `"19.20"`)
- `TEXT` = Free text
- `DIGIT4` = 4-digit PIN code

---

## Endpoints

### 1. POST check_credentials.json — Login

**Form parameters:**
| Parameter  | Example                   |
|-----------|---------------------------|
| `email`   | `user@example.com`        |
| `password`| `plaintext_password`      |
| `locale`  | `nl_NL`                   |

**Response:**
```json
{
  "status": { "code": { "major": "OK", "minor": "AUTHENTICATED" } },
  "data": {
    "userinfo": { "email": "u***@***l.com" }
  }
}
```

### 2. POST get_categories.json — Get Products

Returns all parking categories and products (permits) for the authenticated user.

**Form parameters:** `locale=nl_NL`

**Response:**
```json
{
  "data": {
    "categories": [
      {
        "cty_id": "22",
        "cty_name": "Breda",
        "cty_description": "Gemeente Breda",
        "cty_external_content": "breda",
        "cty_products": [
          {
            "pdt_id": "BDATKTKBH_1317$1053327",
            "pdt_name": "Bewoner Basisvergunning Huishouden - Boeimeer",
            "pdt_valid_from": "2026-02-09 00:00",
            "pdt_valid_to": "2026-12-31 23:59",
            "pdt_is_blocked": "false",
            "pdt_member_pool_max_registered": "20",
            "pdt_member_pool_max_active": "1",
            "pdt_options": "MEMBER_ADMIN|FLPN",
            "pdt_parameter_groups": [ ... ]
          },
          {
            "pdt_id": "BDABZRG_1317$1055649",
            "pdt_name": "Bezoekersregeling Straat - Boeimeer",
            "pdt_valid_from": "2026-02-09 00:00",
            "pdt_valid_to": "2076-02-08 23:59",
            "pdt_member_pool_max_active": "10",
            "pdt_options": "EXTEND|MEMBER_ADMIN",
            "pdt_parameter_groups": [ ... ]
          }
        ]
      }
    ]
  }
}
```

**Product options flags:** `MEMBER_ADMIN` = can manage members, `FLPN` = fixed license plate, `EXTEND` = can extend sessions.

**Parameter groups** define available actions per product: `START` (start parking), `FAVORITE` (add favorite), `ADD_PRODUCT`, `APK_REGISTER_KEY`, etc. The `START` group defines required fields: `MBR_IDENT` (license plate, required), `TIMESTART` (required), `TIMEEND` (optional), `LOCATION` (readonly, default e.g., `BDA1317`).

### 3. POST get_category_product_details.json — Product Details

Returns members (license plates), active actions, grants, and identifications for a product.

**Form parameters:** `product_id=BDABZRG_1317$1055649&locale=nl_NL`

**Response (visitor scheme):**
```json
{
  "data": {
    "pdt_id": "BDABZRG_1317$1055649",
    "pdt_action_history_count": "4",
    "pdt_grants": [],
    "pdt_members": [
      {
        "mbr_id": "4113678",
        "mbr_identifier": "HRL96K",
        "mbr_type": "LPN",
        "mbr_active": "NO",
        "mbr_parameters": [
          { "prr_label": "NICKNAME", "prr_value": "Mats" }
        ],
        "mbr_actions": []
      }
    ],
    "pdt_identifications": []
  }
}
```

**Response (resident permit)** additionally includes `pdt_identifications` linking physical identification to members (with both `LPN` and `FLPN` types).

- `mbr_active`: `YES`/`NO` — whether currently parked
- `mbr_actions`: Array of active parking actions (populated when parked)

### 4. POST get_balance.json — Get Balance

**Form parameters:** `product_id=BDABZRG_1317$1055649&locale=nl_NL`

**Response:**
```json
{
  "data": {
    "balance": {
      "ble_parameters": [
        { "prr_label": "AMOUNT", "prr_value": "19.20", "prr_datatype": "MONEY" },
        { "prr_label": "CURRENCY_CODE", "prr_value": "EURO" },
        { "prr_label": "CURRENCY_DESC", "prr_value": "€" },
        { "prr_label": "LAST_MODIFIED", "prr_value": "19-02-2026 15:21:14", "prr_datatype": "DATETIME" }
      ]
    }
  }
}
```

### 5. POST start_action.json — Start Parking

**Form parameters:** `product_id`, `locale`, and `data` (URL-encoded JSON):

```json
{
  "action": {
    "atn_parameters": [
      { "prr_label": "MBR_IDENT", "prr_value": "HRL96K" },
      { "prr_label": "TIMESTART", "prr_value": "20-02-2026 18:15:00" },
      { "prr_label": "TIMEEND", "prr_value": "20-02-2026 23:59:59" },
      { "prr_label": "LOCATION", "prr_value": "BDA1317" }
    ]
  }
}
```

**Response:**
```json
{
  "status": { "code": { "major": "OK", "minor": "PRK-00000" } },
  "data": {
    "alternates": [
      {
        "action": {
          "atn_parameters": [
            { "prr_label": "PRODUCT_ID", "prr_value": "BDABZRG_1317" },
            { "prr_label": "TIMESTART", "prr_value": "20-02-2026 18:15:26" },
            { "prr_label": "TIMEEND", "prr_value": "20-02-2026 23:59:59" },
            { "prr_label": "AMOUNT", "prr_value": "0.94", "prr_datatype": "MONEY" }
          ]
        }
      }
    ]
  }
}
```

- Success code: `PRK-00000`
- Returns estimated cost in `AMOUNT`

### 6. POST stop_action.json — Stop Parking

**Form parameters:** `action_id=19244245&product_id=BDABZRG_1317$1055649&locale=nl_NL`

**Response:** Standard success envelope (no data payload).

### 7. POST handle_favorite.json — Manage Favorites

**Form parameters:** `product_id`, `locale`, and `data` (URL-encoded JSON):

```json
{
  "favorite": {
    "fav_parameters": [
      { "prr_label": "NICKNAME", "prr_value": "Mats" }
    ],
    "action": "add",
    "mbr_ident": "HRL96K"
  }
}
```

- `action`: `"add"` (presumably `"remove"` to delete)

### 8. POST get_action_history.json — Parking History

**Form parameters:** `product_id`, `locale`, `startindex=0`, `stopindex=10` (0-based pagination)

**Response:**
```json
{
  "data": {
    "startindex": "0",
    "stopindex": "3",
    "maxindex": "4",
    "headers": [ ... ],
    "actions": [
      {
        "atn_state": "COMPLETED",
        "atn_id": "19227774",
        "atn_chained": "NO",
        "atn_parameters": [
          { "prr_label": "MBR_IDENT", "prr_value": "HRL96K" },
          { "prr_label": "TIMESTART", "prr_value": "19-02-2026 15:21:14" },
          { "prr_label": "TIMEEND", "prr_value": "19-02-2026 15:25:00" },
          { "prr_label": "LOCATION", "prr_value": "BDA Boeimeer" },
          { "prr_label": "COST", "prr_value": "0.02" },
          { "prr_label": "CURRENCY_DESC", "prr_value": "€" }
        ]
      }
    ]
  }
}
```

- `atn_state`: `COMPLETED` or `ACTIVE`

### 9. POST get_mutation_history.json — Balance History

**Form parameters:** `product_id`, `locale`, `startindex=1`, `stopindex=10` (**1-based** pagination)

**Response:** Contains `mutations` array with entries:
- `Afboeking` = Debit (negative amount, parking cost)
- `Bijboeking` = Credit (positive amount, top-up, has `PAYMENT_REFERENCE`)
- `Startsaldo` = Initial balance

### 10. POST get_activations.json — Active Sessions

**Form parameters:** None (empty body, uses session)

**Response:**
```json
{
  "data": {
    "categories": []
  }
}
```

Returns all active parking sessions across all products (empty when none active).

### 11. GET version.json — Version Check

**Response:** `{ "env": "" }` (empty = production)

---

## API Call Flows

### Login
1. `check_credentials.json` → authenticate
2. `get_categories.json` → get all products
3. For each product: `get_category_product_details.json` + `get_balance.json`

### Start Parking
1. `start_action.json` → start session (returns estimated cost)
2. Optionally `handle_favorite.json` → save plate
3. `get_category_product_details.json` + `get_balance.json` → refresh state

### Stop Parking
1. `stop_action.json` (with `action_id`)
2. `get_category_product_details.json` + `get_balance.json` → refresh state

---

## Integration Design Notes

- Use `aiohttp.ClientSession` with persistent connection for session management
- Poll `get_category_product_details.json` + `get_balance.json` for sensor updates
- Expose sensors: balance (EUR), active parking count, active plates
- Expose services: start_parking, stop_parking
- Config flow: email + password credentials
