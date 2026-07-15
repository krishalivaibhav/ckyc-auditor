.PHONY: up fixtures test demo-core demo-watchlist demo-signals demo-casefile demo-ui eval

# One process, no Docker. SQLite sink is rebuilt from fixtures on startup.
up:        ; uvicorn api.main:app --reload --port 8000 && echo "api -> http://localhost:8000/docs"
fixtures:  ; python scripts/make_fixtures.py
test:      ; pytest tests/ -q

# each package must run STANDALONE against fixtures. this is the CP1 gate.
demo-core:      ; python -m core.demo
demo-watchlist: ; python -m watchlist.demo
demo-signals:   ; python -m signals.demo
demo-casefile:  ; python -m casefile.demo
demo-ui:        ; cd ui && npm run dev

eval:      ; python eval/evaluate.py
portfolio: ; python eval/build_portfolio.py
