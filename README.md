# Fraud Transaction Detection — Streamlit Application

An AI-powered tool for detecting fraudulent financial transactions using an ensemble of XGBoost, Random Forest, and Isolation Forest models.

## Problem

Financial fraud costs institutions billions annually. This application provides a screening tool that scores individual transactions for fraud probability, enabling analysts to prioritize investigations.

## Features

- **🔐 Mandatory Login (Security Gate)** — the whole system sits behind a password gate; nothing renders until you sign in. Passwords are salted + hashed (PBKDF2-HMAC-SHA256), failed attempts are rate-limited (5 tries → 30s lock), and every login attempt is written to `login_log.csv`
- **🔑 Forgot Password** — verify identity by answering 3 security questions, then set a new password (questions are hashed, managed per-account via `manage_users.py setup-security`)
- **Upload CSV** — score thousands of transactions in bulk (multiple files accepted)
- **Manual Entry** — Score a single transaction interactively
- **Risk Classification** — CRITICAL / HIGH / MEDIUM / LOW / MINIMAL
- **Visual Dashboard** — Histograms, box plots, pie charts of results
- **Adjustable Threshold** — Tune sensitivity via sidebar slider
- **Multi-Currency** — Set the working currency in the sidebar (16 currencies); inputs are converted to USD for model scoring, results are displayed back in your chosen currency
- **Export Results** — Download flagged transactions as CSV
- **Model Analytics** — View feature importance, per-model comparison, confusion matrix, ROC-AUC, and an auto-generated interpretation
- **Automated Audit Trail** — every decision is logged with risk score, rules triggered, AI reasoning, data used, action taken, and space for an investigator's decision and final outcome
- **🔎 Review Queue** — a dedicated tab that lists every flagged transaction (from the audit trail) with status (Pending/Decided), filters, per-case AI reasoning + rules, and one-click actions to record an investigator decision and final outcome — persisted back to the audit log
- **Flagged Fraud Summary** — after scoring a batch, an executive summary of the detected fraud: risk-level counts, the rules that fired most, fraud concentration by category/channel, behaviour signals, and an auto-generated plain-language explanation of **why** each pattern was flagged (computed from the actual batch, not templates)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| ML Models | XGBoost, LightGBM, scikit-learn, imbalanced-learn |
| Visualization | Plotly |
| Data | Pandas, NumPy |

## Project Structure

```
fraud-detection-app/
├── app.py                 # Main Streamlit application
├── auth.py                # Authentication & access control (login gate)
├── manage_users.py        # CLI to add / list / reset-password / remove accounts
├── model.py               # ML model training, prediction, feature engineering
├── audit_trail.py         # Automated audit trail (append-only decision log)
├── fraud_summary.py       # Flagged-fraud summary & reasoning generator
├── generate_data.py       # Synthetic transaction data generator
├── test_app.py            # Pytest test suite (normal + edge cases + audit)
├── test_auth.py           # Pytest tests for the auth module
├── test_fraud_summary.py  # Pytest tests for the fraud-summary module
├── test_app_native.py     # Streamlit AppTest functional checks
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── saved_models/          # Saved model artifacts (auto-generated)
│   └── fraud_model.joblib
├── audit_log.csv          # Runtime audit log (auto-created, git-ignored)
└── login_log.csv          # Login attempts log (auto-created, git-ignored)
```

