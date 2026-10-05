<!-- Gerado por scripts/gen_reference.py a partir do código. Não editar à mão. -->

# Detected technologies

This table is the single source used by the detectors (code, manifests, configuration) and by [documentation vs code](../guide/docs-vs-code). A trailing `*` is a prefix.

## Databases

| Technology | npm | PyPI | Imports | In strings / URLs | Env vars / config files |
|---|---|---|---|---|---|
| **SQLite** | `better-sqlite3`, `sqlite3`, `sqlite`, `@libsql/client` | `aiosqlite`, `sqlite-utils` | `better-sqlite3`, `sqlite3`, `sqlite`, `aiosqlite`, `sqlite_utils`, `@libsql/client` | `sqlite:` | — |
| **PostgreSQL** | `pg`, `postgres`, `pg-promise`, `@neondatabase/serverless`, `@vercel/postgres` | `psycopg2`, `psycopg2-binary`, `psycopg`, `psycopg-binary`, `asyncpg` | `pg`, `postgres`, `pg-promise`, `psycopg2`, `psycopg`, `asyncpg`, `@neondatabase/serverless`, `@vercel/postgres` | `postgres://`, `postgresql://`, `postgresql+` | — |
| **MySQL** | `mysql`, `mysql2` | `mysqlclient`, `pymysql`, `mysql-connector-python`, `aiomysql` | `mysql`, `mysql2`, `MySQLdb`, `pymysql`, `aiomysql` | `mysql://`, `mysql+` | — |
| **MongoDB** | `mongodb`, `mongoose` | `pymongo`, `motor`, `mongoengine`, `beanie` | `mongodb`, `mongoose`, `pymongo`, `motor`, `mongoengine`, `beanie` | `mongodb://`, `mongodb+srv://` | — |
| **Redis** | `redis`, `ioredis`, `@upstash/redis` | `redis`, `aioredis` | `redis`, `ioredis`, `aioredis`, `@upstash/redis` | `redis://`, `rediss://` | `REDIS_URL` |
| **Supabase** (also serviço externo) | `@supabase/supabase-js`, `@supabase/ssr` | `supabase` | `@supabase/supabase-js`, `@supabase/ssr`, `supabase` | `.supabase.co` | `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| **DynamoDB** | `@aws-sdk/client-dynamodb`, `@aws-sdk/lib-dynamodb` | — | `@aws-sdk/client-dynamodb`, `@aws-sdk/lib-dynamodb` | — | — |

## ORMs

| Technology | npm | PyPI | Imports | In strings / URLs | Env vars / config files |
|---|---|---|---|---|---|
| **Prisma** | `prisma`, `@prisma/client` | — | `@prisma/client` | — | `schema.prisma` |
| **SQLAlchemy** | — | `sqlalchemy`, `flask-sqlalchemy`, `sqlmodel` | `sqlalchemy`, `flask_sqlalchemy`, `sqlmodel` | — | — |
| **Drizzle** | `drizzle-orm` | — | `drizzle-orm` | — | `drizzle.config.ts`, `drizzle.config.js` |
| **TypeORM** | `typeorm` | — | `typeorm` | — | — |
| **Sequelize** | `sequelize` | — | `sequelize` | — | — |
| **Django ORM** | — | — | `django.db` | — | — |

## Frameworks

| Technology | npm | PyPI | Imports | In strings / URLs | Env vars / config files |
|---|---|---|---|---|---|
| **React** | `react` | — | `react` | — | — |
| **Next.js** | `next` | — | `next` | — | `next.config.js`, `next.config.mjs`, `next.config.ts` |
| **Vue** | `vue` | — | `vue` | — | — |
| **Nuxt** | `nuxt` | — | `nuxt`, `#app` | — | `nuxt.config.ts`, `nuxt.config.js` |
| **Svelte** | `svelte`, `@sveltejs/kit` | — | `svelte`, `@sveltejs/kit` | — | `svelte.config.js` |
| **Angular** | `@angular/core` | — | `@angular/core` | — | `angular.json` |
| **Express** | `express` | — | `express` | — | — |
| **Fastify** | `fastify` | — | `fastify` | — | — |
| **Koa** | `koa` | — | `koa` | — | — |
| **NestJS** | `@nestjs/core` | — | `@nestjs/core`, `@nestjs/common` | — | — |
| **Hono** | `hono` | — | `hono` | — | — |
| **Vite** | `vite` | — | `vite` | — | `vite.config.js`, `vite.config.ts`, `vite.config.mjs` |
| **Electron** | `electron` | — | `electron` | — | — |
| **FastAPI** | — | `fastapi` | `fastapi` | — | — |
| **Flask** | — | `flask` | `flask` | — | — |
| **Django** | — | `django` | `django` | — | `manage.py` |
| **Streamlit** | — | `streamlit` | `streamlit` | — | — |
| **Gradio** | — | `gradio` | `gradio` | — | — |
| **Typer** | — | `typer` | `typer` | — | — |
| **Click** | — | `click` | `click` | — | — |
| **LangChain** | `langchain`, `@langchain/*` | `langchain`, `langchain-*` | `langchain`, `langchain_*`, `@langchain/*` | — | — |

