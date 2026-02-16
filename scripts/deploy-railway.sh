#!/usr/bin/env bash
# Deploy Dex to Railway
# Run this script from the project root: bash scripts/deploy-railway.sh
#
# Prerequisites:
#   - Railway CLI: npm install -g @railway/cli  (or use npx @railway/cli)
#   - Railway account: https://railway.com (Hobby plan $5/mo)
#   - GEMINI_API_KEY in backend/.env
#
# What this does:
#   1. Logs into Railway (opens browser)
#   2. Creates a new Railway project named "dex"
#   3. Sets environment variables (GEMINI_API_KEY, ENVIRONMENT)
#   4. Deploys using the Dockerfile
#   5. Assigns a public domain
#   6. Runs smoke tests against the live URL

set -euo pipefail

RAILWAY="npx @railway/cli"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Dex Railway Deployment ==="
echo ""

# Step 1: Login
echo "[1/6] Logging into Railway..."
$RAILWAY whoami 2>/dev/null || $RAILWAY login
echo "Logged in as: $($RAILWAY whoami)"
echo ""

# Step 2: Initialize project
echo "[2/6] Creating Railway project..."
$RAILWAY init 2>/dev/null || echo "Project may already exist, continuing..."
echo ""

# Step 3: Set environment variables
echo "[3/6] Setting environment variables..."
GEMINI_KEY=$(grep GEMINI_API_KEY backend/.env | cut -d= -f2)
if [ -z "$GEMINI_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY not found in backend/.env"
    exit 1
fi
$RAILWAY variables set GEMINI_API_KEY="$GEMINI_KEY"
$RAILWAY variables set ENVIRONMENT=production
echo "Environment variables set."
echo ""

# Step 4: Deploy
echo "[4/6] Deploying to Railway (this may take 3-5 minutes)..."
$RAILWAY up --detach
echo "Deployment initiated."
echo ""

# Step 5: Get domain
echo "[5/6] Assigning public domain..."
DOMAIN=$($RAILWAY domain 2>/dev/null || echo "")
if [ -z "$DOMAIN" ]; then
    echo "Generating domain..."
    DOMAIN=$($RAILWAY domain)
fi
echo "Domain: https://$DOMAIN"
echo ""

# Step 6: Smoke tests (wait for deployment to be healthy)
echo "[6/6] Running smoke tests..."
echo "Waiting 30 seconds for deployment to start..."
sleep 30

HEALTH_URL="https://$DOMAIN/health"
echo "Testing health endpoint: $HEALTH_URL"
for i in 1 2 3 4 5; do
    RESPONSE=$(curl -s "$HEALTH_URL" 2>/dev/null || echo "UNREACHABLE")
    if echo "$RESPONSE" | grep -q "agent_ready"; then
        echo "Health check passed: $RESPONSE"
        break
    fi
    echo "Attempt $i/5: $RESPONSE (retrying in 15s...)"
    sleep 15
done

ROOT_URL="https://$DOMAIN/"
echo ""
echo "Testing root URL: $ROOT_URL"
ROOT_RESPONSE=$(curl -s "$ROOT_URL" | head -5)
if echo "$ROOT_RESPONSE" | grep -q "html"; then
    echo "Root serves HTML: OK"
else
    echo "Root response: $ROOT_RESPONSE"
fi

QUERY_URL="https://$DOMAIN/query"
echo ""
echo "Testing query endpoint: $QUERY_URL"
QUERY_RESPONSE=$(curl -s -X POST "$QUERY_URL" \
    -H "Content-Type: application/json" \
    -d '{"question":"What pump does the Sundance Aspen use?"}' 2>/dev/null || echo "UNREACHABLE")
if echo "$QUERY_RESPONSE" | grep -q "answer"; then
    echo "Query endpoint works: OK"
    echo "Response preview: $(echo "$QUERY_RESPONSE" | head -c 200)"
else
    echo "Query response: $QUERY_RESPONSE"
fi

echo ""
echo "=== Deployment Complete ==="
echo "URL: https://$DOMAIN"
echo ""
echo "Share this URL with Adam and Stephen for testing."
echo "Verify manually:"
echo "  1. Open https://$DOMAIN in browser"
echo "  2. Ask: 'What pump does the Sundance Aspen use?'"
echo "  3. Verify streamed response with correct specs"
