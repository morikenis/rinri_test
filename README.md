# 倫理研究所 書籍チャット(RAG + Gemma 4)

一般社団法人倫理研究所の刊行書籍を読み込ませ、教えに関する質問に答えるチャットボット。
ConoHa VPS(GPU 24GB+)上に Docker Compose で一括デプロイする構成です。

## 構成

| サービス | 役割 | ポート |
|---|---|---|
| `ollama` | LLM 推論(Gemma 4) | 11434 |
| `tei` | Embedding 推論(bge-m3) | 8080 |
| `qdrant` | ベクトルDB | 6333 |
| `api` | FastAPI。`/chat` で RAG 回答をストリーム返却 | 8000 |
| `ui` | Streamlit チャット UI | 8501 |

システムプロンプトは `app/prompts.py` で固定、RAG で書籍から関連箇所を取得してプロンプトに注入するハイブリッド構成。

## 前提(VPS 側セットアップ)

1. NVIDIA ドライバ導入済み
2. Docker + Docker Compose v2
3. [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) 導入済み
   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

## セットアップ手順

```bash
git clone <this-repo>
cd rinri_test
cp .env.example .env
# 必要なら .env を編集(LLM_MODEL のタグなど)

# 1) サービス起動
docker compose up -d

# 2) Gemma 4 モデルを pull(初回のみ・数GB〜数十GB)
docker compose exec ollama ollama pull gemma4:latest
# タグは .env の LLM_MODEL と合わせる

# 3) 書籍テキストを配置
cp /path/to/*.txt data/books/

# 4) ベクトル化(初回 or 再インデックス時は --recreate)
docker compose exec api python -m ingest.ingest --books-dir /srv/data/books --recreate
```

## アクセス

- UI: `http://<vps-ip>:8501`
- API: `http://<vps-ip>:8000/health`

本番運用では nginx + Let's Encrypt(certbot)で HTTPS 化とベーシック認証/OAuth を前段に置く想定。

## ディレクトリ

```
rinri_test/
├── docker-compose.yml
├── .env.example
├── data/books/         # 書籍 .txt をここに配置(git 管理外)
├── ingest/             # 取り込みパイプライン
│   ├── loader.py       # .txt 読み込み
│   ├── chunker.py      # 日本語の句点ベース分割
│   └── ingest.py       # CLI エントリ
├── app/                # FastAPI バックエンド
│   ├── main.py
│   ├── rag.py
│   ├── prompts.py      # ★システムプロンプト(倫理研究所向け)
│   ├── clients.py      # Ollama / TEI / Qdrant クライアント
│   ├── config.py
│   └── Dockerfile
└── ui/
    ├── streamlit_app.py
    └── Dockerfile
```

## 設計メモ

### RAG パイプライン
1. ユーザー質問を受信
2. bge-m3 でクエリを埋め込み(1024 次元、コサイン類似度)
3. Qdrant から top-k(既定 6)を取得
4. システムプロンプト + 書籍引用 + 質問 を Ollama に投げてストリーム生成
5. UI 側で回答と「参照した書籍箇所」を表示

### チャンク分割(`ingest/chunker.py`)
- 句点(。!?)と空行で文を分け、800字目安でパック。120字オーバーラップでコンテキスト欠損を防ぐ
- 文の途中で切れないため、引用しても意味が崩れにくい

### システムプロンプト(`app/prompts.py`)
- 敬体で、書籍外のことは憶測しない
- 医療・法律・宗教教義の断定的助言を禁止
- 回答末尾に出典を明記させる

## 調整ポイント

- `LLM_MODEL` を別モデルへ差し替え可能(`gemma4:27b` / `gemma3:27b` 等)
- `RAG_TOP_K` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` を `.env` で変更
- 日本語の検索精度をさらに上げるなら BGE Reranker(`bge-reranker-v2-m3`)を追加する拡張が有望

## よくある作業

```bash
# 書籍を追加したら再インデックス
docker compose exec api python -m ingest.ingest --books-dir /srv/data/books --recreate

# ログ
docker compose logs -f api
docker compose logs -f ollama

# モデル一覧
docker compose exec ollama ollama list
```