## External services

| Technology | npm | PyPI | Imports | In strings / URLs | Env vars / config files |
|---|---|---|---|---|---|
| **OpenAI** | `openai`, `@ai-sdk/openai` | `openai`, `langchain-openai` | `openai`, `@ai-sdk/openai`, `langchain_openai` | `api.openai.com` | `OPENAI_API_KEY`, `OPENAI_*` |
| **Anthropic** | `@anthropic-ai/sdk`, `@ai-sdk/anthropic` | `anthropic`, `langchain-anthropic` | `anthropic`, `@anthropic-ai/sdk`, `@ai-sdk/anthropic`, `langchain_anthropic` | `api.anthropic.com` | `ANTHROPIC_API_KEY`, `ANTHROPIC_*` |
| **Google Gemini** | `@google/generative-ai`, `@google/genai` | `google-generativeai`, `google-genai` | `@google/generative-ai`, `@google/genai`, `google.generativeai`, `google.genai` | `generativelanguage.googleapis.com` | `GEMINI_API_KEY`, `GOOGLE_API_KEY` |
| **Ollama** | `ollama` | `ollama` | `ollama` | `localhost:11434`, `127.0.0.1:11434` | `OLLAMA_HOST`, `OLLAMA_*` |
| **Stripe** | `stripe`, `@stripe/stripe-js`, `@stripe/react-stripe-js` | `stripe` | `stripe`, `@stripe/stripe-js`, `@stripe/react-stripe-js` | `api.stripe.com`, `js.stripe.com` | `STRIPE_*` |
| **GitHub API** | `@octokit/rest`, `@octokit/core`, `octokit` | `pygithub` | `@octokit/rest`, `@octokit/core`, `octokit`, `github` | `api.github.com` | `GITHUB_TOKEN` |
| **AWS** | `aws-sdk`, `@aws-sdk/*` | `boto3`, `botocore`, `aiobotocore` | `aws-sdk`, `@aws-sdk/*`, `boto3`, `botocore` | `amazonaws.com` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |
| **Firebase** | `firebase`, `firebase-admin` | `firebase-admin` | `firebase`, `firebase/*`, `firebase-admin`, `firebase_admin` | `firebaseio.com`, `firebaseapp.com` | `FIREBASE_*` |
| **Sentry** | `@sentry/*` | `sentry-sdk` | `@sentry/*`, `sentry_sdk` | `ingest.sentry.io` | `SENTRY_DSN` |
| **Twilio** | `twilio` | `twilio` | `twilio` | `api.twilio.com` | `TWILIO_*` |
| **SendGrid** | `@sendgrid/mail` | `sendgrid` | `@sendgrid/mail`, `sendgrid` | — | `SENDGRID_API_KEY` |
| **Resend** | `resend` | `resend` | `resend` | `api.resend.com` | `RESEND_API_KEY` |
| **Slack API** | `@slack/web-api`, `@slack/bolt` | `slack-sdk`, `slack-bolt` | `@slack/web-api`, `@slack/bolt`, `slack_sdk`, `slack_bolt` | `hooks.slack.com`, `slack.com/api` | `SLACK_*` |
| **Hugging Face** | `@huggingface/inference` | `huggingface-hub`, `transformers` | `@huggingface/inference`, `huggingface_hub`, `transformers` | `huggingface.co` | `HF_TOKEN`, `HUGGINGFACE_*` |
