# Investor — DCF Stock Valuation App

A stock valuation web app built with Python, [yfinance](https://github.com/ranaroussi/yfinance), and [Streamlit](https://streamlit.io). Financial data is pulled automatically from Yahoo Finance — no API key required.

Three valuation models across three tabs:

| Tab | Model |
|---|---|
| **Simple DCF** | FCF-based DCF with linear growth decline |
| **Three-Phase DCF** | ROIC-based DCF (Damodaran): invest → scale → mature |
| **Reverse DCF** | Solve for the implied near-term growth rate priced into the market |

## Requirements

- [UV](https://github.com/astral-sh/uv) (Python package manager)
- Python 3.12+

## Setup

```bash
git clone git@github.com:supercoolname/investor.git
cd investor
uv sync
```

## Run

```bash
uv run streamlit run main.py
```

Open `http://localhost:8501` in your browser. Also accessible on the local network at the **Network URL** printed in the terminal.

## Usage

Each tab has its own ticker input. Enter a ticker (e.g. `AAPL`, `MSFT`, `TSLA`), click **Load**, adjust the parameters, and click **Calculate**.

---

## Models

### Simple DCF

Standard FCF-based discounted cash flow. Growth declines linearly from the near-term rate to the terminal rate.

$$P = \sum_{t=1}^{n} \frac{FCF_t}{(1+r)^t} + \frac{TV}{(1+r)^n} - \text{Net Debt}$$

| Symbol | Description |
|---|---|
| FCF₀ | Base Free Cash Flow (most recent annual) |
| FCF_t | FCF₀ × (1 + g_t), g_t declines linearly to g∞ |
| g | Near-term growth rate (year 1) |
| g∞ | Terminal growth rate (perpetual) |
| TV | FCF_n × (1 + g∞) / (r − g∞) |
| r | WACC — Discount Rate |
| n | Forecast years |

**Outputs:** intrinsic value per share, margin of safety, year-by-year FCF table, sensitivity simulation.

---

### Three-Phase DCF (Damodaran ROIC model)

Growth requires reinvestment. Each year:

$$\text{Reinvestment Rate}_t = \frac{g_t}{\text{ROIC}_t}, \quad \text{Derived FCF}_t = NOPAT_t \times \left(1 - \frac{g_t}{\text{ROIC}_t}\right)$$

ROIC evolves across three phases:

| Phase | ROIC |
|---|---|
| Investment | Ramps linearly from ROIC_invest → ROIC_peak |
| Scale | Constant at ROIC_peak |
| Mature | Decays linearly from ROIC_peak → WACC |

When FCF_t < 0 (growth exceeds ROIC), the shortfall is funded by equity issuance at the current market price, diluting existing shareholders.

#### NOPAT₀ Resolution (`resolve_nopat`)

NOPAT₀ (base after-tax operating earnings) is resolved from Yahoo Finance data using a fallback chain:

| Priority | Source | Used when |
|---|---|---|
| 1 | EBIT × (1 − effective tax rate) | Preferred — pre-interest, after-tax operating earnings |
| 2 | Operating Cash Flow | EBIT unavailable |
| 3 | FCF (Op CF − CapEx) | Last resort |

#### SBC and Acquisitions

**Stock-Based Compensation (SBC):** SBC is fetched and displayed in the stock info panel, but is *not* deducted from NOPAT₀. Damodaran treats SBC as a real economic cost; strictly speaking, NOPAT₀ should be reduced by SBC to avoid overstating earnings for compensation-heavy companies. The mechanical dilution model (new shares issued when Derived FCF < 0) does not substitute for this adjustment.
do both share dilute and SBC as operating expenses can double count

**Acquisitions:** Future acquisitions are excluded from the model by design, consistent with Damodaran's approach. The reinvestment rate (`g / ROIC`) captures only organic reinvestment (capex + working capital). If a company is a serial acquirer, its historical ROIC already reflects the returns of past deals.

**Outputs:** intrinsic value per diluted share, year-by-year breakdown table (NOPAT, reinvestment, derived FCF, dilution), DCF summary, sensitivity analysis.

#### Other unresolved inssues
1. Dynamic WACC (The Risk Glide-Path)
In your model, WACC is a static input for the entire forecast. Damodaran argues that a company's risk profile changes alongside its ROIC.
A hyper-growth startup in Phase 1 is highly risky (e.g., WACC of 12% to 15%). As it matures into a stable, moaty enterprise in Phase 3, its risk profile drops to the market average (e.g., WACC of 7% to 8%). Just as you linearly decay ROIC in the mature phase, Damodaran linearly decays WACC down to a "mature cost of capital." If you leave WACC static at 12% in perpetuity, you will massively undervalue the terminal phase.

2. Revenue Growth + Margin Expansion (vs. NOPAT Growth)
Your model applies g_t directly to NOPAT. This works fine for an established company like Apple that already has stable margins.
However, for an early-stage company, NOPAT might be negative or near-zero. If you apply a 30% growth rate to a negative NOPAT, it just becomes more negative. High-growth companies scale by growing Revenue exponentially while their Operating Margins expand from negative to positive. Damodaran models Revenue growth and applies a "Target Operating Margin" that phases in over time. NOPAT is a byproduct of those two curves crossing, not a direct growth input.

3. Sales-to-Capital Ratio in Phase 1You calculate reinvestment as $g / ROIC$. If an early-stage company has a 2% ROIC and is growing at 40%, your formula demands a reinvestment rate of 2000%.To prevent these insane reinvestment spikes when ROIC is near zero, Damodaran uses the Sales-to-Capital ratio for Phase 1. Instead of linking reinvestment to ROIC, he links it to revenue generation: How many dollars of capex/working capital must be spent to generate $1 of new revenue? He only switches to the $g / ROIC$ math once the company's margins stabilize in Phase 2 or 3.

4. Probability of Failure
Standard DCFs assume the company has a 100% chance of surviving to Year 10. Young, high-growth companies do not. Damodaran explicitly calculates the present value of the company as a going concern, and then applies a discrete probability of failure (e.g., a 20% chance the company goes bankrupt, returning 0 or a distressed liquidation value).



---

### Reverse DCF

Given the current market price, numerically solves for the near-term FCF growth rate the market is pricing in.

$$P_\text{market} = \sum_{t=1}^{n} \frac{FCF_0 \cdot (1+g_t)}{(1+r)^t} + \frac{TV(g)}{(1+r)^n} - \frac{\text{Net Debt}}{\text{Shares}}$$

Uses `scipy.optimize.brentq` over g ∈ [−50%, 100%].

**Outputs:** implied near-term growth rate, sensitivity table of implied g across discount rates.

---

## Architecture

```
main.py                     # Streamlit entry point, tab routing
datasource/
  fetcher.py                # yfinance wrapper → FinancialData dataclass
models/
  simple_dcf_model.py       # Pure numeric FCF DCF
  damodaran_dcf_model.py    # Pure numeric ROIC DCF (three phases)
apps/
  dcf_app.py                # Simple DCF: business logic + formatting
  damodaran_dcf_app.py      # Three-phase DCF: orchestration + sensitivity
  reverse_dcf_app.py        # Reverse DCF: brentq solver
ui/
  simple_dcf_tab.py
  three_phase_dcf_tab.py
  reverse_dcf_tab.py
  utils.py                  # Shared formatting helpers
```
