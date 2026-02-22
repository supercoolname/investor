# Investor — DCF Stock Valuation App

A Discounted Cash Flow (DCF) stock valuation web app built with Python, [yfinance](https://github.com/ranaroussi/yfinance), and [Streamlit](https://streamlit.io). Financial data is pulled automatically from Yahoo Finance — no API key required.

## Requirements

- [UV](https://github.com/astral-sh/uv) (Python package manager)
- Python 3.12+

## Setup

Clone the repository and install dependencies:

```bash
git clone git@github.com:supercoolname/investor.git
cd investor
uv sync
```

## Starting the App

```bash
uv run streamlit run main.py
```

## Accessing the App Locally

Once started, open your browser and go to:

```
http://localhost:8501
```

The app is also accessible from other devices on the same network at the **Network URL** printed in the terminal (e.g. `http://192.168.x.x:8501`).

## Usage

1. Enter a **ticker symbol** in the sidebar (e.g. `AAPL`, `MSFT`, `TSLA`)
2. Adjust the DCF parameters:
   - **g** — Near-term Growth Rate (%)
   - **g∞** — Terminal Growth Rate (%)
   - **r** — WACC / Discount Rate (%)
   - **n** — Forecast Years
3. Click **Calculate Intrinsic Value**

## What the App Shows

| Section | Description |
|---|---|
| Raw Data (from Yahoo Finance) | FCF₀, Net Debt, Shares Outstanding, Market Data |
| Formula & Assumptions | DCF formula with the exact values used |
| Intrinsic Value vs Current Price | Key valuation metrics and margin of safety |
| Value Breakdown | Bar chart of PV of FCFs vs Terminal Value |
| Year-by-Year FCF Breakdown | Projected FCF and discounted values per year |
| DCF Summary | Full step-by-step calculation table |

## DCF Model

$$P = \sum_{t=1}^{n} \frac{FCF_t}{(1+r)^t} + \frac{TV}{(1+r)^n} - \text{Net Debt}$$

| Symbol | Description |
|---|---|
| FCF₀ | Base Free Cash Flow (most recent annual) |
| FCF_t | FCF₀ × (1 + g)^t |
| g | Near-term Growth Rate |
| g∞ | Terminal Growth Rate (perpetual) |
| TV | Terminal Value = FCF_n × (1 + g∞) / (r − g∞) |
| r | WACC — Discount Rate |
| n | Forecast Years |
