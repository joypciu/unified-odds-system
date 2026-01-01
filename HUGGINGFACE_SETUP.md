# 🤗 Hugging Face Setup Guide

## Why Switch to Hugging Face?

Hugging Face Inference Providers offers **better rate limits** than OpenRouter's free tier:

| Provider         | Free Tier              | With Credits                       |
| ---------------- | ---------------------- | ---------------------------------- |
| **Hugging Face** | Generous free tier     | 1,000+ requests/day ($9/month PRO) |
| OpenRouter       | **50 requests/day** ❌ | 1,000 requests/day ($10)           |
| Google Gemini    | 60 requests/min        | N/A                                |

## Setup Steps

### 1. Get Your Hugging Face Token

1. Go to: https://huggingface.co/settings/tokens
2. Click **"New token"**
3. Name: `unified-odds-llm`
4. Type: **Read** (default)
5. Click **"Generate token"**
6. Copy the token (starts with `hf_...`)

### 2. Update Local .env File

Open `agent/.env` and replace:

```bash
HF_TOKEN=your-huggingface-token-here
```

With your actual token:

```bash
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Update VPS .env File

SSH into your VPS and update the file:

```bash
ssh ubuntu@142.44.160.36
cd /home/ubuntu/services/unified-odds/agent
nano .env
```

Update the `HF_TOKEN` line, then save (Ctrl+O, Enter, Ctrl+X).

### 4. Install Dependencies

**Local:**

```powershell
cd "E:\vps deploy\combine 1xbet, fanduel and bet365 (main)"
pip install langchain-huggingface huggingface-hub
```

**VPS:**

```bash
cd /home/ubuntu/services/unified-odds
pip install langchain-huggingface huggingface-hub
sudo systemctl restart unified-odds
```

## Available Models

### Fast Mode (Default)

- **mistralai/Mistral-7B-Instruct-v0.3**
  - Ultra-fast responses
  - Good for quick queries
  - Perfect for general questions

### Reasoning Mode (enable_reasoning=True)

- **meta-llama/Llama-3.3-70B-Instruct**
  - Deep reasoning capabilities
  - Better for complex analysis
  - Slower but more thorough

### Other Great Free Models

- `Qwen/Qwen2.5-72B-Instruct`
- `microsoft/Phi-3.5-mini-instruct`
- `google/gemma-2-9b-it`

## Fallback System

The system automatically tries providers in this order:

1. **Hugging Face** (Primary) - Best rate limits
2. **OpenRouter** (Fallback #1) - If HF fails
3. **Google Gemini** (Fallback #2) - Final fallback

## Testing

Test the setup:

```bash
cd /home/ubuntu/services/unified-odds
python3 agent/quick_start.py
```

## Upgrading to PRO (Optional)

For production use, consider **Hugging Face PRO** ($9/month):

- 20× included inference credits
- 1,000+ free model requests/day
- 8× ZeroGPU quota
- Priority queue access

Subscribe at: https://huggingface.co/subscribe/pro

## Troubleshooting

### "401 Unauthorized"

- Token is invalid or expired
- Generate a new token at https://huggingface.co/settings/tokens

### "Module not found: langchain_huggingface"

```bash
pip install --upgrade langchain-huggingface huggingface-hub
```

### "Rate limit exceeded"

- System will automatically fallback to OpenRouter → Google
- Consider upgrading to HF PRO for higher limits

## API Comparison

| Feature           | Hugging Face | OpenRouter       | Google    |
| ----------------- | ------------ | ---------------- | --------- |
| Free requests/day | 1000+ (PRO)  | 50               | ~8,640    |
| Free models       | ✅ Many      | ✅ Some          | ✅ Gemini |
| Rate limits       | Generous     | Very restrictive | Good      |
| Fallback support  | ✅           | ✅               | ✅        |
| Cost              | $9/month PRO | $10 credits      | Free      |

## Next Steps

1. Get HF token from https://huggingface.co/settings/tokens
2. Update `agent/.env` with `HF_TOKEN`
3. Install dependencies
4. Test with `python3 agent/quick_start.py`
5. Deploy to VPS
6. Monitor usage at https://huggingface.co/settings/billing
