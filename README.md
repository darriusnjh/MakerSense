# GovTech Demo - LangGraph Multi-Agent Marketing Workflow

This project implements the workflow in `docs/Multi Agent 320d5f5ab35480819ad7fbd2b803ed41.md` with:

- LangGraph orchestration
- OpenAI-powered specialist agents
- MCP server for tool access
- JSON dummy data backend that can be switched to Postgres
- Nano Banana image generation client

## Project layout

- `src/workflow/graph.py`: LangGraph state machine
- `src/agents/nodes.py`: orchestrator and specialist node logic
- `src/mcp_server.py`: MCP tool server
- `src/storage/`: backend abstraction (`json` and `postgres`)
- `src/services/`: analytics/compliance/scoring/memory/scheduling/image services
- `data/*.json`: dummy processed social analytics data

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
```

Fill `.env` with your keys:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY` (preferred for Nano Banana via `gemini-2.5-flash-image`)
- `NANO_BANANA_API_KEY` (fallback alias if `GEMINI_API_KEY` is empty)
- `WEB_SEARCH_API_KEY` (for `WEB_SEARCH_PROVIDER=tavily` or `serpapi`)

Generated images are saved locally under `GENERATED_IMAGES_DIR` (default `data/generated_images`).

## Run the campaign workflow

```bash
python -m src.run_campaign --request "Build a 2-week campaign for our fintech creator product"
```

Optional:

- `--brand-id`
- `--campaign-id`
- `--reflect` (runs the post-performance learning loop)
- `--realtime` (prints node-by-node execution updates with timestamps)
- `--trace-file logs/workflow_trace.jsonl` (writes structured run trace events)
- `--exclude-campaign-state-from-planner` (planner will not receive `campaign_state` context)

Task routing behavior:

- The orchestrator LLM now assigns tasks from request intent and context.
- If routing JSON is invalid/unavailable, the workflow falls back to deterministic keyword routing.
- Simple research questions can skip planner/creative/compliance automatically.
- Full campaign or generation requests will run planner and creative pipeline.
- Final output includes `task_plan_source` so you can see which router was used.

Example with live progress:

```bash
python -m src.run_campaign --request "Build a 2-week campaign for our fintech creator product" --realtime --trace-file logs/workflow_trace.jsonl
```

## Run the live frontend monitor

```bash
streamlit run src/frontend_app.py
```

Then open the local Streamlit URL shown in terminal.

What it shows live:

- node-by-node task progress across the LangGraph pipeline
- routing plan assigned by orchestrator (`task_plan` + `task_plan_source`)
- real-time event feed (`node`, `updated keys`, timestamp)
- final output JSON and downloadable result file
- campaign output gallery (captions, CTAs, channels, generated images or image errors)
- image controls for Nano Banana:
  - `Subject images` upload (passed as subject image inputs to Nano Banana)
  - `Subject labels (optional)` and `Image elements` (text constraints for composition)

Uploaded subject images are saved to `data/subject_uploads/<campaign_id>/` and then referenced in generation calls.

## Run the MCP server

```bash
python -m src.mcp_server
```

## Test web search directly

```bash
python scripts/test_websearch.py "govtech competitor social media trends"
```

Optional:

- `--max-results 3`
- `--provider tavily`
- `--full`
- `--save-json logs/websearch_result.json`

The server exposes tools such as:

- `get_trend_data`
- `web_search`
- `get_comments`
- `get_competitor_posts`
- `get_brand_guidelines`
- `score_compliance`
- `schedule_post`
- `update_memory`
- `score_candidate_post`

## Switch to Postgres backend

Set in `.env`:

- `DATA_BACKEND=postgres`
- `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname`

`PostgresRepository` auto-creates its tables on startup.
