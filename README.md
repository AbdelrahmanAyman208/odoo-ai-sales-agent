# Odoo AI Sales & Operations Copilot (`sale_ai_agent`)

> **Autonomous AI operations agent for Odoo ERP.**  
> Automates sales quotations, CRM lead follow-ups, RFQs, smart inventory replenishment, supplier offer analysis, composite product BOM generation, and live interactive chat via LLM tool-calling.

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20%7C%2018.0%20%7C%2020.0-purple.svg)](https://www.odoo.com/)
[![License](https://img.shields.io/badge/License-LGPL--3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)

---

## 🚀 Key Features

### 1. 💬 Interactive AI Agent Assistant
- Floating / dedicated **AI Agent Chat Wizard** accessible right from Odoo menus.
- Supports multi-turn conversations with autonomous tool-execution and reasoning loops.
- Live responses with direct links to generated orders, quotes, and products.

### 2. 📑 Intelligent Sales & Quotation Management
- Create draft sales quotes automatically from customer instructions.
- Auto-match existing customers or create new contacts on the fly.
- Smart line-item matching against product catalog with pricing and taxes.
- Send customized follow-up emails for pipeline opportunities.

### 3. 📦 Inventory Tracking & Auto-Replenishment
- Scan for low-stock items across warehouses against configured thresholds.
- Compute reorder requirements and generate automated replenishment purchase orders.
- Check real-time stock levels, quantities on hand, and forecasted quantities.

### 4. 🏢 RFQ Broadcast & Supplier Operations
- Broadcast Requests for Quotation (RFQs) to all qualified suppliers simultaneously.
- Manage vendor lead times, unit costs, and purchase orders.

### 5. 📊 Vendor Offer & Price Analysis
- Automatically compare competing vendor quotations to find the lowest price and highest cost savings.
- Analyze vendor delivery dates, quantities, and terms with summary reporting.

### 6. 🧩 Composite Product & Bill of Materials (BOM) Generation
- Automatically create assembled kit/composite products.
- Configure component Bill of Materials and automatically calculate combined product costs.

### 7. 🔒 Audit Trails & Execution Logs
- Every tool call and AI operation is recorded in `ai.agent.log`.
- Tracks timestamps, user identity, function arguments, execution status, and LLM reasoning.

---

## 🤖 Supported AI Providers

Configurable via **Settings ➔ Sales / General Settings ➔ AI Agent**:

| Provider | Supported Models | Description |
| :--- | :--- | :--- |
| **OpenAI Compatible** | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` | Direct OpenAI API or custom endpoints |
| **OpenRouter / Groq** | `meta-llama/*`, `deepseek/*`, `mistralai/*` | Cost-effective and ultra-fast inference |
| **Anthropic Claude** | `claude-3-7-sonnet`, `claude-3-5-sonnet` | Native Claude support with tool calling |
| **Google Gemini** | `gemini-2.0-flash`, `gemini-1.5-pro` | High context window and fast tool calling |
| **Local LLMs** | Ollama, vLLM, LMStudio | Connect locally via OpenAI-compatible endpoint |

---

## 📦 Installation & Setup

### 1. Add to your Odoo Addons Path
Clone this repository or place the `custom_addons/sale_ai_agent` folder into your custom addons directory:

```bash
git clone https://github.com/AbdelrahmanAyman208/odoo-ai-sales-agent.git
```

In your `odoo.conf`:
```ini
addons_path = /path/to/custom_addons, /path/to/odoo/addons
```

### 2. Update Apps & Install
1. Start your Odoo server with `-u sale_ai_agent` or activate **Developer Mode** in the Odoo web interface.
2. Navigate to **Apps ➔ Update Apps List**.
3. Search for **AI Agent** (`sale_ai_agent`) and click **Install / Activate**.

### 3. Configure API Credentials
1. Go to **Settings ➔ AI Agent Settings** (or find under Sales settings).
2. Choose your **AI Provider** (`OpenAI Compatible`, `Anthropic`, or `Gemini`).
3. Enter your **API Key** and desired **Model**.
4. *(Optional)* Fine-tune the temperature or customize the **System Prompt**.

---

## 📁 Repository Structure

```text
├── custom_addons/
│   └── sale_ai_agent/
│       ├── __init__.py
│       ├── __manifest__.py
│       ├── models/
│       │   ├── ai_agent_log.py
│       │   ├── ai_agent_service.py
│       │   ├── ai_tools.py
│       │   ├── crm_lead.py
│       │   ├── product_template.py
│       │   ├── res_config_settings.py
│       │   └── sale_order.py
│       ├── security/
│       │   └── ir.access.csv
│       ├── tests/
│       │   └── test_ai_agent.py
│       ├── views/
│       │   ├── ai_agent_log_views.xml
│       │   ├── crm_lead_views.xml
│       │   ├── menu_views.xml
│       │   ├── product_template_views.xml
│       │   ├── res_config_settings_views.xml
│       │   └── sale_order_views.xml
│       └── wizard/
│           ├── ai_agent_chat_wizard.py
│           ├── ai_agent_chat_wizard_views.xml
│           ├── ai_sale_followup_wizard.py
│           └── ai_sale_followup_wizard_views.xml
├── .gitignore
└── README.md
```

---

## 🛡️ License
Licensed under the [LGPL-3.0 License](LICENSE).
