import os
import yfinance as yf
import anthropic
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY', ''))

ALLOWED_TYPES = {'stock', 'crypto', 'etf'}

SUGGESTIONS = [
    {'ticker': 'NVDA', 'type': 'stock'},
    {'ticker': 'AAPL', 'type': 'stock'},
    {'ticker': 'TSLA', 'type': 'stock'},
    {'ticker': 'BTC-USD', 'type': 'crypto'},
    {'ticker': 'ETH-USD', 'type': 'crypto'},
    {'ticker': 'META', 'type': 'stock'},
    {'ticker': 'JPM', 'type': 'stock'},
    {'ticker': 'AMZN', 'type': 'stock'},
]


@app.get('/')
def index():
    return render_template('index.html', suggestions=SUGGESTIONS)


@app.get('/health')
def health():
    return jsonify({'ok': True})


@app.post('/api/brief')
def api_brief():
    data = request.get_json(force=True)
    ticker = data.get('ticker', '').strip().upper()
    if not ticker or len(ticker) > 10:
        return jsonify({'error': 'Invalid ticker.'}), 400

    # Fetch headlines via yfinance
    try:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info or {}
        name = info.get('shortName') or info.get('longName') or ticker
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        news_raw = yf_ticker.news or []
    except Exception as e:
        return jsonify({'error': f'Could not fetch data for {ticker}.'}), 502

    if not news_raw:
        return jsonify({'error': f'No news found for {ticker}. Try a different ticker.'}), 404

    headlines = [
        a.get('content', {}).get('title', '') or a.get('title', '')
        for a in news_raw[:8]
        if a.get('content', {}).get('title') or a.get('title')
    ]
    if not headlines:
        return jsonify({'error': f'No readable headlines for {ticker}.'}), 404

    headline_block = '\n'.join(f'- {h}' for h in headlines[:8])

    price_context = f'Current price: ${current_price:.2f}. ' if current_price else ''

    prompt = (
        f'You are a concise financial analyst. {price_context}'
        f'Based on these recent headlines for {name} ({ticker}), write a 3-sentence market brief. '
        f'Be specific, factual, and direct. Do not give investment advice.\n\n'
        f'Headlines:\n{headline_block}'
    )

    try:
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}],
        )
        brief = response.content[0].text.strip()
    except anthropic.APIError as e:
        return jsonify({'error': f'AI service error: {e}'}), 502

    return jsonify({
        'ticker': ticker,
        'name': name,
        'price': current_price,
        'headlines': headlines[:8],
        'brief': brief,
    })
