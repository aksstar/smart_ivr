#!/usr/bin/env bash
set -e

PORT="${PORT:-8080}"
export SSL_CERT_FILE=$(python3 -m certifi)
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-$(python3 -c 'import config_loader; print(config_loader.GOOGLE_CLOUD_PROJECT)')}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-$(python3 -c 'import config_loader; print(config_loader.GOOGLE_CLOUD_LOCATION)')}"
export GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-TRUE}"

cat <<EOF > /etc/nginx/conf.d/default.conf
map \$http_upgrade \$connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen ${PORT};
    server_name _;

    client_max_body_size 50M;

    # Route /live-ws/ to the Full-Duplex Gemini Live WebSocket server on port 8765
    location /live-ws/ {
        proxy_pass http://127.0.0.1:8765/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # Route all other traffic (and Streamlit /_stcore/stream WebSockets) to Streamlit on port 8501
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default

echo "🚀 Starting Gemini Live WebSocket Bridge on 127.0.0.1:8765..."
python3 /app/live_ws_server.py 2>&1 &

echo "🎙️ Starting Streamlit Command Center on 127.0.0.1:8501..."
streamlit run /app/app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false 2>&1 &

echo "⏳ Waiting for Streamlit (127.0.0.1:8501) to become ready before opening port ${PORT}..."
for i in $(seq 1 45); do
    if curl -sf http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
        echo "✅ Streamlit is healthy on 127.0.0.1:8501!"
        break
    fi
    sleep 1
done

echo "🌐 Starting Nginx Reverse Proxy on port ${PORT}..."
exec nginx -g "daemon off;"
