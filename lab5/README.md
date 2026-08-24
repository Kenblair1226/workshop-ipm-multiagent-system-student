# Lab 5 可執行資產：跨雲 Grounding

完整教學與雲端設定步驟見
[Lab 5：Foundry IQ 跨雲 Grounding](../docs/05-lab5-cross-cloud-grounding.md)。

## 內容

```text
lab5/
├── foundry_iq/provision.py    產生、建立、檢查及刪除三個 knowledge source、KB 與 RemoteTool connection
├── configs/                   Azure AI Search 2026-05-01-preview REST JSON 範本
├── hosted-agent/              只連 Foundry Toolbox 的 Hosted Agent
├── s3-mcp-proxy/              固定 bucket/prefix、只有 list/read 的 S3 MCP proxy
├── sample-data/               Azure、AWS、GCP 各一份可辨識文件
├── toolbox.yaml               只允許 knowledge_base_retrieve
├── azure.yaml                 Hosted Agent direct-code deployment
└── tests/                     不需雲端資源即可執行的 payload 與 agent 設定測試
```

## 本機驗證

```bash
cd lab5
uv sync --dev
uv run pytest

cd s3-mcp-proxy
uv sync --dev
uv run pytest
```

## 產生設定而不呼叫雲端

```bash
cd lab5
cp .env.example .env
# 填完所有必要值後：
uv run python -m foundry_iq.provision plan
uv run python -m foundry_iq.provision toolbox > toolbox.resolved.yaml
```

`plan` 會遮蔽 S3 bearer token。Hosted Agent 的環境只有 Foundry project、模型部署與
Toolbox endpoint；AWS、Google、Storage credentials 不會進入 agent container。
