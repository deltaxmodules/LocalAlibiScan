"""Tabela de tecnologias conhecidas.

Usada pelos detetores `database`, `frameworks` e `external_services` (Fase 2) e
pelo extrator de afirmações da documentação (Fase 4). Padrões que terminam em
"*" são prefixos (ex.: "@aws-sdk/*").
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tech:
    id: str
    name: str
    category: str  # "database" | "orm" | "framework" | "service"
    npm: tuple[str, ...] = ()
    pypi: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()  # pacotes importados no código (JS ou Python)
    strings: tuple[str, ...] = ()  # fragmentos em literais de texto (URLs, connection strings)
    env: tuple[str, ...] = ()  # variáveis de ambiente (".env.example")
    config_files: tuple[str, ...] = ()  # nomes de ficheiros de configuração
    doc_names: tuple[str, ...] = ()  # como aparece escrito em documentação
    stdlib: bool = False  # o import não precisa de dependência declarada
    also: tuple[str, ...] = field(default=())  # outras categorias (ex. Supabase: service)

    def names_in_docs(self) -> tuple[str, ...]:
        return self.doc_names or (self.name,)


TECHS: tuple[Tech, ...] = (
    # ------------------------------------------------------------ bases de dados
    Tech(
        "sqlite", "SQLite", "database",
        npm=("better-sqlite3", "sqlite3", "sqlite", "@libsql/client"),
        pypi=("aiosqlite", "sqlite-utils"),
        imports=("better-sqlite3", "sqlite3", "sqlite", "aiosqlite", "sqlite_utils", "@libsql/client"),
        strings=("sqlite:",),
        doc_names=("SQLite", "sqlite3"),
        stdlib=True,
    ),
    Tech(
        "postgresql", "PostgreSQL", "database",
        npm=("pg", "postgres", "pg-promise", "@neondatabase/serverless", "@vercel/postgres"),
        pypi=("psycopg2", "psycopg2-binary", "psycopg", "psycopg-binary", "asyncpg"),
        imports=("pg", "postgres", "pg-promise", "psycopg2", "psycopg", "asyncpg", "@neondatabase/serverless", "@vercel/postgres"),
        strings=("postgres://", "postgresql://", "postgresql+"),
        doc_names=("PostgreSQL", "Postgres"),
    ),
    Tech(
        "mysql", "MySQL", "database",
        npm=("mysql", "mysql2"),
        pypi=("mysqlclient", "pymysql", "mysql-connector-python", "aiomysql"),
        imports=("mysql", "mysql2", "MySQLdb", "pymysql", "aiomysql"),
        strings=("mysql://", "mysql+"),
        doc_names=("MySQL", "MariaDB"),
    ),
    Tech(
        "mongodb", "MongoDB", "database",
        npm=("mongodb", "mongoose"),
        pypi=("pymongo", "motor", "mongoengine", "beanie"),
        imports=("mongodb", "mongoose", "pymongo", "motor", "mongoengine", "beanie"),
        strings=("mongodb://", "mongodb+srv://"),
        doc_names=("MongoDB", "Mongo"),
    ),
    Tech(
        "redis", "Redis", "database",
        npm=("redis", "ioredis", "@upstash/redis"),
        pypi=("redis", "aioredis"),
        imports=("redis", "ioredis", "aioredis", "@upstash/redis"),
        strings=("redis://", "rediss://"),
        env=("REDIS_URL",),
    ),
    Tech(
        "supabase", "Supabase", "database",
        npm=("@supabase/supabase-js", "@supabase/ssr"),
        pypi=("supabase",),
        imports=("@supabase/supabase-js", "@supabase/ssr", "supabase"),
        strings=(".supabase.co",),
        env=("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
        also=("service",),
    ),
    Tech(
        "dynamodb", "DynamoDB", "database",
        npm=("@aws-sdk/client-dynamodb", "@aws-sdk/lib-dynamodb"),
        imports=("@aws-sdk/client-dynamodb", "@aws-sdk/lib-dynamodb"),
    ),
    # ------------------------------------------------------------ ORMs
    Tech(
        "prisma", "Prisma", "orm",
        npm=("prisma", "@prisma/client"),
        imports=("@prisma/client",),
        config_files=("schema.prisma",),
    ),
    Tech(
        "sqlalchemy", "SQLAlchemy", "orm",
        pypi=("sqlalchemy", "flask-sqlalchemy", "sqlmodel"),
        imports=("sqlalchemy", "flask_sqlalchemy", "sqlmodel"),
    ),
    Tech("drizzle", "Drizzle", "orm", npm=("drizzle-orm",), imports=("drizzle-orm",), config_files=("drizzle.config.ts", "drizzle.config.js")),
    Tech("typeorm", "TypeORM", "orm", npm=("typeorm",), imports=("typeorm",)),
    Tech("sequelize", "Sequelize", "orm", npm=("sequelize",), imports=("sequelize",)),
    Tech("django_orm", "Django ORM", "orm", imports=("django.db",), doc_names=("Django ORM",)),
    # ------------------------------------------------------------ frameworks
    Tech("react", "React", "framework", npm=("react",), imports=("react",)),
    Tech(
        "nextjs", "Next.js", "framework",
        npm=("next",), imports=("next",),
        config_files=("next.config.js", "next.config.mjs", "next.config.ts"),
        doc_names=("Next.js", "NextJS"),
    ),
    Tech("vue", "Vue", "framework", npm=("vue",), imports=("vue",), doc_names=("Vue.js", "VueJS", "Vue 3", "Vue 2")),
    Tech("nuxt", "Nuxt", "framework", npm=("nuxt",), imports=("nuxt", "#app"), config_files=("nuxt.config.ts", "nuxt.config.js")),
    Tech("svelte", "Svelte", "framework", npm=("svelte", "@sveltejs/kit"), imports=("svelte", "@sveltejs/kit"), config_files=("svelte.config.js",)),
    Tech("angular", "Angular", "framework", npm=("@angular/core",), imports=("@angular/core",), config_files=("angular.json",)),
    Tech("express", "Express", "framework", npm=("express",), imports=("express",)),
    Tech("fastify", "Fastify", "framework", npm=("fastify",), imports=("fastify",)),
    Tech("koa", "Koa", "framework", npm=("koa",), imports=("koa",)),
    Tech("nestjs", "NestJS", "framework", npm=("@nestjs/core",), imports=("@nestjs/core", "@nestjs/common")),
    Tech("hono", "Hono", "framework", npm=("hono",), imports=("hono",)),
    Tech(
        "vite", "Vite", "framework",
        npm=("vite",), imports=("vite",),
        config_files=("vite.config.js", "vite.config.ts", "vite.config.mjs"),
    ),
    Tech("electron", "Electron", "framework", npm=("electron",), imports=("electron",)),
    Tech("fastapi", "FastAPI", "framework", pypi=("fastapi",), imports=("fastapi",)),
    Tech("flask", "Flask", "framework", pypi=("flask",), imports=("flask",)),
    Tech("django", "Django", "framework", pypi=("django",), imports=("django",), config_files=("manage.py",)),
    Tech("streamlit", "Streamlit", "framework", pypi=("streamlit",), imports=("streamlit",)),
    Tech("gradio", "Gradio", "framework", pypi=("gradio",), imports=("gradio",)),
    Tech("typer", "Typer", "framework", pypi=("typer",), imports=("typer",)),
    Tech("click", "Click", "framework", pypi=("click",), imports=("click",), doc_names=("Python Click",)),
    Tech("langchain", "LangChain", "framework", npm=("langchain", "@langchain/*"), pypi=("langchain", "langchain-*"), imports=("langchain", "langchain_*", "@langchain/*")),
    # ------------------------------------------------------------ serviços externos
    Tech(
        "openai", "OpenAI", "service",
        npm=("openai", "@ai-sdk/openai"), pypi=("openai", "langchain-openai"),
        imports=("openai", "@ai-sdk/openai", "langchain_openai"),
        strings=("api.openai.com",), env=("OPENAI_API_KEY", "OPENAI_*"),
    ),
    Tech(
        "anthropic", "Anthropic", "service",
        npm=("@anthropic-ai/sdk", "@ai-sdk/anthropic"), pypi=("anthropic", "langchain-anthropic"),
        imports=("anthropic", "@anthropic-ai/sdk", "@ai-sdk/anthropic", "langchain_anthropic"),
        strings=("api.anthropic.com",), env=("ANTHROPIC_API_KEY", "ANTHROPIC_*"),
        doc_names=("Anthropic", "Claude API"),
    ),
    Tech(
        "google_ai", "Google Gemini", "service",
        npm=("@google/generative-ai", "@google/genai"), pypi=("google-generativeai", "google-genai"),
        imports=("@google/generative-ai", "@google/genai", "google.generativeai", "google.genai"),
        strings=("generativelanguage.googleapis.com",), env=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        doc_names=("Gemini",),
    ),
    Tech(
        "ollama", "Ollama", "service",
        npm=("ollama",), pypi=("ollama",), imports=("ollama",),
        strings=("localhost:11434", "127.0.0.1:11434"), env=("OLLAMA_HOST", "OLLAMA_*"),
    ),
    Tech(
        "stripe", "Stripe", "service",
        npm=("stripe", "@stripe/stripe-js", "@stripe/react-stripe-js"), pypi=("stripe",),
        imports=("stripe", "@stripe/stripe-js", "@stripe/react-stripe-js"),
        strings=("api.stripe.com", "js.stripe.com"), env=("STRIPE_*",),
    ),
    Tech(
        "github_api", "GitHub API", "service",
        npm=("@octokit/rest", "@octokit/core", "octokit"), pypi=("pygithub",),
        imports=("@octokit/rest", "@octokit/core", "octokit", "github"),
        strings=("api.github.com",), env=("GITHUB_TOKEN",),
    ),
    Tech(
        "aws", "AWS", "service",
        npm=("aws-sdk", "@aws-sdk/*"), pypi=("boto3", "botocore", "aiobotocore"),
        imports=("aws-sdk", "@aws-sdk/*", "boto3", "botocore"),
        strings=("amazonaws.com",), env=("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"),
        doc_names=("AWS", "Amazon Web Services", "S3"),
    ),
    Tech(
        "firebase", "Firebase", "service",
        npm=("firebase", "firebase-admin"), pypi=("firebase-admin",),
        imports=("firebase", "firebase/*", "firebase-admin", "firebase_admin"),
        strings=("firebaseio.com", "firebaseapp.com"), env=("FIREBASE_*",),
    ),
    Tech("sentry", "Sentry", "service", npm=("@sentry/*",), pypi=("sentry-sdk",), imports=("@sentry/*", "sentry_sdk"), env=("SENTRY_DSN",), strings=("ingest.sentry.io",)),
    Tech("twilio", "Twilio", "service", npm=("twilio",), pypi=("twilio",), imports=("twilio",), env=("TWILIO_*",), strings=("api.twilio.com",)),
    Tech("sendgrid", "SendGrid", "service", npm=("@sendgrid/mail",), pypi=("sendgrid",), imports=("@sendgrid/mail", "sendgrid"), env=("SENDGRID_API_KEY",)),
    Tech("resend", "Resend", "service", npm=("resend",), pypi=("resend",), imports=("resend",), env=("RESEND_API_KEY",), strings=("api.resend.com",)),
    Tech("slack", "Slack API", "service", npm=("@slack/web-api", "@slack/bolt"), pypi=("slack-sdk", "slack-bolt"), imports=("@slack/web-api", "@slack/bolt", "slack_sdk", "slack_bolt"), env=("SLACK_*",), strings=("hooks.slack.com", "slack.com/api"), doc_names=("Slack API", "Slack bot", "Slack webhook", "Slack app")),
    Tech("huggingface", "Hugging Face", "service", npm=("@huggingface/inference",), pypi=("huggingface-hub", "transformers"), imports=("@huggingface/inference", "huggingface_hub", "transformers"), env=("HF_TOKEN", "HUGGINGFACE_*"), strings=("huggingface.co",)),
)

TECH_BY_ID: dict[str, Tech] = {t.id: t for t in TECHS}

CATEGORY_LABEL = {
    "database": "Base de dados",
    "orm": "ORM",
    "framework": "Framework",
    "service": "Serviço externo",
}
# Prefixo do id dos Claims de cada categoria.
CATEGORY_PREFIX = {"database": "db", "orm": "orm", "framework": "framework", "service": "service"}


def matches(pattern: str, value: str) -> bool:
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return value == pattern


def matches_any(patterns: tuple[str, ...], value: str) -> bool:
    return any(matches(p, value) for p in patterns)


def techs_in(category: str) -> list[Tech]:
    return [t for t in TECHS if t.category == category or category in t.also]


# Grupos de tecnologias mutuamente exclusivas: se a documentação diz X e o
# código confirma Y do mesmo grupo (e X não tem qualquer sinal), há contradição.
# Tecnologias fora destes grupos (serviços, ORMs, Redis...) costumam coexistir.
EXCLUSIVE_GROUPS: dict[str, str] = {
    "sqlite": "db",
    "postgresql": "db",
    "mysql": "db",
    "mongodb": "db",
    "dynamodb": "db",
    "fastapi": "py_web",
    "flask": "py_web",
    "django": "py_web",
    "express": "js_server",
    "fastify": "js_server",
    "koa": "js_server",
    "hono": "js_server",
    "react": "ui",
    "vue": "ui",
    "svelte": "ui",
    "angular": "ui",
}

# Nomes que também são palavras comuns: na documentação só contam com a
# capitalização exata (ex.: "Express", não "express delivery").
CASE_SENSITIVE_DOC_NAMES: frozenset[str] = frozenset(
    {
        "Express", "Click", "React", "Vue", "Koa", "Hono", "Typer", "Gradio", "Angular", "Svelte",
        "Vite", "Electron", "Slack", "S3", "Mongo", "Resend", "Sentry", "Flask", "Streamlit", "Nuxt",
        "Gemini", "Drizzle", "Prisma",
    }
)