## Setup & Installation

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/<your-username>/fraud-detection-app.git
cd fraud-detection-app
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
streamlit run app.py
```

5. Open http://localhost:8501 in your browser.

6. **Sign in** — required before the system will render:

| Account | Password | Role |
|---------|----------|------|
| `admin` | `admin123` | Administrator (full access) |
| `analyst` | `analyst123` | Analyst |

> The default seed accounts are created automatically on first login. **Change the
> passwords before real-world use** — see [Security & Account Management](#security--account-management).

## Security & Account Management

The application is fully gated: without a valid login you only see the sign-in card — no
charts, no data, no audit log is ever rendered.

- **Password storage**: PBKDF2-HMAC-SHA256 with a random per-user salt (200,000 iterations).
  Plain-text passwords are never written to disk.
- **Forgot Password dashboard**: pick **🔑 Forgot Password** on the sign-in card — you must
  answer the 3 security questions configured for your account before a new password is
  accepted. Seed accounts ship with demo questions (answers `dog`, `mashava`,
  `great zimbabwe`); replace them per account via `python manage_users.py setup-security
  <username>`. Answers are hashed and matched leniently (case-insensitive, trim).
- **Rate limiting**: 5 failed attempts locks the session for 30 seconds (per browser session).
- **Login audit log**: every successful and failed attempt is appended to `login_log.csv`
  (UTC timestamp, username, outcome, reason).
- **Account store**: `users.json` (git-ignored). Manage it from the terminal:

```bash
python manage_users.py init                  # ensure the default demo accounts
python manage_users.py list                  # show all accounts & roles
python manage_users.py add alice             # create a new analyst account
python manage_users.py setup-security alice  # set alice's 3 forgot-password questions
python manage_users.py reset-password admin  # change a password
python manage_users.py remove carol          # delete an account
```

> The seeded demo accounts come pre-configured with 3 security questions. Their demo
> answers are `dog`, `mashava`, `great zimbabwe` (shown on the login card). To try the
> forgot-password flow immediately: switch the login card to **🔑 Forgot Password**, enter
> `admin`, load the questions, answer with those values, then set a new password.

> Passwords are entered in hidden mode; never type them into logs or the chat.

### Running Tests

```bash
pytest test_app.py          # unit tests: data, model, prediction, edge cases, audit trail, currency
pytest test_auth.py         # unit tests: password hashing, users, security questions, login log
pytest test_fraud_summary.py  # unit tests: flagged-fraud summary & reasoning generator
python test_app_native.py   # functional AppTest checks incl. the security gate & login/logout
```

> Note: `saved_models/fraud_model.joblib` is committed so the deployed app starts instantly. It was
> trained with the v3 5-model stack (XGBoost + LightGBM + Random Forest + Neural Net + Isolation
> Forest) and regenerates via the **🔄 Retrain Model** button if you ever retrain.

## How It Works

1. **Data Input**: User uploads one or more CSVs (combined into a single batch, each file keeps its own audit source) or enters a single transaction manually.
2. **Currency Normalisation**: Input amounts and balances are converted from the sidebar-selected currency (default USD) to USD using static reference rates, since the model is trained on USD-denominated data.
3. **Feature Engineering**: 12+ derived features are computed (amount ratios, time flags, cyclical hour encoding, overdraft flags, balances, etc.).
4. **Ensemble Scoring**: A modern 5-model ensemble produces the final fraud score:
   - XGBoost (30% weight) — gradient-boosted trees
   - LightGBM (25% weight) — fast leaf-wise gradient boosting
   - Random Forest (15% weight) — bagged trees
   - Neural Network MLP (10% weight) — non-linear feature interactions
   - Isolation Forest (20% weight) — unsupervised anomaly detection
   - Each member's individual vote is surfaced in the results (`score_xgb`, `score_lgbm`, `score_rf`, `score_nn`, `score_iso` columns) and compared in the Analytics tab.
5. **Threshold Application**: Final ensemble score compared against user-set threshold (default 0.5).
6. **Risk Classification**: Score mapped to CRITICAL (≥0.8), HIGH (≥0.6), MEDIUM (≥0.4), LOW (≥0.2), MINIMAL (<0.2).
7. **Local Currency Display**: Results (table, metrics, charts) are converted back to the working currency, so the analyst sees familiar numbers while the model scores in USD.
8. **Audit Trail**: Every decision — from both CSV batch and manual entry — is automatically recorded to `audit_log.csv` with the risk score, business rules triggered, AI reasoning, data used (including original currency and USD equivalent), and the action taken. Investigators review flagged transactions and can record their decision and the final outcome.

### Audit Trail Columns

| Column | Description |
|--------|-------------|
| `transaction_id` | Unique identifier of the scored transaction |
| `date_time` | UTC timestamp of the decision |
| `risk_score` | Model fraud probability (0–1) |
| `rules_triggered` | Human-readable business rules that fired |
| `ai_reasoning` | Plain-English explanation of the model's score |
| `data_used` | JSON: input source, channel, type, amount |
| `action_taken` | System action (flagged for review / cleared) |
| `investigator_decision` | Human verdict (filled via the Audit Trail tab) |
| `final_outcome` | Closed-loop outcome of the case |

## Assumptions

- Fraud rate is ~3% of all transactions (industry average)
- Fraudulent transactions tend to have higher amounts, occur at night, and involve international/online channels
- Training data is synthetically generated and mirrors realistic patterns
- No real PII or financial data is used anywhere in the application

## Data Sources

All data is **synthetically generated** via `generate_data.py`. No real financial records, API keys, or personal data are used.

### Example CSV files (ready to upload)

Pre-made example files in `data/` that match the app's expected schema:

| File | Scenario | What to look for |
|------|----------|------------------|
| `example_retail_spending.csv` | Everyday consumer spending (POS/Mobile/ATM) | `RET1021` — $5,000 jewellery bought online internationally at 03:00 → CRITICAL |
| `example_corporate_expenses.csv` | Business expenses & vendor payments | `COR1019` — large overnight international purchase exceeding balance → CRITICAL |
| `example_cross_border.csv` | International & online-heavy card | Higher flag rate (~20%) — several CRITICAL overnight international transfers |

Upload one, or select several at once and they are combined into a single scored batch.

## Limitations

- Synthetic data may not capture all real-world fraud patterns
- Model requires periodic retraining on fresh, real-world data
- No account-level behavioral baselines (each transaction is scored independently)
- No real-time streaming capability in this version

## Deployment

### Streamlit Community Cloud

1. Push this repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Select `app.py` as the main file
5. Deploy — the app will be live at `https://<your-app>.streamlit.app`

> On deployment, the security files behave as follows: `auth.py` and `manage_users.py` are
> committed; `users.json` and `login_log.csv` are **git-ignored** and auto-created on the
> cloud instance the first time someone logs in (fresh seed accounts `admin`/`admin123`).
> Remember to push `auth.py`, `manage_users.py`, and the latest `app.py`/`model.py`/
> `requirements.txt`/`saved_models/fraud_model.joblib` to GitHub `main` to deploy this
> security gate.

## License

This project is for educational purposes (HBF2212 — Artificial Intelligence in Finance).
