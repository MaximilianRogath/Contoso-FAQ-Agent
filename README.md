# Contoso FAQ Agent

A minimal example showing how to build a RAG-based FAQ agent using the **Microsoft Agent Framework** — with Azure AI Search as the knowledge base and multi-turn conversations via `AgentSession`.

## What this project demonstrates

- **Creating an agent** with `FoundryChatClient` and `Agent(client=..., instructions=...)`
- **Registering a tool** with the `@tool` decorator — imported directly from `agent_framework`
- **RAG pattern** — Azure AI Search (hybrid: full-text + vector + semantic reranking) as the knowledge source
- **Multi-turn conversation** with `agent.create_session()` and `InMemoryHistoryProvider`
- **Keyless authentication** via `AzureCliCredential` — no API keys required for any Azure resource
- **`.env` configuration** via `load_dotenv()`

## Project structure

```
├── faq_agent.py        # Main file — agent with search_faq tool
├── setup_index.py      # Run once — creates the index and uploads FAQs
├── contoso_faq.json    # FAQ data (customisable)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .gitignore
└── LICENSE
```

## Prerequisites

- Python 3.11+
- [Azure CLI](https://aka.ms/installazurecli) — used for keyless authentication
- An [Azure subscription](https://azure.microsoft.com/free/)
- The following Azure resources:
  - **Azure AI Foundry** — project with a deployed model (e.g. `gpt-4o`)
  - **Azure OpenAI** — embedding deployment (e.g. `text-embedding-3-small`)
  - **Azure AI Search** — resource with Semantic Ranker enabled

## Setup

**1. Clone the repository and install dependencies**

```bash
git clone https://github.com/MaximilianRogath/Contoso-FAQ-Agent
cd Contoso-FAQ-Agent
python -m pip install -r requirements.txt
```

**2. Log in to Azure**

```bash
az login
```

**3. Enable RBAC on Azure AI Search**

This project uses keyless authentication for all Azure resources — no API keys required. Azure AI Search requires role-based access control (RBAC) to be enabled explicitly:

1. Go to your Azure AI Search resource in the [Azure portal](https://portal.azure.com)
2. Navigate to **Settings → Keys**
3. Select **Role-based access control** and save
4. Go to **Access control (IAM) → Add role assignment** and assign yourself:
   - **Search Service Contributor** — to create and manage the index
   - **Search Index Data Contributor** — to upload and query documents

> Role assignments can take a few minutes to take effect.

**4. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and fill in your endpoints. No API keys needed — authentication runs via Azure CLI.

**5. Create the Azure AI Search index (run once)**

```bash
python setup_index.py
```

This deletes any existing index, creates a fresh one, generates embeddings for all FAQ entries in `contoso_faq.json`, and uploads them. Re-run this script whenever you update the FAQ data.

**6. Start the agent**

```bash
python faq_agent.py
```

## Example interaction

```
You: What payment methods do you accept?
Agent: Contoso accepts credit card (Visa, Mastercard, Amex), PayPal, and
       SEPA direct debit. Annual billing includes 2 months free.

You: And how do I get an invoice?
Agent: Invoices are sent automatically by email after each payment and are
       also available under Settings → Billing → Invoice history.
```

## Customising the FAQ data

`contoso_faq.json` contains FAQ entries in the following format:

```json
{
  "id": "faq-001",
  "question": "How do I create an account?",
  "answer": "Visit contoso.com/register ...",
  "category": "Account"
}
```

After making changes, re-run `setup_index.py` — it will delete the existing index and rebuild it from scratch.

## Further reading

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Azure AI Search Documentation](https://learn.microsoft.com/en-us/azure/search/)
- [Azure AI Foundry](https://ai.azure.com/)

## License

This project is licensed under the [MIT License](LICENSE).