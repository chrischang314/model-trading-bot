.PHONY: backend frontend test compose-up compose-down

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && pnpm run dev -- --host 127.0.0.1 --port 5173

test:
	cd backend && python -m pytest

compose-up:
	docker compose up --build

compose-down:
	docker compose down
