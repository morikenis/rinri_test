# 倫理研究所 書籍チャット(RAG + Gemma 4)

一般社団法人倫理研究所の刊行書籍を読み込ませ、教えに関する質問に答えるチャットボット。
**さくらのクラウド GPU サーバー(V100 32GB)** 上に Docker Compose で一括デプロイする構成です。

## 構成

| サービス | 役割 | ポート |
|---|---|---|
| `ollama` | LLM 推論(Gemma 4、GPU) | 11434 |
| `tei` | Embedding 推論(bge-m3、CPU) | 8080 |
| `qdrant` | ベクトルDB | 6333 |
| `api` | FastAPI。`/chat` で RAG 回答をストリーム返却 | 8000 |
| `ui` | Streamlit チャット UI | 8501 |

システムプロンプトは `app/prompts.py` で固定、RAG で書籍から関連箇所を取得してプロンプトに注入するハイブリッド構成。

### VRAM 使用想定(V100 32GB)

| 項目 | VRAM |
|---|---|
| Gemma 4 27B(Q4_K_M) | 約 20GB |
| KV キャッシュ(`num_ctx=8192`) | 約 3GB |
| 予備 | 約 9GB |

Embedding(bge-m3)は CPU で動かし、GPU は LLM 専用にしています(V100 は TEI の公式 GPU ビルドが存在しないため)。

## セットアップ

### 1. VPS の初期構築(初回のみ)

Ubuntu 22.04 または 24.04 の新規 VM で、付属のセットアップスクリプトを実行します。

```bash
# SSH でログインしたあと
git clone <this-repo-url> ~/rinri_test
cd ~/rinri_test
sudo bash scripts/setup.sh
```

スクリプトが入れるもの:

- NVIDIA ドライバ(未導入の場合)
- Docker Engine + Compose plugin
- NVIDIA Container Toolkit(`docker run --gpus all` を有効化)

NVIDIA ドライバを新規導入した場合は **一度 reboot** してください。以下で動作確認:

```bash
nvidia-smi
docker run --rm --gpus all ubuntu nvidia-smi
```

### 2. 環境設定

```bash
cd ~/rinri_test
cp .env.example .env
# LLM_MODEL のタグは https://ollama.com/library で確認して合わせる
```

### 3. サービス起動

```bash
docker compose up -d
docker compose ps
```

### 4. Gemma 4 モデルの取得(初回のみ、数十GB)

```bash
docker compose exec ollama ollama pull gemma4:latest
# タグが違う場合は .env の LLM_MODEL と合わせて pull する
```

### 5. 書籍テキストの配置

```bash
# ローカルから scp で .txt を VPS に送る例
scp books/*.txt user@<vps-ip>:~/rinri_test/data/books/
```

### 6. ベクトル化(初回 + 書籍追加時)

```bash
docker compose exec api python -m ingest.ingest --books-dir /srv/data/books --recreate
```

- 400KB × 100 ファイル想定で **CPU TEI だと 15〜30 分**
- 完了後、Qdrant に約 5 万チャンクが格納されます

### 7. アクセス

- UI(推奨): SSH ポートフォワードで `http://localhost:8501`
  ```bash
  ssh -L 8501:localhost:8501 user@<vps-ip>
  ```
- 直接公開する場合は **必ず** nginx + Basic 認証 + HTTPS(certbot)を前段に置くこと

## ディレクトリ

```
rinri_test/
├── docker-compose.yml
├── .env.example
├── scripts/
│   └── setup.sh         # VPS 初期構築(ドライバ/Docker/NVIDIA Toolkit)
├── data/books/          # 書籍 .txt をここに配置(git 管理外)
├── ingest/              # 取り込みパイプライン
│   ├── loader.py        # .txt 読み込み
│   ├── chunker.py       # 日本語の句点ベース分割
│   └── ingest.py        # CLI エントリ
├── app/                 # FastAPI バックエンド
│   ├── main.py
│   ├── rag.py
│   ├── prompts.py       # ★システムプロンプト(倫理研究所向け)
│   ├── clients.py       # Ollama / TEI / Qdrant クライアント
│   ├── config.py
│   └── Dockerfile
└── ui/
    ├── streamlit_app.py
    └── Dockerfile
```

## 設計メモ

### RAG パイプライン
1. ユーザー質問を受信
2. bge-m3(CPU)でクエリを埋め込み(1024 次元、コサイン類似度)
3. Qdrant から top-k(既定 6)を取得
4. システムプロンプト + 書籍引用 + 質問 を Ollama に投げてストリーム生成
5. UI 側で回答と「参照した書籍箇所」を表示

### チャンク分割(`ingest/chunker.py`)
- 句点(。!?)と空行で文を分け、800 字目安でパック。120 字オーバーラップでコンテキスト欠損を防ぐ
- 文の途中で切れないため、引用しても意味が崩れにくい

### システムプロンプト(`app/prompts.py`)
- 敬体。書籍外のことは憶測しない
- 医療・法律・宗教教義の断定的助言を禁止
- 回答末尾に出典を明記させる

## 調整ポイント

- `LLM_MODEL` を別モデルへ差し替え可能(`gemma4:12b` / `gemma3:27b` 等)
- `RAG_TOP_K` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` を `.env` で変更
- 日本語の検索精度をさらに上げるなら BGE Reranker(`bge-reranker-v2-m3`)の追加が有望

## 時間課金運用(使わない時は停止)

さくらのクラウドはシャットダウンでサーバー料金が止まり、ディスク料金のみになります。

```bash
# 使い終わったら
sudo shutdown -h now
# コントロールパネルから「起動」で再開、Docker Compose は restart: unless-stopped で自動復帰
# Ollama のモデルは named volume に残るので再ダウンロード不要
```

起動直後の初回応答は Gemma 4 の VRAM ロードで 30〜60 秒かかります。

## よくある作業

```bash
# 書籍を追加したら再インデックス
docker compose exec api python -m ingest.ingest --books-dir /srv/data/books --recreate

# ログ
docker compose logs -f api
docker compose logs -f ollama

# モデル一覧
docker compose exec ollama ollama list

# ヘルスチェック
curl http://localhost:8000/health
curl http://localhost:6333/collections/rinri_books
```

## V100 以外の GPU を使う場合

`.env` と `docker-compose.yml` の TEI 部分を調整すれば、より新しい GPU で TEI も GPU 推論にできます。

1. `.env` の `TEI_IMAGE` を対応アーキテクチャのタグに変更
   - Ampere(A100): `ghcr.io/huggingface/text-embeddings-inference:1.5`
   - Ampere(A10 / RTX 30xx): `:86-1.5`
   - Ada(L4 / RTX 40xx): `:89-1.5`
   - Hopper(H100): `:hopper-1.5`
2. `docker-compose.yml` の `tei` サービスでコメントアウトしてある `deploy.resources.reservations` を有効化
